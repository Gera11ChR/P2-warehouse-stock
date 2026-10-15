"""Validación estricta de DTOs Pydantic V2 — unidad pura (sin BD).

Cubre la fiscalización @sec-ops de FASE 3: extra="forbid" en todas las
entradas e inmutabilidad absoluta de id_lista. Cambio 0027 (RF-2/RF-6/
RF-8): las cantidades son Decimal (hasta 3 dp, máximo 999 999 999.999),
`MaterialUpdate` acepta `valor_unitario` y los DTOs FO/operadores ya no
tienen campos de módulo.
"""

from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.ajuste import AjusteStockAlmacenRequest, CargaInicialRequest
from app.schemas.cancelacion import CancelarMovimientoRequest
from app.schemas.equipo import EquipoCreate, EquipoUpdate
from app.schemas.inventario import (
    FibraAjusteRequest,
    FibraCargaInicialRequest,
    FibraMaterialUpdateRequest,
)
from app.schemas.material import (
    SUPPORTED_UNITS,
    CategoriaCreate,
    MaterialCreate,
    MaterialUpdate,
)
from app.schemas.movimiento import (
    DetalleLine,
    MovimientoBorradorCreate,
    MovimientoBorradorUpdate,
    ProcesarRequest,
)
from app.schemas.operadores import MoverMaterialRequest, SumarCantidadRequest
from app.schemas.seguimiento import CerrarSeguimientoRequest, SeguimientoItemIn

SCHEMAS_ENTRADA: list[type[BaseModel]] = [
    CategoriaCreate,
    MaterialCreate,
    MaterialUpdate,
    DetalleLine,
    MovimientoBorradorCreate,
    MovimientoBorradorUpdate,
    ProcesarRequest,
    CargaInicialRequest,
    AjusteStockAlmacenRequest,
    CancelarMovimientoRequest,
    EquipoCreate,
    EquipoUpdate,
    FibraCargaInicialRequest,
    FibraAjusteRequest,
    FibraMaterialUpdateRequest,
    SumarCantidadRequest,
    MoverMaterialRequest,
    CerrarSeguimientoRequest,
    SeguimientoItemIn,
]


class TestExtraForbid:
    def test_material_create_rechaza_campo_legacy_tipo(self) -> None:
        with pytest.raises(ValidationError):
            MaterialCreate.model_validate(
                {"descripcion": "X", "tipo": "GENERAL"}
            )

    def test_material_create_rechaza_id_lista(self) -> None:
        with pytest.raises(ValidationError):
            MaterialCreate.model_validate(
                {"descripcion": "X", "id_lista": 5}
            )

    def test_material_update_rechaza_id_lista(self) -> None:
        with pytest.raises(ValidationError):
            MaterialUpdate.model_validate(
                {"descripcion": "X", "id_lista": 5}
            )

    def test_material_create_no_acepta_valor_unitario(self) -> None:
        """RF-3 (C-3): el alta de material NO recibe Valor Unitario — nace
        en 1.000 y se modifica después (extra_forbid)."""
        with pytest.raises(ValidationError):
            MaterialCreate.model_validate(
                {"descripcion": "X", "valor_unitario": 2.5}
            )

    def test_fibra_carga_inicial_rechaza_modulo(self) -> None:
        """RF-1: `modulo` es un campo prohibido en las operaciones de
        Inventario FO (extra_forbid → 422 sin efectos)."""
        with pytest.raises(ValidationError):
            FibraCargaInicialRequest.model_validate(
                {"modulo": "PAQUETE", "material_id": 1, "cantidad": 5}
            )
        with pytest.raises(ValidationError):
            FibraAjusteRequest.model_validate(
                {"modulo": "EN_USO", "material_id": 1, "nuevo_stock": 5}
            )

    def test_operadores_rechazan_campos_de_modulo(self) -> None:
        """RF-1: sumar-cantidad/mover sin campos de módulo (extra_forbid)."""
        with pytest.raises(ValidationError):
            SumarCantidadRequest.model_validate(
                {"destino": "FO", "modulo": "PAQUETE", "material_id": 1,
                 "cantidad": 1}
            )
        with pytest.raises(ValidationError):
            MoverMaterialRequest.model_validate(
                {"origen": "FO", "origen_modulo": "PAQUETE",
                 "destino": "GENERAL", "material_id": 1, "cantidad": 1}
            )

    def test_movimiento_borrador_rechaza_campo_desconocido(self) -> None:
        with pytest.raises(ValidationError):
            MovimientoBorradorCreate.model_validate(
                {
                    "tipo_movimiento": "TEAMS",
                    "origen_almacen_id": 1,
                    "destino_equipo_id": 1,
                    "detalle": [{"material_id": 1, "cantidad": 1}],
                    "estado": "CONFIRMADO",
                }
            )

    def test_procesar_request_rechaza_campo_desconocido(self) -> None:
        with pytest.raises(ValidationError):
            ProcesarRequest.model_validate(
                {"movimiento_id": 1, "estado": "X"}
            )


