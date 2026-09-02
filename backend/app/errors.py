class BusinessRuleError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "BUSINESS_RULE_VIOLATION",
        coordinates: list[dict] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.coordinates = coordinates or []

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


class TransferIdempotencyConflictError(Exception):
    def __init__(self, idempotency_key: str) -> None:
        super().__init__(f"Idempotency key {idempotency_key!r} is in use by another actor")
        self.idempotency_key = idempotency_key

    def to_http_detail(self) -> dict:
        return {
            "error": {
                "code": "IDEMPOTENCY_KEY_CONFLICT",
                "message": "Idempotency key is in use by another actor",
            }
        }


class TransferNotFoundError(Exception):
    def __init__(self, transfer_id) -> None:
        super().__init__(f"Transfer {transfer_id} not found")
        self.transfer_id = transfer_id

    def to_http_detail(self) -> dict:
        return {
            "error": {
                "code": "TRANSFER_NOT_FOUND",
                "message": f"Transfer {self.transfer_id} not found",
            }
        }


class TransferStateConflictError(Exception):
    def __init__(self, transfer_id, *, current_status: str, attempted: str) -> None:
        super().__init__(
            f"Transfer {transfer_id} in state {current_status} cannot transition via {attempted}"
        )
        self.transfer_id = transfer_id
        self.current_status = current_status
        self.attempted = attempted

    def to_http_detail(self) -> dict:
        return {
            "error": {
                "code": "TRANSFER_STATE_CONFLICT",
                "message": (
                    f"Transfer {self.transfer_id} in state {self.current_status} "
                    f"cannot transition via {self.attempted}"
                ),
                "current_status": self.current_status,
                "attempted_transition": self.attempted,
            }
        }
