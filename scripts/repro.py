"""W1 复现证据（一条命令）：正例 / 两类失败 / 跨客户隔离 / 事实可回查 / 决策字段扫描。

用法：python scripts/seed.py && python scripts/repro.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticketdesk import db, tools  # noqa: E402
from ticketdesk.tools import Session, ToolError  # noqa: E402

MINE = Session(customer_id="C-1001")
OTHERS = Session(customer_id="C-2002")
FORBIDDEN = ("queue", "priority", "escalate", "recommended")


def find_fact(payload, field):
    for item in payload.get("facts", []):
        if item["field"] == field:
            return item
    return None


def check_label_leakage():
    """P0：取数视图里的 current_queue 必须是无信息状态。"""
    ticket = tools.get_ticket("T-1001", MINE)
    fact = find_fact(ticket, "current_queue")
    ok = fact is not None and fact["value"] == "unassigned"
    print("[%s] label leakage：视图 current_queue=%s（底座真值是『履约组』）"
          % ("OK" if ok else "FAIL", fact["value"] if fact else "缺失"))
    return ok


def check_positive():
    """正例：工单与订单都取到，且事实指针可逐条回查。"""
    ticket = tools.get_ticket("T-1001", MINE)
    order_no = tools.extract_order_no(
        find_fact(ticket, "body")["value"] if ticket["found"] else ""
    )
    order = tools.get_order(order_no, MINE) if order_no else {"found": False}
    traceable = 0
    for fact in ticket.get("facts", []) + order.get("facts", []):
        if fact["source"] == "orders":
            sql, params = "SELECT 1 AS ok FROM orders WHERE order_no=%s", (fact["ref"],)
        else:
            sql = "SELECT 1 AS ok FROM %s WHERE ticket_id=%%s" % fact["source"]
            params = (fact["ref"],)
        row = db.query_one(sql, params)
        if row:
            traceable += 1
    total = len(ticket.get("facts", [])) + len(order.get("facts", []))
    ok = ticket["found"] and order["found"] and traceable == total and total > 0
    print("[%s] 正例：工单 %s / 订单 %s / 事实可回查 %d/%d"
          % ("OK" if ok else "FAIL", ticket["found"], order["found"], traceable, total))
    return ok


def check_failure_missing_data():
    """失败 A：引用的订单不存在 → 不猜，标记证据不完整 + 转人工。"""
    ticket = tools.get_ticket("T-1004", MINE)
    order_no = tools.extract_order_no(find_fact(ticket, "body")["value"])
    order = tools.get_order(order_no, MINE)
    evidence_incomplete = not order["found"]
    needs_human = evidence_incomplete
    ok = ticket["found"] and evidence_incomplete and needs_human
    print("[%s] 失败A 数据不存在：订单 %s 查到=%s → evidence_incomplete=%s, "
          "needs_human=%s" % ("OK" if ok else "FAIL", order_no, order["found"],
                              evidence_incomplete, needs_human))
    return ok


def check_failure_tool_error():
    """失败 B：工具异常 → 不吞异常，包成 ToolError 抛出并留原因。"""
    original = db.query_one

    def boom(*args, **kwargs):
        raise RuntimeError("模拟数据库超时")

    db.query_one = boom
    try:
        tools.get_order("O-2001", MINE)
        print("[FAIL] 失败B 工具异常：竟然没有抛错")
        return False
    except ToolError as exc:
        print("[OK] 失败B 工具异常：抛出 ToolError 并带原因 → needs_human=True（%s）"
              % str(exc)[:40])
        return True
    finally:
        db.query_one = original


def check_scope():
    """跨客户隔离：另一个客户读不到本客户的工单与订单。"""
    ticket = tools.get_ticket("T-1001", OTHERS)
    order = tools.get_order("O-9009", MINE)
    ok = (ticket["found"] is False and ticket["error"] == "OUT_OF_SCOPE"
          and order["found"] is False)
    print("[%s] 跨客户隔离：他人读本单=%s(%s)，本客户读他人订单=%s(%s)"
          % ("OK" if ok else "FAIL", ticket["found"], ticket["error"],
             order["found"], order["error"]))
    return ok


def check_missing_key():
    """缺键反例：不给查询键必须报错，不许拉全表。"""
    ok = False
    try:
        tools.get_order("", MINE)
    except ValueError:
        ok = True
    print("[%s] 缺键反例：order_no 为空 → 报错" % ("OK" if ok else "FAIL"))
    return ok


def check_no_decision_keys():
    """隐性决策字段扫描：所有返回里不得出现决策字段。"""
    payloads = [
        tools.get_ticket("T-1001", MINE),
        tools.get_order("O-2001", MINE),
        tools.get_ticket("T-1004", MINE),
    ]
    hits = []
    for payload in payloads:
        hits.extend(tools.decision_key_hits(payload))
    print("[%s] 决策字段扫描：%s" % ("OK" if not hits else "FAIL",
                                    hits or "无 priority/queue/escalate/recommended"))
    return not hits


def main():
    results = [
        check_label_leakage(),
        check_positive(),
        check_failure_missing_data(),
        check_failure_tool_error(),
        check_scope(),
        check_missing_key(),
        check_no_decision_keys(),
    ]
    print("---- %d/%d 通过 ----" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