class TestSelectorDual:
    def test_categoria_id_y_nueva_categoria_juntos_rechazados(self) -> None:
        with pytest.raises(ValidationError):
            MaterialCreate(
                descripcion="X", categoria_id=1, nueva_categoria="Fibra"
            )

    def test_una_rama_aceptada(self) -> None:
        material = MaterialCreate(descripcion="X", categoria_id=1)
        assert material.categoria_id == 1
        material = MaterialCreate(descripcion="X", nueva_categoria="Fibra")
        assert material.nueva_categoria == "Fibra"


class TestUnidades:
    @pytest.mark.parametrize("u_m", SUPPORTED_UNITS)
    def test_unidades_soportadas_aceptadas(self, u_m: str) -> None:
        material = MaterialCreate(descripcion="X", u_m=u_m)
        assert material.u_m == u_m

    def test_unidad_arbitraria_aceptada_por_schema(self) -> None:
        # REQ-UM-001: el schema ya no valida contra el Enum estático
        # SUPPORTED_UNITS; la validación autoritativa es dinámica contra la
        # tabla `ums` en services/catalogo._validar_um (422 determinístico).
        material = MaterialCreate(descripcion="X", u_m="METRO CUADRADO")
        assert material.u_m == "METRO CUADRADO"


class TestStockInicial:
    def test_stock_inicial_sin_seccion_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            MaterialCreate(descripcion="X", stock_inicial=Decimal("10"))

    def test_stock_inicial_con_seccion_aceptado(self) -> None:
        material = MaterialCreate(
            descripcion="X", stock_inicial=Decimal("10"), seccion_id=1
        )
        assert material.stock_inicial == Decimal("10")

    def test_stock_inicial_negativo_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            MaterialCreate(
                descripcion="X", stock_inicial=Decimal("-1"), seccion_id=1
            )


class TestValorUnitario:
    """RF-2/RF-8: cotas decimales de `valor_unitario` (MaterialUpdate)."""

    def test_valor_con_3_decimales_aceptado(self) -> None:
        material = MaterialUpdate(valor_unitario=Decimal("12.345"))
        assert material.valor_unitario == Decimal("12.345")

    def test_valor_cero_aceptado(self) -> None:
        # E2: Valor Unitario 0 es permitido (CHECK >= 0).
        assert MaterialUpdate(valor_unitario=Decimal("0")).valor_unitario == 0

    @pytest.mark.parametrize("valor", [-1, "1.2345", 1000000000, "1e-4"])
    def test_valor_fuera_de_rango_rechazado(self, valor: object) -> None:
        """RF-2: negativo, sobre-precisión (>3 dp), desbordamiento
        (>999 999 999.999) y notación científica sobre-precisa → 422."""
        with pytest.raises(ValidationError):
            MaterialUpdate(valor_unitario=valor)  # type: ignore[arg-type]

    def test_valor_null_explicito_permitido_en_schema(self) -> None:
        """E15: `valor_unitario: null` es válido a nivel de schema (la capa
        de servicio lo trata como no-op; RF-8 lo exige sin error 500)."""
        material = MaterialUpdate(valor_unitario=None)
        assert material.valor_unitario is None


