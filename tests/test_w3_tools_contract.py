"""W3 四组工具的契约测试：正例 + 反例 + 统一契约。

安全约束（评审要求）：
- 夹具只插入**测试专用前缀**的数据（C-TEST / T-TEST- / O-TEST- / KB-TEST- / RF-TEST-），
  结束后按这些键精确删除，**不整表清空、不触碰 W2 冻结数据**；
- 查询异常的用例用 monkeypatch 模拟 DB 失败，**不靠删表制造异常**。
"""

from datetime import datetime, timedelta

import pytest

from ticketdesk import db, tools
from ticketdesk.tools import Session, ToolError

ME = Session(customer_id="C-TEST")
OTHER = Session(customer_id="C-TEST-OTHER")
FUTURE_SENTINEL = "FUTURE_SENTINEL"


@pytest.fixture(scope="module", autouse=True)
def fixture_data():
    now = datetime.now().replace(microsecond=0)
    try:
        with db.tx() as cur:
            cur.execute(
                "INSERT INTO orders (order_no,customer_id,status,amount,"
                "created_at,paid_at) VALUES (%s,%s,%s,%s,%s,%s)",
                ("O-TEST-1", "C-TEST", "PAID", 100.00, now - timedelta(days=9),
                 now - timedelta(days=9)),
            )
            cur.execute(
                "INSERT INTO orders (order_no,customer_id,status,amount,"
                "created_at,paid_at) VALUES (%s,%s,%s,%s,%s,%s)",
                ("O-TEST-FOREIGN", "C-TEST-OTHER", "PAID", 50.00,
                 now - timedelta(days=2), now - timedelta(days=2)),
            )
            cur.execute(
                "INSERT INTO order_line (order_no,sku_code,sku_name,qty,"
                "unit_price) VALUES (%s,%s,%s,%s,%s)",
                ("O-TEST-1", "SKU-TEST", "测试商品", 2, 50.00),
            )
            cur.execute(
                "INSERT INTO refund (refund_no,order_no,amount,state,reason,"
                "created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                ("RF-TEST-1", "O-TEST-1", 100.00, "APPLIED", "不想要了",
                 now - timedelta(days=1)),
            )
            cur.execute(
                "INSERT INTO kb_article (kb_id,title,body,policy_type,version,"
                "status,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ("KB-TEST-PUB", "退款政策", "七天无理由退款，需商品完好。",
                 "refund", "v3", "PUBLISHED", now - timedelta(days=3)),
            )
            cur.execute(
                "INSERT INTO kb_article (kb_id,title,body,policy_type,version,"
                "status,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ("KB-TEST-RET", "已废止的退款政策",
                 "过时条款，仅供历史归档对照。", "refund", "v1", "RETIRED",
                 now - timedelta(days=300)),
            )
            cur.execute(
                "INSERT INTO ticket (ticket_id,customer_id,channel,subject,body,"
                "created_at,sla_due_at,status,current_queue,resolution) "
                "VALUES (%s,%s,'email',%s,%s,%s,%s,'CLOSED',%s,%s)",
                ("T-TEST-HIST", "C-TEST", "历史工单", "上次的问题",
                 now - timedelta(days=20), now - timedelta(days=20), "售后组",
                 "已按退款政策处理完毕"),
            )
            cur.execute(
                "INSERT INTO ticket (ticket_id,customer_id,channel,subject,body,"
                "created_at,sla_due_at,status,current_queue,resolution) "
                "VALUES (%s,%s,'email',%s,%s,%s,%s,'OPEN',%s,%s)",
                ("T-TEST-CUR", "C-TEST", "当前工单", "这次的订单 O-TEST-1",
                 now - timedelta(hours=2), now + timedelta(hours=4), "待分诊",
                 "当前工单不应泄漏的结论"),
            )
            cur.execute(
                "INSERT INTO ticket (ticket_id,customer_id,channel,subject,body,"
                "created_at,sla_due_at,status,current_queue,resolution) "
                "VALUES (%s,%s,'email',%s,%s,%s,%s,'CLOSED',%s,%s)",
                ("T-TEST-FUTURE", "C-TEST", "未来工单", "以后才发生的工单",
                 now + timedelta(days=3), now + timedelta(days=4), "售后组",
                 FUTURE_SENTINEL),
            )
    except Exception as exc:  # noqa: BLE001
        pytest.skip("数据库不可用，跳过 W3 契约测试: " + str(exc))
    yield
    with db.tx() as cur:
        cur.execute("DELETE FROM refund WHERE refund_no='RF-TEST-1'")
        cur.execute("DELETE FROM kb_article WHERE kb_id IN "
                    "('KB-TEST-PUB','KB-TEST-RET')")
        cur.execute("DELETE FROM ticket WHERE ticket_id IN "
                    "('T-TEST-HIST','T-TEST-CUR','T-TEST-FUTURE')")
        cur.execute("DELETE FROM order_line WHERE order_no='O-TEST-1'")
        cur.execute("DELETE FROM orders WHERE order_no IN "
                    "('O-TEST-1','O-TEST-FOREIGN')")


