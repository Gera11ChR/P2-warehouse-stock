from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransferLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=50)
    quantity: int = Field(gt=0)


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_warehouse_id: str = Field(min_length=1, max_length=50)
    destination_warehouse_id: str = Field(min_length=1, max_length=50)
    lines: list[TransferLineCreate] = Field(min_length=1)


class ReceiveLinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: int = Field(gt=0)
    received_quantity: int = Field(ge=0)


class TransferLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_id: int
    sku: str
    dispatched_quantity: int
    received_quantity: int | None


class TransferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transfer_id: UUID
    idempotency_key: str
    status: str
    source_warehouse_id: str
    destination_warehouse_id: str
    requested_by: str
    approved_by: str | None
    created_at: datetime
    dispatched_at: datetime | None
    received_at: datetime | None
    lines: list[TransferLineOut]


class TransferListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transfers: list[TransferOut]


class MfaElevationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1, max_length=50)
    totp_code: str = Field(min_length=6, max_length=8, pattern=r"^\d+$")


class MfaElevationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    elevation_id: UUID
    action: str
    expires_at: datetime
