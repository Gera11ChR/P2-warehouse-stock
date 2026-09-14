class BusinessRuleError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "BUSINESS_RULE_VIOLATION",
        coordinates: list[dict] | None = None,
        status_code: int = 422,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.coordinates = coordinates or []
        self.status_code = status_code

    def to_http_detail(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "coordinates": self.coordinates,
            }
        }


class AuthorizationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "AUTHORIZATION_FAILED",
        actor: str | None = None,
        required_scope: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.actor = actor
        self.required_scope = required_scope or []

    def to_http_detail(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "actor": self.actor,
                "required_scope": self.required_scope,
            }
        }


class MovimientoNotFoundError(Exception):
    def __init__(self, movimiento_id: int) -> None:
        super().__init__(f"Movimiento {movimiento_id} no encontrado")
        self.movimiento_id = movimiento_id

    def to_http_detail(self) -> dict:
        return {
            "error": {
                "code": "MOVIMIENTO_NOT_FOUND",
                "message": f"Movimiento {self.movimiento_id} no encontrado",
            }
        }


class MovimientoStateError(Exception):
    def __init__(self, movimiento_id: int, *, estado: str, operacion: str) -> None:
        super().__init__(
            f"Movimiento {movimiento_id} en estado {estado} no permite {operacion}"
        )
        self.movimiento_id = movimiento_id
        self.estado = estado
        self.operacion = operacion

    def to_http_detail(self) -> dict:
        return {
            "error": {
                "code": "MOVIMIENTO_STATE_CONFLICT",
                "message": (
                    f"Movimiento {self.movimiento_id} en estado {self.estado} "
                    f"no permite {self.operacion}"
                ),
                "estado": self.estado,
                "operacion": self.operacion,
            }
        }
