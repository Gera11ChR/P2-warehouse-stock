"""RF-3 (saneamiento-2): acotación del header `X-Actor`.

`X-Actor` es un identificador NO autenticado (autenticación real fuera de
alcance, desviación conocida de Constitución §3.1/§3.3 reconocida por el
humano). Solo se valida su forma: 1..100 caracteres, con al menos un
carácter no blanco y sin caracteres de control (C0 `\\x00-\\x1f` ni
DEL/C1 `\\x7f-\\x9f`). El rechazo es un 422 que ocurre ANTES de abrir
sesión de base de datos.
"""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app import security

RUTA = "/api/v1/catalogo"  # no exige scope: 200 para cualquier actor válido


def _cliente() -> AsyncClient:
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _get(actor: str | bytes | None) -> Any:
    # Starlette decodifica los headers como latin-1: se envían como bytes.
    headers: dict[bytes, bytes] = {}
    if actor is not None:
        headers[b"X-Actor"] = (
            actor if isinstance(actor, bytes) else actor.encode("latin-1")
        )
    async with _cliente() as c:
        return await c.get(RUTA, headers=headers)


class _SessionLocalEspia:
    """Sustituto de `SessionLocal`: cuenta los intentos de abrir sesión."""

    def __init__(self) -> None:
        self.checkouts = 0

    def __call__(self) -> Any:
        self.checkouts += 1
        raise AssertionError("El rechazo de X-Actor no debe abrir sesión")


@pytest.fixture
def espia(monkeypatch: pytest.MonkeyPatch) -> _SessionLocalEspia:
    espia = _SessionLocalEspia()
    monkeypatch.setattr(security, "SessionLocal", espia)
    return espia


RECHAZADOS: list[tuple[str, str | bytes]] = [
    ("101_caracteres", "a" * 101),
    ("vacio", ""),
    ("solo_espacios", "   "),
    ("solo_tab", "\t"),
    ("tab_interno", "Juan\tPerez"),
    ("salto_de_linea", "Juan\nPerez"),
    ("salto_de_linea_final", "Juan\n"),
    ("retorno_de_carro", "Juan\rPerez"),
    ("nul", "Juan\x00Perez"),
    ("del", "Juan\x7fPerez"),
    ("c1_nel", b"Juan\x85Perez"),
    ("c1_x9f", b"Juan\x9fPerez"),
]


@pytest.mark.parametrize(
    "actor", [v for _, v in RECHAZADOS], ids=[n for n, _ in RECHAZADOS]
)
async def test_RF_3_actor_invalido_422_sin_consultar_scopes(
    espia: _SessionLocalEspia, actor: str | bytes
) -> None:
    resp = await _get(actor)
    assert resp.status_code == 422, resp.text
    assert espia.checkouts == 0


async def test_RF_3_control_positivo_actor_valido_si_abre_sesion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control del espía: con un actor VÁLIDO la dependencia sí abre sesión
    (1 checkout); así el test de rechazo no es vacuo ante cambios futuros."""
    cuenta = {"n": 0}
    original = security.SessionLocal

    def contador() -> Any:
        cuenta["n"] += 1
        return original()

    monkeypatch.setattr(security, "SessionLocal", contador)
    resp = await _get("qa")
    assert resp.status_code == 200, resp.text
    assert cuenta["n"] == 1


async def test_RF_3_actor_ausente_422_sin_consultar_scopes(
    espia: _SessionLocalEspia,
) -> None:
    resp = await _get(None)
    assert resp.status_code == 422, resp.text
    assert espia.checkouts == 0


async def test_RF_3_tabulador_por_http_422(client_factory: Any) -> None:
    """`\\t` es representable en un header HTTP real: 422 por el cliente
    estándar de la suite."""
    async with client_factory("Juan\tPerez") as c:
        resp = await c.get(RUTA)
    assert resp.status_code == 422, resp.text


async def test_RF_3_salto_de_linea_y_nul_por_dependencia_directa() -> None:
    """h11 no admite LF/NUL en un header real: se verifica además la
    validación sobre la dependencia (`Annotated[str, Header(...)]`)."""
    from pydantic import TypeAdapter, ValidationError

    ta = TypeAdapter(security.ActorHeader)
    invalidos = (
        "Juan\nPerez", "Juan\x00Perez", "\x00", "\x01", "\x7f", "\x9f",
        "Juan\n", "", "  ", "a" * 101,
    )
    for invalido in invalidos:
        with pytest.raises(ValidationError):
            ta.validate_python(invalido)
    for valido in ("a" * 100, "Juan Perez", "José", "qa"):
        assert ta.validate_python(valido) == valido


async def test_RF_3_openapi_declara_la_restriccion() -> None:
    from app.main import app

    params = app.openapi()["paths"]["/api/v1/catalogo"]["get"]["parameters"]
    actor = next(p for p in params if p["name"] == "X-Actor")
    assert actor["schema"]["minLength"] == 1
    assert actor["schema"]["maxLength"] == 100
    assert "pattern" in actor["schema"]


@pytest.mark.parametrize(
    "actor",
    [
        "a" * 100,  # E4: exactamente 100
        "Juan Perez",  # E5: espacios internos
        "José".encode("latin-1"),  # acentos (Starlette decodifica latin-1)
        "qa",
        "p2admin",
        "demo-operador",
        "intruso",
        " qa ",  # espacios laterales con un carácter no blanco
    ],
    ids=["100_chars", "espacio_interno", "acento", "qa", "p2admin",
         "demo_operador", "intruso", "espacios_laterales"],
)
async def test_RF_3_actor_valido_200(actor: str | bytes) -> None:
    resp = await _get(actor)
    assert resp.status_code == 200, resp.text


async def test_RF_3_actor_valido_conserva_resolucion_de_scopes(
    client: Any, client_sin_scope: Any
) -> None:
    """Los actores del seed siguen resolviéndose igual: `qa` opera con su
    scope; `intruso` (sin scope) sigue recibiendo 403 en rutas con scope."""
    resp = await client.post("/api/v1/catalogo", json={"descripcion": "Con scope"})
    assert resp.status_code == 201, resp.text
    resp = await client_sin_scope.post(
        "/api/v1/catalogo", json={"descripcion": "Intruso"}
    )
    assert resp.status_code == 403, resp.text
