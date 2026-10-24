"""P1 report traces all 22 original gates without fabricating live acceptance."""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
REPORT=ROOT/"docs/reports/AGO_P1_22_TASK_CONSOLIDATED_EXECUTION.md"
LEDGER=ROOT/"docs/reports/AGO_P0_P1_P2_48_TASK_ACCEPTANCE.json"
IDS={19,21,22,23,26,48,58,60,61,87,119,123,125,126,127,128,
     135,138,139,140,152,154}


def test_all_original_22_p1_gates_traced_without_claiming_fake_live_completion():
    text=REPORT.read_text(encoding="utf-8")
    items=json.loads(LEDGER.read_text(encoding="utf-8"))["tasks"]
    current={task["id"]:task for task in items if task["priority"]=="P1"}
    assert set(current)==IDS
    reported={int(item) for item in re.findall(r"^[|] #([0-9]+) ",text,re.MULTILINE)}
    assert reported==IDS
    assert current[140]["completion_proved"] is False
    assert current[140]["owner_local_or_external_evidence_required"] is True
    assert "Cannot be certified in GitHub CI" in text
    assert "Do not mark P1 22/22" in text


def test_p1_operator_and_work_evidence_are_real_paths_with_no_cloud_startup():
    paths=[
        "apps/web/components/brain-3d-scene.jsx",
        "apps/backend/ago/company_ollama_chain.py",
        "apps/backend/ago/company_ollama_chain_queries.py",
        "scripts/ago_p1_local_inference_probe.py",
        "scripts/local_approved_agent_batch.py",
        "apps/backend/ago/company_chat.py",
    ]
    assert all((ROOT/name).is_file() for name in paths)
    report=REPORT.read_text(encoding="utf-8")
    for statement in ("no-replay","no model","founder","after-ID"):
        assert statement.lower() in report.lower()
