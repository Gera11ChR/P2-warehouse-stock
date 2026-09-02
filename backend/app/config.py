import os

from cryptography.fernet import Fernet

DATABASE_URL = os.environ.get(
    "P2_DATABASE_URL",
    "postgresql+psycopg://p2admin@127.0.0.1:5433/p2",
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
