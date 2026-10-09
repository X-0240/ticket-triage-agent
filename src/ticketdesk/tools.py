"""两个只读取数工具（W1 冻结范围：只有 get_ticket 与 get_order）。

三条硬约束（评审点名的 P0）：

1. **只看 pre_triage_view**：既有处置队列在视图里已固定为 unassigned，工具不碰 ticket 表；
2. **模型不能决定客户范围**：customer_id 由 `Session` 注入，工具不接收该参数；
3. **返回事实指针，不返回结论**：字段只有 field/value/source/ref/timestamp，
   不含 queue / priority / escalate / recommended_* 之类决策字段。

工具异常不吞：包成 `ToolError` 抛出，由上层决定降级与留痕。
"""

import re
from dataclasses import dataclass
from datetime import datetime

from ticketdesk import config, db

# 决策字段黑名单：只扫**键名**，不扫取值。早期版本扫整段 repr，
# 把合法的 current_queue 字段名也判成越界，属于误报。
FORBIDDEN_KEYS = ("queue", "priority", "escalate", "recommended")
# 唯一例外：pre_triage_view 里被屏蔽成 unassigned 的那个字段名，它本身就是防泄漏证据
ALLOWED_KEYS = ("current_queue",)


class ToolError(Exception):
    """取数失败：带上工具名与原因，供上层记录并转人工。"""


@dataclass(frozen=True)
class Session:
    """一次会话：客户范围由系统注入，模型无法更改。"""

    customer_id: str


def _fact(field, value, ref, timestamp, source):
    """事实指针：一条证据必须能按 ref 回查。"""
    return {
        "field": field,
        "value": value,
        "source": source,
        "ref": ref,
        "timestamp": str(timestamp) if timestamp else None,
    }


def _assert_no_decision_keys(payload):
    """返回结构里出现决策字段就是越界。"""
    hits = decision_key_hits(payload)
    if hits:
        raise ToolError("TOOL_CONTRACT_VIOLATION: 返回里出现决策字段 " + str(hits))


def decision_key_hits(payload):
    """递归扫键名，返回命中的决策字段（空列表表示干净）。"""
    hits = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                name = str(key).lower()
                if name not in ALLOWED_KEYS and any(
                    flag in name for flag in FORBIDDEN_KEYS
                ):
                    hits.append(str(key))
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return hits


def get_ticket(ticket_id, session):
    """按工单号取工单（只读 pre_triage_view，服务端校验客户归属）。

    返回事实指针列表。工单不存在 → 明确返回 found=False（不猜、不编）。
    """
    if not ticket_id:
        raise ValueError("缺少查询键：ticket_id")
    try:
        row = db.query_one(
            "SELECT ticket_id,customer_id,channel,subject,body,created_at,"
            "sla_due_at,status,current_queue FROM %s WHERE ticket_id=%%s"
            % config.TICKET_VIEW,
            (ticket_id,),
        )
    except Exception as exc:  # noqa: BLE001 - 统一包成 ToolError，不静默吞
        raise ToolError("get_ticket 取数失败: " + str(exc)) from exc
    if not row:
        return {
            "tool": "get_ticket",
            "found": False,
            "ref": ticket_id,
            "facts": [],
            "error": "NOT_FOUND",
        }
    if row["customer_id"] != session.customer_id:
        # 跨客户：不返回内容，也不区分"不存在"与"不属于你"，避免探测
        return {
            "tool": "get_ticket",
            "found": False,
            "ref": ticket_id,
            "facts": [],
            "error": "OUT_OF_SCOPE",
        }
    facts = [
        _fact("subject", row["subject"], ticket_id, row["created_at"], "ticket"),
        _fact("body", row["body"], ticket_id, row["created_at"], "ticket"),
        _fact("status", row["status"], ticket_id, None, "ticket"),
        _fact("sla_due_at", row["sla_due_at"], ticket_id, None, "ticket"),
        _fact(
            "current_queue",
            row["current_queue"],
            ticket_id,
            None,
            "pre_triage_view",
        ),
    ]
    payload = {
        "tool": "get_ticket",
        "found": True,
        "ref": ticket_id,
        "facts": facts,
        "error": None,
    }
    _assert_no_decision_keys(payload)
    return payload


def extract_order_no(text):
    """从工单正文里取订单号（桩阶段用正则；W3 换成模型抽取）。"""
    match = re.search(r"O-\d{4,}", text or "")
    return match.group(0) if match else None


def get_order(order_no, session):
    """按订单号取订单（服务端强制 order.customer_id == session.customer_id）。

    不接收 customer_id 参数：模型无权决定访问哪个客户。
    """
    if not order_no:
        raise ValueError("缺少查询键：order_no")
    try:
        row = db.query_one(
            "SELECT order_no,customer_id,status,amount,created_at,paid_at "
            "FROM orders WHERE order_no=%s",
            (order_no,),
        )
    except Exception as exc:  # noqa: BLE001
        raise ToolError("get_order 取数失败: " + str(exc)) from exc
    if not row or row["customer_id"] != session.customer_id:
        return {
            "tool": "get_order",
            "found": False,
            "ref": order_no,
            "facts": [],
            "error": "NOT_FOUND_OR_OUT_OF_SCOPE",
        }
    facts = [
        _fact("status", row["status"], order_no, row["created_at"], "orders"),
        _fact("amount", float(row["amount"]), order_no, None, "orders"),
        _fact("created_at", row["created_at"], order_no, None, "orders"),
        _fact("paid_at", row["paid_at"], order_no, None, "orders"),
    ]
    payload = {
        "tool": "get_order",
        "found": True,
        "ref": order_no,
        "facts": facts,
        "error": None,
    }
    _assert_no_decision_keys(payload)
    return payload


def now():
    return datetime.now().replace(microsecond=0)


def get_shipment(order_no, session):
    """按订单号取发货事实（服务端校验客户归属，返回事实指针）。

    只补这一件工具：规则 R-01 的 `required_facts` 需要发货事实。
    发货表暂缺，因此订单未发货时返回 found=False（这本身就是"没有发货事实"）。
    """
    if not order_no:
        raise ValueError("缺少查询键：order_no")
    try:
        row = db.query_one(
            "SELECT s.order_no,s.state,s.carrier,s.tracking_no,s.shipped_at,"
            "o.customer_id FROM shipment s JOIN orders o ON o.order_no=s.order_no "
            "WHERE s.order_no=%s",
            (order_no,),
        )
    except Exception as exc:  # noqa: BLE001
        # 基础设施失败（表缺失/超时/连接断）不得降级成"业务上没有发货事实"
        raise ToolError("get_shipment 取数失败: " + str(exc)) from exc
    if not row or row["customer_id"] != session.customer_id:
        return {
            "tool": "get_shipment",
            "found": False,
            "ref": order_no,
            "facts": [],
            "error": "NO_SHIPMENT_FACT",
        }
    payload = {
        "tool": "get_shipment",
        "found": True,
        "ref": order_no,
        "facts": [
            _fact("shipment_state", row["state"], order_no,
                  row["shipped_at"], "shipment"),
            _fact("carrier", row["carrier"], order_no, None, "shipment"),
        ],
        "error": None,
    }
    _assert_no_decision_keys(payload)
    return payload
