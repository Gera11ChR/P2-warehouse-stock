"""RF-5 (saneamiento-2): guardián de la convención `resultado = 'EXITO'`.

`'EXITO'` es el ÚNICO valor de `auditoria_eventos.resultado` que emiten el
código vivo y las stored functions vigentes (D-1: convención formalizada con
este guardián, sin migración ni CHECK). El ledger es append-only: los
eventos históricos y la migración 0027 (cuyo `'OK'` es texto histórico de
eventos ya purgados) NO se tocan y quedan exentos; el guardián solo inspecciona
las funciones VIGENTES (`pg_get_functiondef` de `public`), nunca las
migraciones.

Comprobaciones:
  (a) stored functions vigentes + DEFAULT de la columna;
  (b) barrido defensivo de `backend/app/**/*.py`;
  (c) valores reales tras un flujo representativo vía API.
"""

import ast
import re
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.helpers.fabrica import (
    ajustar_stock,
    borrador_devol,
    borrador_teams,
    cancelar,
    carga_inicial,
    crear_equipo,
    crear_material,
    fibra_ajuste,
    fibra_carga_inicial,
    procesar,
)

APP_DIR = Path(__file__).resolve().parents[1] / "app"
EXITO = "'EXITO'"


class SqlNoAnalizable(ValueError):
    """Un INSERT en `auditoria_eventos` cuya forma el guardián no sabe
    analizar: se falla de forma conservadora para forzar su revisión."""


# ── Análisis de texto SQL (quote-aware) ─────────────────────────────────


def _sin_comentarios(sql: str) -> str:
    """Elimina `-- ...` y `/* ... */` respetando los literales `'...'`."""
    out: list[str] = []
    i, n = 0, len(sql)
    en_literal = False
    while i < n:
        c = sql[i]
        if en_literal:
            out.append(c)
            if c == "'":
                en_literal = False
            i += 1
        elif c == "'":
            en_literal = True
            out.append(c)
            i += 1
        elif sql.startswith("--", i):
            while i < n and sql[i] != "\n":
                i += 1
        elif sql.startswith("/*", i):
            fin = sql.find("*/", i + 2)
            i = n if fin == -1 else fin + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _cierre(s: str, abre: int) -> int:
    """Índice del `)` que cierra el `(` de la posición `abre`."""
    prof, en_literal = 0, False
    for j in range(abre, len(s)):
        c = s[j]
        if en_literal:
            en_literal = c != "'"
        elif c == "'":
            en_literal = True
        elif c == "(":
            prof += 1
        elif c == ")":
            prof -= 1
            if prof == 0:
                return j
    raise SqlNoAnalizable("paréntesis sin cerrar")


def _partir(s: str) -> list[str]:
    """Separa por comas de primer nivel (fuera de paréntesis y literales)."""
    partes: list[str] = []
    prof, en_literal, actual = 0, False, []
    for c in s:
        if en_literal:
            actual.append(c)
            en_literal = c != "'"
            continue
        if c == "'":
            en_literal = True
        elif c == "(":
            prof += 1
        elif c == ")":
            prof -= 1
        elif c == "," and prof == 0:
            partes.append("".join(actual).strip())
            actual = []
            continue
        actual.append(c)
    partes.append("".join(actual).strip())
    return partes


_INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+(?:public\.)?auditoria_eventos\b", re.IGNORECASE
)
_VALUES_RE = re.compile(r"\s*VALUES\s*\(", re.IGNORECASE)


def resultados_insertados(sql: str) -> list[str | None]:
    """Expresión de `resultado` de cada `INSERT INTO auditoria_eventos`
    (normalizada en espacios). `None` = columna omitida (aplica el DEFAULT,
    que el guardián comprueba aparte). Lanza `SqlNoAnalizable` si el INSERT
    no tiene la forma `(cols) VALUES (...)`."""
    limpio = _sin_comentarios(sql)
    hallados: list[str | None] = []
    for m in _INSERT_RE.finditer(limpio):
        resto = limpio[m.end():]
        ini = len(resto) - len(resto.lstrip())
        if not resto[ini:].startswith("("):
            raise SqlNoAnalizable("INSERT sin lista de columnas")
        abre = m.end() + ini
        cierra = _cierre(limpio, abre)
        columnas = [c.strip().lower() for c in _partir(limpio[abre + 1:cierra])]
        v = _VALUES_RE.match(limpio, cierra + 1)
        if v is None:
            raise SqlNoAnalizable("INSERT sin cláusula VALUES (...)")
        valores = _partir(limpio[v.end():_cierre(limpio, v.end() - 1)])
        if len(valores) != len(columnas):
            raise SqlNoAnalizable("columnas y valores no coinciden")
        if "resultado" not in columnas:
            hallados.append(None)
        else:
            hallados.append(
                re.sub(r"\s+", " ", valores[columnas.index("resultado")])
            )
    return hallados


