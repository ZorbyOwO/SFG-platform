from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _load_local_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    api_base_url: str
    public_app_url: str
    cors_allowed_origins: tuple[str, ...]
    log_level: str
    database_url: str | None
    yunet_model_path: str | None
    sface_model_path: str | None
    pad_model_dir: str | None
    sface_match_threshold: Decimal
    sface_ambiguity_margin: Decimal
    pad_accept_threshold: Decimal
    pad_reject_threshold: Decimal
    biometric_template_encryption_key: str | None
    pin_max_attempts: int
    session_timeout_seconds: int
    paddleocr_lang: str
    paddleocr_model_dir: str | None
    face_only_mode: bool
    max_identify_frames: int
    max_upload_bytes: int
    transfer_min_amount: Decimal
    transfer_max_amount: Decimal
    max_family_members: int
    enrol_frames_required: int
    enrol_required_positions: tuple[str, ...]
    kiosk_key_file: Path
    corecv_root: Path
    biometric_key_file: Path
    biometric_template_db: Path
    enrol_session_timeout_seconds: int
    supabase_url: str | None
    supabase_publishable_key: str | None
    supabase_backend_secret: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        _load_local_env()
        allowed = tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ALLOWED_ORIGINS",
                "http://localhost:5500,http://127.0.0.1:5500,http://localhost:5501,http://127.0.0.1:5501",
            ).split(",")
            if origin.strip()
        )
        if "*" in allowed:
            raise ValueError("CORS_ALLOWED_ORIGINS must be an explicit allowlist")
        pin_attempts = int(os.getenv("PIN_MAX_ATTEMPTS", "3"))
        timeout = int(os.getenv("SESSION_TIMEOUT_SECONDS", "90"))
        if pin_attempts < 1 or timeout < 15:
            raise ValueError("PIN/session policy values are outside safe development bounds")
        positions = tuple(
            item.strip().lower()
            for item in os.getenv("ENROL_REQUIRED_POSITIONS", "front,right,left").split(",")
            if item.strip()
        )
        if not positions:
            raise ValueError("ENROL_REQUIRED_POSITIONS cannot be empty")
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
            public_app_url=os.getenv("PUBLIC_APP_URL", "http://localhost:5500"),
            cors_allowed_origins=allowed,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            database_url=os.getenv("DATABASE_URL") or None,
            yunet_model_path=os.getenv("YUNET_MODEL_PATH") or None,
            sface_model_path=os.getenv("SFACE_MODEL_PATH") or None,
            pad_model_dir=os.getenv("PAD_MODEL_DIR") or None,
            sface_match_threshold=Decimal(os.getenv("SFACE_MATCH_THRESHOLD", "0.40")),
            sface_ambiguity_margin=Decimal(os.getenv("SFACE_AMBIGUITY_MARGIN", "0.05")),
            pad_accept_threshold=Decimal(os.getenv("PAD_ACCEPT_THRESHOLD", "0.70")),
            pad_reject_threshold=Decimal(os.getenv("PAD_REJECT_THRESHOLD", "0.30")),
            biometric_template_encryption_key=os.getenv("BIOMETRIC_TEMPLATE_ENCRYPTION_KEY") or None,
            pin_max_attempts=pin_attempts,
            session_timeout_seconds=timeout,
            paddleocr_lang=os.getenv("PADDLEOCR_LANG", "en"),
            paddleocr_model_dir=os.getenv("PADDLEOCR_MODEL_DIR") or None,
            face_only_mode=_boolean("FACE_ONLY_MODE", False),
            max_identify_frames=int(os.getenv("MAX_IDENTIFY_FRAMES", "10")),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", "5242880")),
            transfer_min_amount=Decimal(os.getenv("TRANSFER_MIN_AMOUNT", "1.00")),
            transfer_max_amount=Decimal(os.getenv("TRANSFER_MAX_AMOUNT", "1000.00")),
            max_family_members=int(os.getenv("MAX_FAMILY_MEMBERS", "10")),
            enrol_frames_required=int(os.getenv("ENROL_FRAMES_REQUIRED", "3")),
            enrol_required_positions=positions,
            kiosk_key_file=ROOT / ".runtime" / "kiosk.key",
            corecv_root=Path(os.getenv("CORECV_ROOT") or (ROOT.parent / "biometric")),
            biometric_key_file=ROOT / ".runtime" / "biometric-template.key",
            biometric_template_db=Path(
                os.getenv("BIOMETRIC_TEMPLATE_DB") or (ROOT / ".runtime" / "biometric" / "templates.sqlite3")
            ),
            enrol_session_timeout_seconds=int(os.getenv("ENROL_SESSION_TIMEOUT_SECONDS", "900")),
            supabase_url=os.getenv("SUPABASE_URL") or None,
            supabase_publishable_key=os.getenv("SUPABASE_PUBLISHABLE_KEY") or None,
            supabase_backend_secret=os.getenv("SUPABASE_BACKEND_SECRET") or None,
        )
