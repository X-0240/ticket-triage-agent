"""生成 50 条 discovery benchmark：规格 → 业务世界 → 冻结规则分桶 → 六样结果。

规格 = 10 个业务状态 × 5 种表达变体（surface_form），共 50 条。
规格里**没有** bucket / agent_needed / dynamic_pattern 三个字段：
它们只能由执行结果产生（后置判定）。正文由 business_intent + surface_form 生成，
**不拿 expected_queue 当模板**，避免 gold 泄漏。

用法：python scripts/generate_cases.py
"""

import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from discovery_pilot import run_case  # noqa: E402
from ticketdesk import db  # noqa: E402
from ticketdesk.tools import Session  # noqa: E402

FIXTURES = ROOT / "fixtures" / "discovery"
OUT = ROOT / "experiments" / "discovery"
CUSTOMER = "C-1001"
SESSION = Session(customer_id=CUSTOMER)

# 业务状态：业务世界（order/shipment）+ gold + provenance（不写 bucket/agent_needed）
STATES = [
    dict(state="paid_no_shipment", dq="queue", order="PAID", ship=None,
         intent="已经付款好几天了，一直没发货", eq="履约组", eh="auto",
         prov="synthetic_with_basis#frappe/helpdesk#2658 自动分配/SLA",
         scen="shipment"),
    dict(state="shipped_delayed", dq="queue", order="SHIPPED", ship="DELAYED",
         intent="物流卡在中转站好几天没动静", eq="物流组", eh="auto",
         prov="synthetic_with_basis#物流异常形态", scen="shipment"),
    dict(state="shipped_normal", dq="queue", order="SHIPPED", ship="SHIPPED",
         intent="想确认一下包裹走到哪了", eq="物流组", eh="auto",
         prov="synthetic_with_basis#正常在途", scen="shipment"),
    dict(state="refund_requested", dq="queue", order="PAID", ship=None,
         intent="不想要了，希望退款", eq="售后组", eh="auto",
         prov="synthetic_with_basis#chatwoot#13543 退款诉求", scen="refund"),
    dict(state="no_order_context", dq="queue", order=None, ship=None,
         intent="我这个情况该怎么办", eq=None, eh="human_review",
         prov="issue_derived#frappe/helpdesk#2658", scen="none"),
    dict(state="multi_signal", dq="queue", order="SHIPPED", ship="DELAYED",
         intent="货没到还要退款，上次也没人处理", eq=None, eh="human_review",
         prov="issue_derived#frappe/helpdesk#3465 重开单与指标失真", scen="mixed"),
    dict(state="order_not_found", dq="queue", order="GHOST", ship=None,
         intent="帮我查一下那个订单", eq=None, eh="human_review",
         prov="synthetic_with_basis#数据不存在形态", scen="missing_data"),
    dict(state="delivered_policy_question", dq="queue", order="SHIPPED",
         ship="SHIPPED", intent="收到货了，想问下保修政策", eq=None,
         eh="human_review", prov="synthetic_with_basis#咨询形态",
         scen="policy"),
    dict(state="sla_soon", dq="priority", order="PAID", ship=None,
         intent="有点着急，麻烦尽快处理", ep="P0", eh="auto",
         prov="synthetic_with_basis#SLA 临近（benchmark policy）", scen="sla"),
    dict(state="refund_priority", dq="priority", order="PAID", ship=None,
         intent="希望尽快退款", ep="P1", eh="auto",
         prov="issue_derived#frappe/helpdesk#3465", scen="refund"),
]

# 5 种表达变体：同一业务状态换说法，防"测的是模板识别"
FORMS = {
    "direct": "{intent}，订单号 {order}。",
    "complaint": "{intent}，这已经是第二次了，实在受不了，订单号 {order}。",
    "timeline": "{days} 天前下的单，中间一直没消息，现在{intent}，订单号 {order}。",
    "rhetorical": "订单 {order} 到底要拖多久？{intent}，你们到底管不管？",
    "missing_context": "{intent}，具体订单号我一时找不到了。",
}


def _stamp(**kwargs):
    return datetime.now().replace(microsecond=0) - timedelta(**kwargs)


def _ticket_id(index):
    return "T-%04d" % (2000 + index)


def _order_no(index):
    return "O-%04d" % (3000 + index)


def build_spec():
    """规格表：50 行，只含允许字段。"""
    spec = []
    index = 0
    for state in STATES:
        for form in FORMS:
            index += 1
            row = {
                "case_id": "D-%02d" % index,
                "ticket_id": _ticket_id(index),
                "decision_question": state["dq"],
                "provenance": state["prov"],
                "business_state": state["state"],
                "business_intent": state["intent"],
                "surface_form_variant": form,
                "scenario_type": state["scen"],
                "expected_handoff": state["eh"],
            }
            if state["dq"] == "queue":
                row["expected_queue"] = state["eq"]
            else:
                row["expected_priority"] = state["ep"]
                row["expected_queue"] = None
            spec.append(row)
    return spec