def violaciones_sql(nombre: str, sql: str) -> list[str]:
    """Hallazgos de un cuerpo SQL: todo `resultado` literal distinto de
    `'EXITO'` (o expresión no literal) es una violación."""
    try:
        resultados = resultados_insertados(sql)
    except SqlNoAnalizable as exc:
        return [f"{nombre}: INSERT no analizable ({exc})"]
    return [
        f"{nombre}: resultado = {r}"
        for r in resultados
        if r is not None and r != EXITO
    ]


# ── Pruebas del propio analizador (el guardián sí detecta 'OK') ─────────


def test_RF_5_analizador_detecta_valor_distinto_de_exito() -> None:
    """Escenario de spec: una función que inserta `resultado = 'OK'` hace
    fallar el guardián."""
    cuerpo = """
        INSERT INTO auditoria_eventos (usuario, tipo_accion, resultado, detalles)
        VALUES (CURRENT_USER, 'X', 'OK', jsonb_build_object('a', 1));
    """
    assert violaciones_sql("fn_mala", cuerpo) == ["fn_mala: resultado = 'OK'"]


def test_RF_5_analizador_acepta_exito_y_tolera_comentarios_con_parentesis() -> None:
    cuerpo = """
        INSERT INTO auditoria_eventos (
            usuario, resultado, detalles
        ) VALUES (
            -- comentario (con paréntesis sin cerrar y 'comilla
            COALESCE(NULLIF(current_setting('app.actor', true), ''), CURRENT_USER),
            'EXITO', /* otro (comentario */ jsonb_build_object('k', 'v, w')
        );
    """
    assert violaciones_sql("fn_buena", cuerpo) == []


def test_RF_5_analizador_marca_expresion_no_literal_y_forma_desconocida() -> None:
    no_literal = (
        "INSERT INTO auditoria_eventos (usuario, resultado) "
        "VALUES (CURRENT_USER, v_res)"
    )
    assert violaciones_sql("f1", no_literal) == ["f1: resultado = v_res"]
    por_select = (
        "INSERT INTO auditoria_eventos (usuario, resultado) "
        "SELECT usuario, 'OK' FROM otra"
    )
    assert "no analizable" in violaciones_sql("f2", por_select)[0]


# ── (a) Stored functions vigentes y DEFAULT de la columna ───────────────


async def test_RF_5_a_funciones_vigentes_solo_insertan_exito(session) -> None:
    filas = (
        await session.execute(
            text(
                "SELECT p.proname, pg_get_functiondef(p.oid) "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public' AND p.prokind IN ('f', 'p') "
                "ORDER BY p.proname, p.oid"
            )
        )
    ).all()
    assert filas, "no se encontraron funciones en public"
    con_insert = 0
    violaciones: list[str] = []
    for nombre, definicion in filas:
        if _INSERT_RE.search(_sin_comentarios(definicion)):
            con_insert += 1
        violaciones += violaciones_sql(nombre, definicion)
    # Sanidad: el análisis realmente vio las funciones que auditan.
    assert con_insert >= 10, con_insert
    assert violaciones == []


async def test_RF_5_a_default_de_la_columna_es_nulo_o_exito(session) -> None:
    fila = (
        await session.execute(
            text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND table_name = 'auditoria_eventos' "
                "AND column_name = 'resultado'"
            )
        )
    ).all()
    assert len(fila) == 1, "columna auditoria_eventos.resultado inexistente"
    default = fila[0][0]
    assert default is None or default.startswith(EXITO), default


