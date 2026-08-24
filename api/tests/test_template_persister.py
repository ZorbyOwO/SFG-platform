"""Contract tests for the hosted template upload client (fail-closed)."""

from __future__ import annotations

import base64
import json

import pytest

from api.services.template_persister import SupabaseTemplatePersister, TemplatePersistError
from api.services.template_sealer import SealedTemplateBundle


URL = "https://oxpvsblgjrvfbrbaluxp.supabase.co"
SECRET = "sb_secret_test_only_never_real"
BUNDLE = SealedTemplateBundle(
    encrypted_payload=base64.b64encode(bytes(64)).decode("ascii"),
    nonce=base64.b64encode(bytes(12)).decode("ascii"),
    compatibility_fingerprint="a18bbbd47a57d14d",
    encryption_version="sfg-aesgcm-v1",
)


class FakeResponse:
    def __init__(self, status_code: int, body: object) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> object:
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeTransport:
    """Records requests and replays a scripted response."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, json: dict, headers: dict, timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return self.response


def _persister(transport: FakeTransport) -> SupabaseTemplatePersister:
    return SupabaseTemplatePersister(supabase_url=URL, backend_secret=SECRET, client=transport)


def _ok_transport() -> tuple[FakeTransport, str]:
    hosted_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    transport = FakeTransport(FakeResponse(200, [{"template_id": hosted_id}]))
    return transport, hosted_id


def test_success_posts_rpc_with_service_headers_and_returns_template_id():
    transport, hosted_id = _ok_transport()
    result = _persister(transport).persist(citizen_id="c-1", pose="front", bundle=BUNDLE)
    assert result == hosted_id
    call = transport.calls[0]
    assert call["url"].endswith("/rest/v1/rpc/sfg_backend_complete_reenrolment")
    headers = call["headers"]
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert headers["apikey"] == SECRET
    payload = call["json"]
    assert payload["p_citizen_id"] == "c-1"
    assert payload["p_encrypted_payload"] == BUNDLE.encrypted_payload
    assert payload["p_nonce"] == BUNDLE.nonce
    # The live CHECK constraint requires a JSON *object* here.
    assert isinstance(payload["p_compatibility_fingerprint"], dict)
    assert payload["p_encryption_version"] == "sfg-aesgcm-v1"


def test_persist_generation_sends_all_required_poses_in_one_rpc():
    hosted_ids = [
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1",
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2",
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee3",
    ]
    transport = FakeTransport(
        FakeResponse(200, [{"template_id": template_id} for template_id in hosted_ids])
    )
    result = _persister(transport).persist_generation(
        citizen_id="11111111-2222-3333-4444-555555555555",
        generation_id="66666666-7777-8888-9999-000000000000",
        bundles={"front": BUNDLE, "right": BUNDLE, "left": BUNDLE},
    )

    assert result == tuple(hosted_ids)
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"].endswith("/rest/v1/rpc/sfg_backend_replace_template_generation")
    payload = call["json"]
    assert payload["p_generation_id"] == "66666666-7777-8888-9999-000000000000"
    assert {row["capture_pose"] for row in payload["p_bundles"]} == {"front", "right", "left"}
    assert all(row["encrypted_payload"] == BUNDLE.encrypted_payload for row in payload["p_bundles"])


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failures_map_to_forbidden(status: int):
    persister = _persister(FakeTransport(FakeResponse(status, {"message": "no"})))
    with pytest.raises(TemplatePersistError) as excinfo:
        persister.persist(citizen_id="c-1", pose="front", bundle=BUNDLE)
    assert excinfo.value.code == "PERSIST_FORBIDDEN"


def test_missing_rpc_maps_to_config_error():
    persister = _persister(FakeTransport(FakeResponse(404, {"message": "not found"})))
    with pytest.raises(TemplatePersistError) as excinfo:
        persister.persist(citizen_id="c-1", pose="front", bundle=BUNDLE)
    assert excinfo.value.code == "PERSIST_RPC_MISSING"


@pytest.mark.parametrize("status", [500, 503])
def test_server_errors_map_to_refused(status: int):
    persister = _persister(FakeTransport(FakeResponse(status, {"message": "boom"})))
    with pytest.raises(TemplatePersistError) as excinfo:
        persister.persist(citizen_id="c-1", pose="front", bundle=BUNDLE)
    assert excinfo.value.code == "PERSIST_REFUSED"


def test_malformed_body_maps_to_malformed():
    persister = _persister(FakeTransport(FakeResponse(200, {"unexpected": True})))
    with pytest.raises(TemplatePersistError) as excinfo:
        persister.persist(citizen_id="c-1", pose="front", bundle=BUNDLE)
    assert excinfo.value.code == "PERSIST_MALFORMED_RESPONSE"


def test_unreachable_transport_fails_closed_without_leaking_details():
    class ExplodingTransport:
        def post(self, *args, **kwargs):
            raise OSError("getaddrinfo failed for some-internal-host")

    persister = SupabaseTemplatePersister(
        supabase_url=URL, backend_secret=SECRET, client=ExplodingTransport()
    )
    with pytest.raises(TemplatePersistError) as excinfo:
        persister.persist(citizen_id="c-1", pose="front", bundle=BUNDLE)
    assert excinfo.value.code == "PERSIST_UNREACHABLE"


def test_insecure_url_is_rejected_at_build_time():
    with pytest.raises(TemplatePersistError) as excinfo:
        SupabaseTemplatePersister(supabase_url="http://insecure.example.com", backend_secret=SECRET)
    assert excinfo.value.code == "PERSIST_INSECURE_URL"


def test_missing_configuration_is_refused_at_build_time():
    with pytest.raises(TemplatePersistError) as excinfo:
        SupabaseTemplatePersister(supabase_url="", backend_secret="")
    assert excinfo.value.code == "PERSIST_NOT_CONFIGURED"