def materialize(spec):
    """按规格造业务世界（订单 / 发货 / 工单），订单号与工单号与规格一一对应。"""
    by_state = {s["state"]: s for s in STATES}
    now = datetime.now().replace(microsecond=0)
    with db.tx() as cur:
        cur.execute("DELETE FROM ticket")
        cur.execute("DELETE FROM shipment")
        cur.execute("DELETE FROM orders")
        for row in spec:
            state = by_state[row["business_state"]]
            index = int(row["case_id"].split("-")[1])
            order_no = _order_no(index)
            ghost = state["order"] == "GHOST"
            if not ghost and state["order"]:
                status = state["order"]
                cur.execute(
                    "INSERT INTO orders (order_no,customer_id,status,amount,"
                    "created_at,paid_at) VALUES (%s,%s,%s,%s,%s,%s)",
                    (order_no, CUSTOMER, status, 199.00, _stamp(days=8),
                     _stamp(days=8) if status != "CREATED" else None),
                )
                if state["ship"]:
                    exception = 1 if state["ship"] == "DELAYED" else 0
                    cur.execute(
                        "INSERT INTO shipment (order_no,state,carrier,"
                        "tracking_no,exception_flag,shipped_at,last_event_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (order_no, state["ship"], "SF", "SF%04d" % index,
                         exception, _stamp(days=6), _stamp(hours=6)),
                    )
            reference = _order_no(index) if not ghost else "O-9999"
            body = FORMS[row["surface_form_variant"]].format(
                intent=state["intent"], order=reference, days=5
            )
            if row["surface_form_variant"] == "missing_context":
                body = state["intent"] + "，具体订单号我一时找不到了。"
            sla_hours = 1 if state["state"] == "sla_soon" else 6
            cur.execute(
                "INSERT INTO ticket (ticket_id,customer_id,channel,subject,body,"
                "created_at,sla_due_at,status,current_queue) "
                "VALUES (%s,%s,'email',%s,%s,%s,%s,'OPEN',%s)",
                (row["ticket_id"], CUSTOMER, state["intent"][:20], body,
                 _stamp(hours=3), now + timedelta(hours=sla_hours), "待分诊"),
            )
    return len(spec)


def leak_check(rows, spec):
    """防泄漏自检：提示词是否只集中在某一个 gold 类里。"""
    markers = ["退款", "赔付", "物流异常", "投诉", "没人管"]
    golds = {}
    for row in spec:
        key = row.get("expected_queue") or row.get("expected_priority") or "-"
        golds.setdefault(key, []).append(row["case_id"])
    report = []
    for marker in markers:
        hit_golds = {key for key, ids in golds.items()
                     if any(marker in r_body for r_body in
                            [row_body(j, spec) for j in ids])}
        report.append({"marker": marker, "gold_classes": sorted(hit_golds)})
    return report


def row_body(case_id, spec):
    import re
    row = next(r for r in spec if r["case_id"] == case_id)
    state = next(s for s in STATES if s["state"] == row["business_state"])
    index = int(case_id.split("-")[1])
    reference = _order_no(index) if state["order"] != "GHOST" else "O-9999"
    if row["surface_form_variant"] == "missing_context":
        return state["intent"] + "，具体订单号我一时找不到了。"
    return FORMS[row["surface_form_variant"]].format(
        intent=state["intent"], order=reference, days=5
    )


def main():
    rules_doc = json.loads(
        (FIXTURES / "rules_v1.json").read_text(encoding="utf-8")
    )
    rules = rules_doc["rules"] + rules_doc.get("priority_rules", [])
    spec = build_spec()
    count = materialize(spec)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "spec_50.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = [run_case(row, rules) for row in spec]
    counts = {"unique": 0, "zero_candidate": 0, "multi_candidate": 0,
              "unexecutable": 0}
    for row in rows:
        counts[row["bucket"]] += 1
    prov = {}
    for row in spec:
        key = row["provenance"].split("#")[0]
        prov[key] = prov.get(key, 0) + 1
    patterns = {}
    for row, result in zip(spec, rows):
        if result["bucket"] in ("multi_candidate", "unique"):
            patterns[row["scenario_type"]] = patterns.get(
                row["scenario_type"], 0) + 1

    print("规则表 %s ｜ hash %s" % (
        rules_doc["version"],
        hashlib.sha256((FIXTURES / "rules_v1.json").read_bytes())
        .hexdigest()[:16]))
    print("生成 case：%d 条（%d 状态 × %d 表达）" % (count, len(STATES), len(FORMS)))
    print("provenance 分布：%s" % prov)
    print("三桶：%s" % counts)
    print("动态取数模式（按 scenario_type 分层，**待复核**，不作为结论）：%s" % patterns)
    print("Agent-needed 待复核候选：")
    for row, result in zip(spec, rows):
        if result["bucket"] == "multi_candidate":
            print("   %s | %s | %s | gold=%s | 命中 %s" % (
                row["case_id"], row["business_state"],
                row["business_intent"][:18],
                row.get("expected_queue") or row.get("expected_priority"),
                ",".join(result["hit_rules"])))
    print("防泄漏自检：%s" % leak_check(rows, spec))
    out = OUT / ("benchmark50_%s.json" % datetime.now().strftime("%Y%m%dT%H%M%S"))
    out.write_text(json.dumps({
        "kind": "discovery_benchmark_50", "rules_version": rules_doc["version"],
        "counts": counts, "provenance": prov, "patterns_pending_review": patterns,
        "cases": [dict(s, **r) for s, r in zip(spec, rows)],
        "note": "agent_needed 未判定：第②条判据必须人判；外部复核未发生。",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("结果落盘：%s" % out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