def test_get_order_returns_line_items():
    payload = tools.get_order("O-TEST-1", ME)
    fields = {f["field"] for f in payload["facts"]}
    assert payload["found"] is True
    assert {"line_sku", "line_qty", "line_unit_price"} <= fields


def test_get_order_cross_customer_blocked():
    payload = tools.get_order("O-TEST-FOREIGN", ME)
    assert payload["found"] is False
    assert payload["error"] == "NOT_FOUND_OR_OUT_OF_SCOPE"


def test_get_order_missing_key_rejected():
    with pytest.raises(ValueError):
        tools.get_order("", ME)


def test_refund_positive():
    payload = tools.get_refund_records("O-TEST-1", ME)
    assert payload["found"] is True
    states = [f["value"] for f in payload["facts"] if f["field"] == "refund_state"]
    assert states == ["APPLIED"]


def test_refund_cross_customer_blocked():
    payload = tools.get_refund_records("O-TEST-FOREIGN", ME)
    assert payload["found"] is False
    assert payload["error"] == "OUT_OF_SCOPE"


def test_refund_domain_absence():
    payload = tools.get_refund_records("O-TEST-1", OTHER)
    assert payload["found"] is False


def test_refund_infrastructure_error(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("模拟数据库执行失败")

    monkeypatch.setattr(tools.db, "query_one", boom)
    with pytest.raises(ToolError):
        tools.get_refund_records("O-TEST-1", ME)


def test_kb_published_visible_with_metadata():
    payload = tools.search_kb("退款")
    fields = {f["field"] for f in payload["facts"]}
    refs = {f["ref"] for f in payload["facts"]}
    assert payload["found"] is True
    assert {"policy_version", "policy_status", "policy_snippet",
            "policy_title"} <= fields
    assert refs == {"KB-TEST-PUB"}


def test_kb_retired_invisible():
    payload = tools.search_kb("过时条款")
    assert payload["found"] is False
    assert payload["error"] == "NO_PUBLISHED_POLICY"


def test_ticket_history_excludes_current_and_future():
    payload = tools.get_ticket_history(ME, "T-TEST-CUR")
    refs = {f["ref"] for f in payload["facts"]}
    values = [str(f["value"]) for f in payload["facts"]]
    assert refs == {"T-TEST-HIST"}
    assert "T-TEST-CUR" not in refs and "T-TEST-FUTURE" not in refs
    assert FUTURE_SENTINEL not in values
    assert "当前工单不应泄漏的结论" not in values


def test_ticket_history_domain_absence():
    payload = tools.get_ticket_history(ME, "T-TEST-HIST")
    assert payload["found"] is False
    assert payload["error"] == "NO_HISTORY_TICKET"


def test_no_decision_fields_anywhere():
    payloads = [
        tools.get_order("O-TEST-1", ME),
        tools.get_refund_records("O-TEST-1", ME),
        tools.search_kb("退款"),
        tools.get_ticket_history(ME, "T-TEST-CUR"),
    ]
    hits = []
    for payload in payloads:
        hits.extend(tools.decision_key_hits(payload))
    assert hits == []
