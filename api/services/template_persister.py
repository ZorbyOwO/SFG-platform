"""Upload sealed template bundles to the hosted private biometric store.

This is the approved trusted-tier-to-Supabase connection for the platform
child's enrolment persistence. It speaks PostgREST RPC with a server-side
service credential; the browser never sees this secret and the kiosk never
touches this path.

Fails closed: any non-2xx, timeout, or malformed response raises and leaves the
local encrypted store untouched. Responses are reduced to ``template_id``
before logging, so no payload material can reach a log line.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .template_sealer import ENCRYPTION_VERSION, SealedTemplateBundle


LOGGER = logging.getLogger(__name__)

LEGACY_RPC_PATH = "/rest/v1/rpc/sfg_backend_complete_reenrolment"
GENERATION_RPC_PATH = "/rest/v1/rpc/sfg_backend_replace_template_generation"
REQUEST_TIMEOUT_SECONDS = 10.0
REQUIRED_POSES = ("front", "right", "left")


class TemplatePersistError(RuntimeError):
    """Raised when the hosted store refuses or fails to record a bundle."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _rpc_payload(
    citizen_id: str, bundle: SealedTemplateBundle
) -> dict[str, str]:
    return {
        "p_citizen_id": citizen_id,
        "p_encrypted_payload": bundle.encrypted_payload,
        "p_nonce": bundle.nonce,
        "p_compatibility_fingerprint": {"fingerprint": bundle.compatibility_fingerprint},
        "p_encryption_version": ENCRYPTION_VERSION,
    }


class SupabaseTemplatePersister:
    """Record one sealed bundle per completed enrolment session."""

    def __init__(
        self,
        *,
        supabase_url: str,
        backend_secret: str,
        client: Any | None = None,
    ) -> None:
        if not supabase_url or not backend_secret:
            raise TemplatePersistError("PERSIST_NOT_CONFIGURED")
        base = supabase_url.rstrip("/")
        # Defense in depth: refuse to send the secret over plaintext transport.
        if not (base.startswith("https://") or base.rsplit(":", 1)[-1].strip("/") == "54321"):
            raise TemplatePersistError("PERSIST_INSECURE_URL")
        self._base_url = base
        self._secret = backend_secret
        self._client = client

    def _request(self, rpc_path: str, payload: dict[str, Any]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._secret}",
            "apikey": self._secret,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        sender = self._client or httpx
        return sender.post(
            f"{self._base_url}{rpc_path}",
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    def persist(
        self,
        *,
        citizen_id: str,
        pose: str,
        bundle: SealedTemplateBundle,
    ) -> str:
        """Upload one bundle; returns the hosted template id on success."""

        del pose  # bound inside the sealed AAD; the RPC contract has no pose field
        try:
            response = self._request(LEGACY_RPC_PATH, _rpc_payload(citizen_id, bundle))
        except Exception as exc:
            LOGGER.warning("biometric persist=unreachable detail=%s", type(exc).__name__)
            raise TemplatePersistError("PERSIST_UNREACHABLE") from None
        if response.status_code == 401 or response.status_code == 403:
            raise TemplatePersistError("PERSIST_FORBIDDEN")
        if response.status_code == 404:
            raise TemplatePersistError("PERSIST_RPC_MISSING")
        if response.status_code // 100 != 2:
            # Status only: response bodies may echo request fragments.
            LOGGER.warning("biometric persist=refused status=%s", response.status_code)
            raise TemplatePersistError("PERSIST_REFUSED")
        try:
            body = response.json()
        except Exception:
            raise TemplatePersistError("PERSIST_MALFORMED_RESPONSE") from None
        rows = body if isinstance(body, list) else [body]
        template_id = None
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("template_id"), str):
                template_id = row["template_id"]
                break
        if not template_id:
            raise TemplatePersistError("PERSIST_MALFORMED_RESPONSE")
        return template_id

    def persist_generation(
        self,
        *,
        citizen_id: str,
        generation_id: str,
        bundles: dict[str, SealedTemplateBundle],
    ) -> tuple[str, ...]:
        """Replace all required poses in one hosted database transaction."""

        if set(bundles) != set(REQUIRED_POSES):
            raise TemplatePersistError("PERSIST_INCOMPLETE_GENERATION")
        wire_bundles = [
            {
                "capture_pose": pose,
                "encrypted_payload": bundles[pose].encrypted_payload,
                "nonce": bundles[pose].nonce,
                "compatibility_fingerprint": {
                    "fingerprint": bundles[pose].compatibility_fingerprint
                },
                "encryption_version": ENCRYPTION_VERSION,
            }
            for pose in REQUIRED_POSES
        ]
        payload: dict[str, Any] = {
            "p_citizen_id": citizen_id,
            "p_generation_id": generation_id,
            "p_bundles": wire_bundles,
        }
        try:
            response = self._request(GENERATION_RPC_PATH, payload)
        except Exception as exc:
            LOGGER.warning("biometric persist=unreachable detail=%s", type(exc).__name__)
            raise TemplatePersistError("PERSIST_UNREACHABLE") from None
        if response.status_code in {401, 403}:
            raise TemplatePersistError("PERSIST_FORBIDDEN")
        if response.status_code == 404:
            raise TemplatePersistError("PERSIST_RPC_MISSING")
        if response.status_code // 100 != 2:
            LOGGER.warning("biometric persist=refused status=%s", response.status_code)
            raise TemplatePersistError("PERSIST_REFUSED")
        try:
            body = response.json()
        except Exception:
            raise TemplatePersistError("PERSIST_MALFORMED_RESPONSE") from None

        raw_ids: object
        if isinstance(body, dict) and isinstance(body.get("template_ids"), list):
            raw_ids = body["template_ids"]
        else:
            rows = body if isinstance(body, list) else [body]
            raw_ids = [
                row.get("template_id")
                for row in rows
                if isinstance(row, dict) and isinstance(row.get("template_id"), str)
            ]
        if not isinstance(raw_ids, list) or len(raw_ids) != len(REQUIRED_POSES):
            raise TemplatePersistError("PERSIST_MALFORMED_RESPONSE")
        template_ids = tuple(item for item in raw_ids if isinstance(item, str) and item)
        if len(template_ids) != len(REQUIRED_POSES) or len(set(template_ids)) != len(REQUIRED_POSES):
            raise TemplatePersistError("PERSIST_MALFORMED_RESPONSE")
        return template_ids


__all__ = ["SupabaseTemplatePersister", "TemplatePersistError"]
