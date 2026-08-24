from __future__ import annotations

import json
from pathlib import Path


def test_contract_baseline_remains_exact_and_has_no_ocr_status_family() -> None:
    package_root = Path(__file__).resolve().parents[1]
    contract = json.loads((package_root / "config" / "contract-v1.2-baseline.json").read_text(encoding="utf-8"))

    assert contract["contract_version"] == "1.2"
    assert len(contract["shared_variables"]) == 22
    assert len(contract["statuses"]) == 32
    assert len(contract["canonical_config_names"]) == 18
    assert len(set(contract["shared_variables"])) == 22
    assert len(set(contract["statuses"])) == 32
    assert len(set(contract["canonical_config_names"])) == 18
    assert not any("OCR" in status for status in contract["statuses"])
    assert "PADDLEOCR_LANG" in contract["canonical_config_names"]
    assert "PADDLEOCR_MODEL_DIR" in contract["canonical_config_names"]


def test_ocr_local_fields_are_not_promoted_to_shared_variables() -> None:
    package_root = Path(__file__).resolve().parents[1]
    contract = json.loads((package_root / "config" / "contract-v1.2-baseline.json").read_text(encoding="utf-8"))

    assert "full_name" not in contract["shared_variables"]
    assert "ic" not in contract["shared_variables"]
    assert "requires_confirmation" not in contract["shared_variables"]