class TestExtremosMovimiento:
    def test_teams_sin_destino_equipo_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            MovimientoBorradorCreate(
                tipo_movimiento="TEAMS",
                origen_almacen_id=1,
                detalle=[DetalleLine(material_id=1, cantidad=Decimal("1"))],
            )

    def test_devol_sin_origen_equipo_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            MovimientoBorradorCreate(
                tipo_movimiento="DEVOL",
                destino_almacen_id=1,
                detalle=[DetalleLine(material_id=1, cantidad=Decimal("1"))],
            )

    def test_detalle_vacio_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            MovimientoBorradorCreate(
                tipo_movimiento="TEAMS",
                origen_almacen_id=1,
                destino_equipo_id=1,
                detalle=[],
            )

    def test_detalle_material_duplicado_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            MovimientoBorradorCreate(
                tipo_movimiento="TEAMS",
                origen_almacen_id=1,
                destino_equipo_id=1,
                detalle=[
                    DetalleLine(material_id=1, cantidad=Decimal("1")),
                    DetalleLine(material_id=1, cantidad=Decimal("2")),
                ],
            )

    def test_cantidad_cero_o_negativa_rechazada(self) -> None:
        with pytest.raises(ValidationError):
            DetalleLine(material_id=1, cantidad=Decimal("0"))
        with pytest.raises(ValidationError):
            DetalleLine(material_id=1, cantidad=Decimal("-5"))

    def test_cantidad_sobre_precisa_rechazada(self) -> None:
        """RF-6: cantidades con más de 3 decimales → 422 (sin redondeo)."""
        with pytest.raises(ValidationError):
            DetalleLine(material_id=1, cantidad=Decimal("1.0005"))

    def test_procesar_movimiento_id_no_positivo_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            ProcesarRequest(movimiento_id=0)


class TestAjustes:
    def test_motivo_opcional_en_ajuste(self) -> None:
        """REQ-ERG-005: AjusteStockAlmacenRequest acepta motivo ausente,
        null o vacío."""
        assert (
            AjusteStockAlmacenRequest(
                almacen_id=1, material_id=1, nuevo_stock=Decimal("5"), motivo=""
            ).motivo
            == ""
        )
        assert (
            AjusteStockAlmacenRequest(
                almacen_id=1, material_id=1, nuevo_stock=Decimal("5")
            ).motivo
            is None
        )

    def test_carga_inicial_cantidad_negativa_rechazada(self) -> None:
        with pytest.raises(ValidationError):
            CargaInicialRequest(
                almacen_id=1, material_id=1, cantidad=Decimal("-1")
            )


class TestMetaInvariantes:
    def test_todos_los_schemas_entrada_tienen_extra_forbid(self) -> None:
        for schema in SCHEMAS_ENTRADA:
            assert schema.model_config is not None, schema.__name__
            assert schema.model_config.get("extra") == "forbid", schema.__name__

    def test_id_lista_ausente_en_todo_schema_entrada(self) -> None:
        for schema in SCHEMAS_ENTRADA:
            assert "id_lista" not in schema.model_fields, schema.__name__

    def test_campo_tipo_ausente_en_schemas_de_material(self) -> None:
        assert "tipo" not in MaterialCreate.model_fields
        assert "tipo" not in MaterialUpdate.model_fields

    def test_modulo_ausente_en_dtos_del_dominio_vivo(self) -> None:
        """RF-1: ningún DTO de entrada del dominio vivo declara `modulo`."""
        for schema in SCHEMAS_ENTRADA:
            assert "modulo" not in schema.model_fields, schema.__name__
            assert "origen_modulo" not in schema.model_fields, schema.__name__
            assert "destino_modulo" not in schema.model_fields, schema.__name__