# ── (b) Barrido defensivo de backend/app ────────────────────────────────

_ASIGNA_RE = re.compile(
    r"""\bresultado["']?\s*(?:=|:)\s*(["'])(?P<valor>[^"']*)\1"""
)


def _hallazgos_fuente(ruta: Path, fuente: str) -> list[str]:
    hallazgos = [
        f"{ruta.name}: resultado = '{m['valor']}'"
        for m in _ASIGNA_RE.finditer(fuente)
        if m["valor"] != "EXITO"
    ]
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            if _INSERT_RE.search(nodo.value):
                hallazgos += violaciones_sql(ruta.name, nodo.value)
    return hallazgos


def test_RF_5_b_app_sin_literales_resultado_distintos_de_exito() -> None:
    archivos = sorted(APP_DIR.rglob("*.py"))
    assert archivos, "backend/app sin archivos .py"
    hallazgos: list[str] = []
    for ruta in archivos:
        hallazgos += _hallazgos_fuente(ruta, ruta.read_text(encoding="utf-8"))
    assert hallazgos == []


def test_RF_5_b_barrido_detecta_asignaciones_con_otro_literal() -> None:
    fuente = (
        "evento = AuditoriaEvento(resultado='OK')\n"
        "d = {'resultado': \"FALLO\"}\n"
        "ok = AuditoriaEvento(resultado='EXITO')\n"
    )
    hallazgos = _hallazgos_fuente(Path("x.py"), fuente)
    assert hallazgos == ["x.py: resultado = 'OK'", "x.py: resultado = 'FALLO'"]


# ── (c) Valores reales tras un flujo representativo vía API ─────────────


@pytest.mark.critical
async def test_RF_5_c_flujo_representativo_solo_emite_exito(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    # Catálogo (alta con categoría + modificación: triggers de auditoría).
    cat = await client_admin.post(
        "/api/v1/catalogo/categorias", json={"nombre": "Cat RF5"}
    )
    assert cat.status_code == 201, cat.text
    material = await crear_material(client, descripcion="Material RF5")
    resp = await client.patch(
        f"/api/v1/catalogo/{material['id_lista']}",
        json={"descripcion": "Material RF5 v2"},
    )
    assert resp.status_code == 200, resp.text
    mid = material["id_lista"]

    # Carga inicial, ajuste y TEAMS (transferencia) + DEVOL + cancelación.
    await carga_inicial(client, material_id=mid, cantidad=100)
    await ajustar_stock(client, almacen_id=1, material_id=mid, nuevo_stock=90)
    equipo = await crear_equipo(client, nombre="Equipo RF5")
    teams = await borrador_teams(
        client, almacen_id=1, equipo_id=equipo["equipo_id"],
        material_id=mid, cantidad=30,
    )
    await procesar(client, teams["id"])
    devol = await borrador_devol(
        client, equipo_id=equipo["equipo_id"], almacen_id=1,
        material_id=mid, cantidad=10,
    )
    await procesar(client, devol["id"])
    await cancelar(client, devol["id"], motivo="Guardián RF-5")

    # Seguimiento (apertura y cierre) e Inventario FO.
    seg = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos",
        json={"items": [{"material_id": mid, "cantidad_tomada": 5}]},
    )
    assert seg.status_code == 201, seg.text
    cierre = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos/"
        f"{seg.json()['id']}/cerrar",
        json={"consumidos": [{"material_id": mid, "cantidad_consumida": 2}]},
    )
    assert cierre.status_code == 200, cierre.text
    fo = await crear_material(client, descripcion="Cable FO RF5")
    await fibra_carga_inicial(client, material_id=fo["id_lista"], cantidad=10)
    await fibra_ajuste(client, material_id=fo["id_lista"], nuevo_stock=8)

    tipos = {
        r[0]
        for r in (
            await session.execute(
                text("SELECT DISTINCT tipo_accion FROM auditoria_eventos")
            )
        ).all()
    }
    # El flujo realmente produjo eventos de los distintos orígenes.
    assert len(tipos) >= 8, tipos
    valores = {
        r[0]
        for r in (
            await session.execute(
                text("SELECT DISTINCT resultado FROM auditoria_eventos")
            )
        ).all()
    }
    assert valores == {"EXITO"}
