"""补实验输入的可追溯性（闭环）：快照 → 盲审包 → 用同一份输入重跑冻结规则。

背景：历史分桶读的是数据库内容，而库已被后续 seed 覆盖，**历史输入无法验证一致**。
因此本脚本从冻结的 spec_50.json 重建输入，并把这份重建结果**固化为唯一输入快照**；
盲审包与规则执行都只读快照，从源头消除"两套生成逻辑漂移"。

用法：python scripts/build_input_snapshot.py
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import discovery_pilot as dp  # noqa: E402
import generate_cases as gc  # noqa: E402

OUT = ROOT / "experiments" / "discovery"
FIXTURES = ROOT / "fixtures" / "discovery"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_case(spec_row):
    """按 spec 渲染一条输入（正文 + 规范化事实），并算逐条 hash。"""
    state = next(
        s for s in gc.STATES if s["state"] == spec_row["business_state"]
    )
    index = int(spec_row["case_id"].split("-")[1])
    ghost = state["order"] == "GHOST"
    reference = "O-9999" if ghost else "O-%04d" % (3000 + index)
    form = spec_row["surface_form_variant"]
    if form == "missing_context":
        body = state["intent"] + "，具体订单号我一时找不到了。"
    else:
        body = gc.FORMS[form].format(
            intent=state["intent"], order=reference, days=5
        )
    facts = {
        "order_found": bool(state["order"]) and not ghost,
        "order_status": None if ghost else state["order"],
        "shipment_found": bool(state["ship"]),
        "shipment_state": state["ship"],
    }
    canonical = json.dumps(
        {
            "case_id": spec_row["case_id"],
            "ticket_id": spec_row["ticket_id"],
            "decision_question": spec_row["decision_question"],
            "body": body,
            "facts": facts,
            "order_no": reference,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return {
        "case_id": spec_row["case_id"],
        "ticket_id": spec_row["ticket_id"],
        "decision_question": spec_row["decision_question"],
        "business_state": spec_row["business_state"],
        "surface_form_variant": form,
        "provenance": spec_row["provenance"],
        "scenario_type": spec_row["scenario_type"],
        "expected_queue": spec_row.get("expected_queue"),
        "expected_priority": spec_row.get("expected_priority"),
        "expected_handoff": spec_row.get("expected_handoff"),
        "body": body,
        "facts": facts,
        "order_no": reference,
        "input_sha256": sha(canonical),
    }


def bucket_with(snapshot_row, rules):
    """用快照输入跑冻结规则（与 DB 无关），返回分桶行。"""
    facts = {
        "body": snapshot_row["body"],
        "status": snapshot_row["facts"]["order_status"],
        "shipment_state": snapshot_row["facts"]["shipment_state"],
    }
    evidence = {
        "order_no": None if snapshot_row["order_no"] == "O-9999"
        else snapshot_row["order_no"],
        "order_found": snapshot_row["facts"]["order_found"],
        "shipment_found": snapshot_row["facts"]["shipment_found"],
    }
    candidates, undecidable, unexecutable = [], [], []
    for rule in rules:
        if rule.get("decision_type", "queue") != snapshot_row[
            "decision_question"
        ]:
            continue
        status, missing = dp.rule_status(rule)
        if status == "UNEXECUTABLE":
            unexecutable.append(rule["rule_id"])
            continue
        if not dp.evaluate(rule["rule_id"], facts, evidence):
            continue
        if rule["effect"] == "UNDECIDABLE":
            undecidable.append(rule["rule_id"])
        else:
            candidates.append((rule["rule_id"], rule["output"]))
    outputs = sorted({value for _, value in candidates})
    if not candidates and unexecutable:
        bucket = "unexecutable"
    elif not candidates:
        bucket = "zero_candidate"
    elif len(outputs) == 1:
        bucket = "unique"
    else:
        bucket = "multi_candidate"
    return {
        "case_id": snapshot_row["case_id"],
        "decision_question": snapshot_row["decision_question"],
        "bucket": bucket,
        "candidate_outputs": outputs,
        "hit_rules": [rid for rid, _ in candidates],
        "undecidable_rules": undecidable,
        "unexecutable_rules": unexecutable,
        "expected_queue": snapshot_row["expected_queue"],
        "expected_priority": snapshot_row["expected_priority"],
    }


def main():
    spec = json.loads((OUT / "spec_50.json").read_text(encoding="utf-8"))
    rules_doc = json.loads((FIXTURES / "rules_v1.json").read_text(encoding="utf-8"))
    rules = rules_doc["rules"] + rules_doc.get("priority_rules", [])

    snapshot = [render_case(row) for row in spec]
    dataset_hash = sha("".join(r["input_sha256"] for r in snapshot))
    (OUT / "inputs_50.json").write_text(
        json.dumps(
            {"kind": "discovery_input_snapshot", "dataset_sha256": dataset_hash,
             "cases": snapshot},
            ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    results = [bucket_with(row, rules) for row in snapshot]
    counts = {"unique": 0, "zero_candidate": 0, "multi_candidate": 0,
              "unexecutable": 0}
    for row in results:
        counts[row["bucket"]] += 1

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            cwd=str(ROOT), capture_output=True, text=True)
    rules_hash = sha((FIXTURES / "rules_v1.json").read_text(encoding="utf-8"))[:16]
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    record = {
        "kind": "discovery_benchmark_50_reproducible",
        "rules_version": rules_doc["version"],
        "rules_hash": rules_hash,
        "input_dataset_sha256": dataset_hash,
        "commit": commit.stdout.strip() or None,
        "counts": counts,
        "note": "输入来自 inputs_50.json（唯一来源）；旧的 benchmark50_*.json 缺少历史输入快照，"
                "其历史输入一致性无法验证，保留但不作为可复现记录。",
        "cases": [dict(s, **r) for s, r in zip(snapshot, results)],
    }
    (OUT / ("benchmark50_repro_%s.json" % stamp)).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print("输入快照：inputs_50.json ｜ 数据集 hash %s ｜ 逐条 hash %d 条"
          % (dataset_hash, len(snapshot)))
    print("规则 %s ｜ 规则 hash %s ｜ commit %s"
          % (rules_doc["version"], rules_hash, record["commit"] or "n/a"))
    print("重跑分桶：%s" % counts)
    print("可复现记录：benchmark50_repro_%s.json" % stamp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
