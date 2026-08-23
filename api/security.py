from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import date

from .errors import ApiError


_DUMMY_HASH = "pbkdf2_sha256$240000$4d0d3ff1ec47b81a69f6d11ace955469$2a2ae47fb3c173e6a29a08fb9b2de69eb4ecf2d00c40d8d3aa379718fb8b1b43"
_MALAYSIAN_STATE_CODES = {
    "01", "21", "22", "23", "24", "02", "25", "26", "27", "03", "28", "29", "04", "30",
    "05", "31", "59", "06", "32", "33", "07", "34", "35", "08", "36", "37", "38", "39", "09",
    "40", "10", "41", "42", "43", "44", "11", "45", "46", "12", "47", "48", "49", "13", "50",
    "51", "52", "53", "14", "54", "55", "56", "57", "15", "58", "16", "82",
}


def normalize_ic(value: str) -> str:
    normalized = "".join(char for char in value if char.isdigit())
    if len(normalized) != 12:
        raise ApiError(422, "invalid_ic", "Enter a valid 12-digit Malaysian IC number.")
    yy, mm, dd, state = int(normalized[:2]), int(normalized[2:4]), int(normalized[4:6]), normalized[6:8]
    current_yy = date.today().year % 100
    year = 2000 + yy if yy <= current_yy else 1900 + yy
    try:
        date(year, mm, dd)
    except ValueError as exc:
        raise ApiError(422, "invalid_ic", "Enter a valid 12-digit Malaysian IC number.") from exc
    if state not in _MALAYSIAN_STATE_CODES:
        raise ApiError(422, "invalid_ic", "Enter a valid 12-digit Malaysian IC number.")
    return normalized


def mask_ic(value: str) -> str:
    return f"******-**-{value[-4:]}"


def display_mask_name(value: str) -> str:
    parts = value.split()
    if len(parts) == 1:
        return f"{parts[0][:2]}***"
    return f"{parts[0]} {parts[1][:1]}. ***"


def hash_secret(value: str, *, iterations: int = 240_000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_secret(value: str, encoded: str | None) -> bool:
    target = encoded or _DUMMY_HASH
    try:
        algorithm, iterations_raw, salt, expected = target.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", value.encode(), bytes.fromhex(salt), int(iterations_raw)
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def validate_password(value: str) -> None:
    if len(value) < 8 or not any(c.isupper() for c in value) or not any(c.islower() for c in value) or not any(c.isdigit() for c in value):
        raise ApiError(422, "weak_password", "Use at least 8 characters with uppercase, lowercase, and a number.")


def validate_pin(value: str, ic: str) -> None:
    if len(value) != 6 or not value.isdigit():
        raise ApiError(422, "invalid_pin", "Enter a six-digit PIN.")
    blocked = {digit * 6 for digit in "0123456789"} | {"123456", "654321", "121212", "123123"}
    yymmdd = ic[:6]
    ddmmyy = f"{ic[4:6]}{ic[2:4]}{ic[:2]}"
    if value in blocked or value in {yymmdd, ddmmyy}:
        raise ApiError(422, "pin_blocklisted", "Choose a less predictable six-digit PIN.")


def token_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
