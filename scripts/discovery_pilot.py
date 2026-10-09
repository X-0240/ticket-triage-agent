"""W2 pilot：用规则表给 case 分桶（唯一 / 零命中 / 多候选），结果落盘。

冻结口径（2026-10-09）：

1. unique 且候选==期望 → workflow-resolvable；multi → Agent-needed candidate；
   zero → human-review candidate；
2. 三桶由执行器算，case 文件不得指定 bucket；
3. 规则 `required_facts` 不可满足 → UNEXECUTABLE，不参与分桶（W3 加工具后自动恢复）；
4. `effect=UNDECIDABLE` 单独计，不算候选；
5. **pilot 只验分桶机制，不计 Agent-needed 比例**；
6. 旧结果不覆盖，作废的在 experiments/discovery/README.md 里标 INVALIDATED。

用法：python scripts/discovery_pilot.py
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticketdesk import pipeline  # noqa: E402
from ticketdesk.tools import Session  # noqa: E402

FIXTURES = ROOT / "fixtures" / "discovery"
OUT_DIR = ROOT / "experiments" / "discovery"
SESSION = Session(customer_id="C-1001")

# W1 两个工具能拿到的事实（W3 加工具后这里再扩）
AVAILABLE_FACTS = {
    "subject", "body", "status", "sla_due_at", "current_queue",
    "amount", "created_at", "paid_at", "shipment",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def rule_status(rule):
    missing = set(rule["required_facts"]) - AVAILABLE_FACTS
    return ("UNEXECUTABLE", sorted(missing)) if missing else ("EXECUTABLE", [])


def evaluate(rule_id, facts, evidence):
    """单条规则是否命中（只对 EXECUTABLE 规则调用）。"""
    body = str(facts.get("body") or "")
    status = facts.get("status")
    if rule_id == "R-01":
        # 条件照旧（已支付且没有任何发货事实），只是现在这条事实取得到了
        return status == "PAID" and not evidence.get("shipment_found")
    if rule_id == "R-02":
        return "退款" in body
    if rule_id == "R-03":
        return "没人管" in body or "投诉" in body
    if rule_id == "R-04":
        # 已发货类事实现在真的取得到：看 shipment.state，不再只看订单状态
        return str(facts.get("shipment_state") or "") in (
            "SHIPPED",
            "DELAYED",
            "LOST",
        )
    if rule_id == "R-05":
        return not evidence["order_no"]
    if rule_id == "P-01":
        sla = facts.get("sla_due_at")
        if not sla:
            return False
        delta = datetime.strptime(str(sla), "%Y-%m-%d %H:%M:%S") - datetime.now()
        return delta.total_seconds() < 2 * 3600
    if rule_id == "P-02":
        return "退款" in body
    return False


def run_case(case, rules):
    question = case["decision_question"]
    rules = [r for r in rules if r.get("decision_type", "queue") == question]
    evidence = pipeline.build_evidence(case["ticket_id"], SESSION)
    facts = {item["field"]: item["value"] for item in evidence["facts"]}
    candidates, undecidable, unexecutable = [], [], []
    for rule in rules:
        status, missing = rule_status(rule)
        if status == "UNEXECUTABLE":
            unexecutable.append("%s(缺%s)" % (rule["rule_id"], ",".join(missing)))
            continue
        if not evaluate(rule["rule_id"], facts, evidence):
            continue
        if rule["effect"] == "UNDECIDABLE":
            undecidable.append(rule["rule_id"])
        else:
            candidates.append((rule["rule_id"], rule["output"]))
    outputs = sorted({value for _, value in candidates})
    # 四态：规则需要的事实当前不可达 → UNEXECUTABLE（不计入 discovery 分母）；
    # 事实齐全但无候选 → ZERO_CANDIDATE；唯一 → UNIQUE；多候选 → MULTI_CANDIDATE
    if not candidates and unexecutable:
        bucket = "unexecutable"
    elif not candidates:
        bucket = "zero_candidate"
    elif len(outputs) == 1:
        bucket = "unique"
    else:
        bucket = "multi_candidate"
    if bucket == "unique" and outputs[0] == case.get("expected_queue"):
        resolution = "workflow-resolvable"
    elif bucket == "multi_candidate":
        resolution = "agent-needed candidate"
    elif bucket == "unexecutable":
        resolution = "excluded: required_facts 不可达"
    else:
        resolution = "human-review candidate"
    if undecidable:
        resolution += "+undecidable"
    return {
        "case_id": case["case_id"],
        "ticket_id": case["ticket_id"],
        "decision_question": case["decision_question"],
        "bucket": bucket,
        "candidate_outputs": outputs,
        "resolution": resolution,
        "expected_queue": case.get("expected_queue"),
        "expected_handoff": case.get("expected_handoff"),
        "expected_priority": case.get("expected_priority"),
        "hit_rules": [rid for rid, _ in candidates],
        "undecidable_rules": undecidable,
        "unexecutable_rules": unexecutable,
    }


def main():
    rules_path = FIXTURES / "rules_v1.json"
    cases_path = FIXTURES / "cases_pilot.json"
    rules_doc = json.loads(rules_path.read_text(encoding="utf-8"))
    cases_doc = json.loads(cases_path.read_text(encoding="utf-8"))
    rules = rules_doc["rules"]

    print("规则表 %s（%d 条）｜ hash %s" % (
        rules_doc["version"], len(rules), digest(rules_path)))
    print("%-6s %-8s %-9s %-6s %-10s %-24s %s" % (
        "case", "ticket", "question", "bucket", "候选输出", "resolution",
        "规则"))
    rules = rules_doc["rules"] + rules_doc.get("priority_rules", [])
    rows, counts = [], {"unique": 0, "zero_candidate": 0, "multi_candidate": 0,
                        "unexecutable": 0}
    for case in cases_doc["cases"]:
        row = run_case(case, rules)
        rows.append(row)
        counts[row["bucket"]] += 1
        detail = "命中 " + (",".join(row["hit_rules"]) or "-")
        if row["undecidable_rules"]:
            detail += "｜无法判定 " + ",".join(row["undecidable_rules"])
        if row["unexecutable_rules"]:
            detail += "｜不可执行 " + ",".join(row["unexecutable_rules"])
        print("%-6s %-8s %-9s %-6s %-10s %-24s %s" % (
            row["case_id"], row["ticket_id"], row["decision_question"],
            row["bucket"], ",".join(row["candidate_outputs"]) or "-",
            row["resolution"], detail))

    print("---- pilot 分桶：UNIQUE %d / ZERO_CANDIDATE %d / MULTI_CANDIDATE %d "
          "/ UNEXECUTABLE %d ----" % (
              counts["unique"], counts["zero_candidate"],
              counts["multi_candidate"], counts["unexecutable"]))
    print("注：UNEXECUTABLE 不计入 discovery 分母；pilot 只验分桶机制，"
          "不计 Agent-needed 比例。")

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            cwd=str(ROOT), capture_output=True, text=True)
    result = {
        "kind": "discovery_pilot",
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
        "rules_version": rules_doc["version"],
        "rules_hash": digest(rules_path),
        "cases_version": cases_doc["version"],
        "cases_hash": digest(cases_path),
        "commit": commit.stdout.strip() or None,
        "available_facts": sorted(AVAILABLE_FACTS),
        "counts": counts,
        "rows": rows,
        "note": "pilot 只验分桶机制；v1-draft 结果已作废（见 experiments/discovery/README.md）",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = result["created_at"].replace(":", "")
    out = OUT_DIR / ("pilot_%s_%s.json" % (rules_doc["version"], stamp))
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("结果落盘：%s" % out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
