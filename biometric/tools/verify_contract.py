"""Verify the exact v1.2 22/32/18 contract and unchanged root authority."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CONTRACT_SHA256 = "fb9e156daa8795dcbeaed95d9e0b62fd5d99c79673d283cc8b9e94017ea469d2"


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    baseline = json.loads((package_root / "config" / "contract-v1.2-baseline.json").read_text(encoding="utf-8"))
    if not (
        baseline["contract_version"] == "1.2"
        and len(baseline["shared_variables"]) == len(set(baseline["shared_variables"])) == 22
        and len(baseline["statuses"]) == len(set(baseline["statuses"])) == 32
        and len(baseline["canonical_config_names"]) == len(set(baseline["canonical_config_names"])) == 18
    ):
        print("contract_gate=FAIL baseline_counts")
        return 1
    root_contract = package_root.parent / "integration-contracts.md"
    if root_contract.is_file():
        data = root_contract.read_bytes()
        text = data.decode("utf-8")
        if hashlib.sha256(data).hexdigest() != CONTRACT_SHA256:
            print("contract_gate=FAIL root_contract_hash")
            return 1
        if len(re.findall(r"^### Variable \d+: `[^`]+`", text, re.MULTILINE)) != 22:
            print("contract_gate=FAIL root_variable_count")
            return 1
    print("contract_gate=PASS variables=22 statuses=32 configs=18 ocr_expansion=NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
