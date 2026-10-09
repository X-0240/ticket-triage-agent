"""生成盲审包：**覆盖全部 50 条**，不给 gold、不给我们的判断、不分组。

为什么要全量：冻结判据第①条还包括"规则给出唯一候选，但与正文语义冲突"，
所以 28 条 UNIQUE 不能直接排除。按 case_id 排序混排，避免暴露我们怀疑哪些。

用法：python scripts/make_review_packet.py <benchmark50_*.json>
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_cases  # noqa: E402

FIXTURES = ROOT / "fixtures" / "discovery"

HEADER = [
    "# 工单分诊 benchmark·盲审包（v1，全 50 条）",
    "",
    "请对每条 case 独立判断，**不要参考任何人的先前判断**；你看到的是原始材料。",
    "每条按末尾模板回答六项：criterion_1_met / criterion_2_met / criterion_3_met / "
    "agent_needed / required_next_lookup / reason。",
    "",
    "三条判据（冻结口径）：",
    "1. 固定取数 + 结构化规则之后仍给不出唯一结论，**或规则给出唯一候选但与正文语义冲突**；",
    "2. **必须根据工单正文语义决定下一步查什么**；",
    "3. 该形态在真实场景存在（见每条附的 provenance，可核查）。",
    "",
    "两条提醒：",
    "- **0 候选（zero_candidate）也可能是 agent_needed**，只要同时满足 ②③；",
    "- 但**因工具/事实缺失造成的**零命中不算——本包已把这类（UNEXECUTABLE）排除。",
    "",
]

ANSWER_TEMPLATE = [
    "```",
    "criterion_1_met: true/false",
    "criterion_2_met: true/false",
    "criterion_3_met: true/false",
    "agent_needed: true/false",
    "required_next_lookup: <还需查什么，或 none>",
    "reason: <一句话>",
    "```",
]


def load_required_facts():
    doc = json.loads((FIXTURES / "rules_v1.json").read_text(encoding="utf-8"))
    rules = doc["rules"] + doc.get("priority_rules", [])
    return {rule["rule_id"]: rule.get("required_facts", []) for rule in rules}


def derive(case_row):
    """离线重算原始材料：正文由 business_intent + surface_form 生成，事实取自业务状态。

    **不读数据库**：这样盲审包可离线复现（MySQL 未启动也能出包），
    且正文与 case 生成时用的是同一套模板，不会出现两份真相。
    """
    state = next(
        s for s in generate_cases.STATES
        if s["state"] == case_row["business_state"]
    )
    index = int(case_row["case_id"].split("-")[1])
    ghost = state["order"] == "GHOST"
    reference = "O-9999" if ghost else "O-%04d" % (3000 + index)
    if case_row["surface_form_variant"] == "missing_context":
        body = state["intent"] + "，具体订单号我一时找不到了。"
    else:
        body = generate_cases.FORMS[case_row["surface_form_variant"]].format(
            intent=state["intent"], order=reference, days=5
        )
    facts = []
    if not ghost and state["order"]:
        facts.append("order.status=%s" % state["order"])
    else:
        facts.append("order=（查不到该订单）")
    if state["ship"]:
        flag = 1 if state["ship"] == "DELAYED" else 0
        facts.append("shipment.state=%s" % state["ship"])
        facts.append("shipment.exception_flag=%d" % flag)
    else:
        facts.append("shipment=（无发货记录）")
    return body, facts


def main():
    if len(sys.argv) < 2:
        raise SystemExit(
            "用法：python scripts/make_review_packet.py <benchmark50_*.json>"
        )
    src = Path(sys.argv[1])
    data = json.loads(src.read_text(encoding="utf-8"))
    required_map = load_required_facts()
    rows = sorted(data["cases"], key=lambda row: row["case_id"])

    lines = list(HEADER)
    lines.append("cases：%d 条（含 unique / zero_candidate / multi_candidate，随机顺序即按 id）"
                 % len(rows))
    lines.append("")
    for row in rows:
        body, facts = derive(row)
        required = [f for rid in row["hit_rules"]
                    for f in required_map.get(rid, [])]
        lines.append("### %s（%s）" % (row["case_id"], row["decision_question"]))
        lines.append("")
        lines.append("- provenance：%s" % row["provenance"])
        lines.append("- scenario_type：%s" % row["scenario_type"])
        lines.append("- 工单正文：%s" % body)
        lines.append("- baseline 事实：%s" % ("；".join(facts) or "(无)"))
        lines.append("- 判定问题：%s" % row["decision_question"])
        lines.append("- 候选结果：%s（命中规则 %s）"
                     % (row["candidate_outputs"] or "无候选",
                        ",".join(row["hit_rules"]) or "无"))
        lines.append("- 可用事实：order.status/amount、shipment.state/exception_flag、"
                     "ticket.body/sla_due_at")
        lines.append("- 命中规则所需事实：%s" % (sorted(set(required)) or "无"))
        lines.append("- 当前分桶：%s" % row["bucket"])
        lines.append("")
        lines.extend(ANSWER_TEMPLATE)
        lines.append("")

    out = src.with_name("review_packet_v1.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    print("盲审包已生成：%s（%d 条）" % (out.relative_to(ROOT), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
