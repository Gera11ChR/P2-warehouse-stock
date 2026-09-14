"""Validación estricta de DTOs Pydantic V2 — unidad pura (sin BD).

Cubre la fiscalización @sec-ops de FASE 3: extra="forbid" en todas las
entradas e inmutabilidad absoluta de id_lista.
"""

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.ajuste import AjusteStockAlmacenRequest, CargaInicialRequest
from app.schemas.cancelacion import CancelarMovimientoRequest
from app.schemas.equipo import EquipoCreate, EquipoUpdate
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

    def test_unidad_invalida_rechazada(self) -> None:
        with pytest.raises(ValidationError):
            MaterialCreate(descripcion="X", u_m="LITRO")


class TestStockInicial:
    def test_stock_inicial_sin_seccion_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            MaterialCreate(descripcion="X", stock_inicial=10)

    def test_stock_inicial_con_seccion_aceptado(self) -> None:
        material = MaterialCreate(
            descripcion="X", stock_inicial=10, seccion_id=1
        )
        assert material.stock_inicial == 10

    def test_stock_inicial_negativo_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            MaterialCreate(
                descripcion="X", stock_inicial=-1, seccion_id=1
            )


class TestExtremosMovimiento:
    def test_teams_sin_destino_equipo_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            MovimientoBorradorCreate(
                tipo_movimiento="TEAMS",
                origen_almacen_id=1,
                detalle=[DetalleLine(material_id=1, cantidad=1)],
            )

    def test_devol_sin_origen_equipo_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            MovimientoBorradorCreate(
                tipo_movimiento="DEVOL",
                destino_almacen_id=1,
                detalle=[DetalleLine(material_id=1, cantidad=1)],
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
                    DetalleLine(material_id=1, cantidad=1),
                    DetalleLine(material_id=1, cantidad=2),
                ],
            )

    def test_cantidad_cero_o_negativa_rechazada(self) -> None:
        with pytest.raises(ValidationError):
            DetalleLine(material_id=1, cantidad=0)
        with pytest.raises(ValidationError):
            DetalleLine(material_id=1, cantidad=-5)

    def test_procesar_movimiento_id_no_positivo_rechazado(self) -> None:
        with pytest.raises(ValidationError):
            ProcesarRequest(movimiento_id=0)


class TestAjustes:
    def test_motivo_obligatorio_en_ajuste(self) -> None:
        with pytest.raises(ValidationError):
            AjusteStockAlmacenRequest(
                almacen_id=1, material_id=1, nuevo_stock=5, motivo=""
            )

    def test_carga_inicial_cantidad_negativa_rechazada(self) -> None:
        with pytest.raises(ValidationError):
            CargaInicialRequest(almacen_id=1, material_id=1, cantidad=-1)


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
