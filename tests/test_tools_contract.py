"""两个只读工具的契约测试：正例 / 跨客户 / 缺键 / 无决策字段。"""

import pytest

from ticketdesk import tools
from ticketdesk.tools import Session, ToolError

MINE = Session(customer_id="C-1001")
OTHERS = Session(customer_id="C-2002")


def test_get_ticket_returns_facts():
    """正例：工单取到，且每条事实都带 ref（可回查）。"""
    payload = tools.get_ticket("T-1001", MINE)
    assert payload["found"] is True
    assert payload["facts"]
    assert all(item["ref"] for item in payload["facts"])


def test_get_ticket_masks_current_queue():
    """P0：取数视图把既有处置队列固定成 unassigned。"""
    payload = tools.get_ticket("T-1001", MINE)
    fact = next(f for f in payload["facts"] if f["field"] == "current_queue")
    assert fact["value"] == "unassigned"


def test_get_order_returns_facts():
    payload = tools.get_order("O-2001", MINE)
    assert payload["found"] is True
    assert {item["field"] for item in payload["facts"]} >= {"status", "amount"}


def test_cross_customer_is_blocked():
    """跨客户反例：读别人的工单/订单都取不到，且不泄露是否存在。"""
    ticket = tools.get_ticket("T-1001", OTHERS)
    order = tools.get_order("O-9009", MINE)
    assert ticket["found"] is False and ticket["error"] == "OUT_OF_SCOPE"
    assert order["found"] is False


def test_missing_key_raises():
    """缺键反例：不给查询键必须报错，不许拉全表。"""
    with pytest.raises(ValueError):
        tools.get_ticket("", MINE)
    with pytest.raises(ValueError):
        tools.get_order("", MINE)


def test_tool_error_is_not_swallowed(monkeypatch):
    """工具异常不被吞掉：包成 ToolError 抛出。"""

    def boom(*args, **kwargs):
        raise RuntimeError("模拟数据库超时")

    monkeypatch.setattr(tools.db, "query_one", boom)
    with pytest.raises(ToolError):
        tools.get_order("O-2001", MINE)


def test_no_decision_fields_in_returns():
    """返回里不得出现 queue / priority / escalate / recommended 等决策字段。"""
    payloads = [
        tools.get_ticket("T-1001", MINE),
        tools.get_order("O-2001", MINE),
        tools.get_ticket("T-1004", MINE),
    ]
    hits = []
    for payload in payloads:
        hits.extend(tools.decision_key_hits(payload))
    assert hits == []


def test_not_found_is_explicit():
    """数据不存在时明确返回 found=False，不猜。"""
    payload = tools.get_order("O-9999", MINE)
    assert payload["found"] is False
    assert payload["error"] == "NOT_FOUND_OR_OUT_OF_SCOPE"


def test_shipment_domain_absence_when_no_row():
    """域内缺席：查询成功但没有发货记录 → NO_SHIPMENT_FACT（业务事实为空）。

    O-2001 在种子里**故意不建 shipment 行**，代表"未产生发货事实"。
    """
    payload = tools.get_shipment("O-2001", MINE)
    assert payload["found"] is False
    assert payload["error"] == "NO_SHIPMENT_FACT"


def test_shipment_infrastructure_error_raises(monkeypatch):
    """基础设施错误：查询失败必须抛 ToolError，不得降级成"没有发货事实"。

    这两条是不同语义，早期版本共用一个降级值，会把数据库故障伪装成业务缺席。
    """

    def boom(*args, **kwargs):
        raise RuntimeError("模拟 schema 缺失")

    monkeypatch.setattr(tools.db, "query_one", boom)
    with pytest.raises(ToolError):
        tools.get_shipment("O-2002", MINE)
