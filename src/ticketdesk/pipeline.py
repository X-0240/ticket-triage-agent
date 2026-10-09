"""W1 纵切：取数 → 证据包（带 fact_id）→ 确定性桩判定 → 人工确认 → 审计。

边界（评审硬条件）：

1. **桩不读 gold**：`stub_decide` 只接事实，签名里没有任何 gold 参数；
2. **证据包只引用真实工具返回**：每条事实带 `fact_id`，判定与审计都按 fact_id 引用；
3. **人工确认记 before/after**：model_output / human_action / final_output /
   changed_fields / timestamp；
4. **审计区分"事实发生"与"系统记录"**：`occurred_at` 来自源数据，`recorded_at` 是系统写入时间。

W1 的桩只证明"系统能容纳一个被认为有歧义的 case"，**不判定它是否真的 Agent-needed**
（那属于 W2 discovery benchmark）。
"""

from datetime import datetime

from ticketdesk import tools


def _now():
    return datetime.now().replace(microsecond=0)


def _with_fact_ids(facts):
    """给工具返回的事实编号：fact_01…，后续判定与审计只引用编号。"""
    numbered = []
    for index, fact in enumerate(facts, start=1):
        item = dict(fact)
        item["fact_id"] = "fact_%02d" % index
        item["occurred_at"] = fact.get("timestamp")
        item["recorded_at"] = str(_now())
        numbered.append(item)
    return numbered


def build_evidence(ticket_id, session):
    """取数并组装证据包（只读工具，不写任何表）。"""
    ticket = tools.get_ticket(ticket_id, session)
    if not ticket["found"]:
        return {
            "ticket_id": ticket_id,
            "facts": [],
            "order_no": None,
            "evidence_incomplete": True,
            "note": ticket["error"],
        }
    body = next(
        (f["value"] for f in ticket["facts"] if f["field"] == "body"), ""
    )
    order_no = tools.extract_order_no(body)
    order = tools.get_order(order_no, session) if order_no else {"found": False}
    shipment = (
        tools.get_shipment(order_no, session) if order_no else {"facts": []}
    )
    facts = _with_fact_ids(
        ticket["facts"] + order.get("facts", []) + shipment.get("facts", [])
    )
    return {
        "ticket_id": ticket_id,
        "facts": facts,
        "order_no": order_no,
        "order_found": bool(order.get("found")),
        "shipment_found": bool(shipment.get("found")),
        "shipment_fact": next(
            (f for f in facts if f["field"] == "shipment_state"), None
        ),
        "evidence_incomplete": not bool(order.get("found")),
        "note": None if order.get("found") else "订单事实缺失",
    }


def stub_decide(evidence):
    """确定性桩判定：只看证据包，签名里没有 gold，也没有任何 gold 字段可读。

    判定规则（刻意写得笨，够用即可）：
    - 订单事实缺失 → 争议（无法唯一判定）；
    - 已支付未发货 → 履约组 / P1；
    - 正文出现"退款"且订单存在 → 多信号冲突（争议）；
    - 其余 → 咨询组 / P2。
    """
    facts = {item["field"]: item for item in evidence["facts"]}
    if not facts:
        return {
            "verdict": "EVIDENCE_INCOMPLETE",
            "queue": None,
            "priority": None,
            "ambiguous": True,
            "needs_human": True,
            "reason": "工单不存在或取不到事实",
            "cited_facts": [],
        }
    if evidence["evidence_incomplete"]:
        return {
            "verdict": "EVIDENCE_INCOMPLETE",
            "queue": None,
            "priority": None,
            "ambiguous": True,
            "needs_human": True,
            "reason": "订单事实缺失，不猜",
            "cited_facts": [
                item["fact_id"]
                for item in evidence["facts"]
                if item["field"] in ("body", "status")
            ],
        }
    body = facts.get("body", {}).get("value", "")
    status = facts.get("status", {}).get("value")
    if "退款" in body:
        return {
            "verdict": "AMBIGUOUS",
            "queue": None,
            "priority": None,
            "ambiguous": True,
            "needs_human": True,
            "reason": "正文诉求与订单事实指向不同队列，属争议",
            "cited_facts": [facts["body"]["fact_id"], facts["status"]["fact_id"]],
        }
    if status == "PAID":
        return {
            "verdict": "DECIDED",
            "queue": "履约组",
            "priority": "P1",
            "ambiguous": False,
            "needs_human": True,
            "reason": "订单已支付且无发货事实",
            "cited_facts": [facts["status"]["fact_id"]],
        }
    return {
        "verdict": "DECIDED",
        "queue": "咨询组",
        "priority": "P2",
        "ambiguous": False,
        "needs_human": True,
        "reason": "无匹配的处置条件，按一般咨询处理",
        "cited_facts": [facts["status"]["fact_id"]],
    }


def human_confirm(decision, human_action, final_queue=None):
    """人工确认：记 before/after（模型输出 / 人工动作 / 最终输出 / 变更字段 / 时间）。"""
    final = dict(decision)
    if final_queue:
        final["queue"] = final_queue
    changed = [
        field
        for field in ("queue", "priority")
        if final.get(field) != decision.get(field)
    ]
    return {
        "model_output": decision,
        "human_action": human_action,
        "final_output": final,
        "changed_fields": changed,
        "timestamp": str(_now()),
    }


def audit_events(evidence, decision, confirmation):
    """审计时间线：区分"事实发生"（occurred_at）与"系统记录"（recorded_at）。"""
    events = []
    for fact in evidence["facts"]:
        events.append(
            {
                "event_type": "FACT_OBSERVED",
                "fact_id": fact["fact_id"],
                "occurred_at": fact["occurred_at"],
                "recorded_at": fact["recorded_at"],
                "detail": "%s=%s" % (fact["field"], fact["value"]),
            }
        )
    events.append(
        {
            "event_type": "STUB_DECIDED",
            "fact_id": None,
            "occurred_at": None,
            "recorded_at": str(_now()),
            "detail": "%s / %s" % (decision["verdict"], decision["reason"]),
        }
    )
    events.append(
        {
            "event_type": "HUMAN_CONFIRMED",
            "fact_id": None,
            "occurred_at": None,
            "recorded_at": confirmation["timestamp"],
            "detail": "changed=%s" % confirmation["changed_fields"],
        }
    )
    return events
