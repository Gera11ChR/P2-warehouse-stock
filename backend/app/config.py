import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

from cryptography.fernet import Fernet

DATABASE_URL = os.environ.get(
    "P2_DATABASE_URL",
    "postgresql+psycopg://p2admin@127.0.0.1:5432/p2",
)

TRANSFER_APPROVAL_THRESHOLD = int(
    os.environ.get("P2_TRANSFER_APPROVAL_THRESHOLD", "100")
)

MFA_ENCRYPTION_KEY: str = (
    os.environ.get("P2_MFA_ENCRYPTION_KEY") or Fernet.generate_key().decode()
)

MFA_ELEVATION_TTL_SECONDS = int(
    os.environ.get("P2_MFA_ELEVATION_TTL_SECONDS", "300")
)
TOTP_MAX_ATTEMPTS = int(os.environ.get("P2_TOTP_MAX_ATTEMPTS", "5"))
TOTP_WINDOW_SECONDS = int(os.environ.get("P2_TOTP_WINDOW_SECONDS", "600"))
TOTP_LOCKOUT_SECONDS = int(os.environ.get("P2_TOTP_LOCKOUT_SECONDS", "900"))

# ── Zona de negocio de los reportes de actividades (F-13, plan D-2) ───────
REPORTES_TZ: str = os.environ.get("P2_REPORTES_TZ") or "America/Mexico_City"
# Validación al importar: una zona inválida impide que el servidor arranque
# (plan D-2/F-13; el filtro SQL y la FECHA del XLSX dependen de esta zona).
ZoneInfo(REPORTES_TZ)
