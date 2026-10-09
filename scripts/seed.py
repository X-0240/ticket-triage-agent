"""种子数据：一个客户下覆盖三类工单，外加一条"引用了不存在的订单"的工单。

三类工单（评审要求同一 customer_id 下都要出现）：

1. 正常：正文提到订单，事实指向唯一队列条件；
2. 上下文缺失：正文没有订单号，取不到订单事实；
3. 固定取数仍无法唯一判定：事实同时命中多个方向，必须读正文。

用法：python scripts/seed.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticketdesk import db  # noqa: E402

CUSTOMER = "C-1001"
OTHER_CUSTOMER = "C-2002"


def _stamp(days=0, hours_ago=0):
    return datetime.now().replace(microsecond=0) - timedelta(
        days=days, hours=hours_ago
    )


def seed():
    now = _stamp()
    rows = [
        # 订单：一个属于本客户、一个属于别的客户（用来做跨客户反例）
        (
            "INSERT INTO orders (order_no,customer_id,status,amount,created_at,paid_at) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("O-2001", CUSTOMER, "PAID", 199.00, _stamp(days=5), _stamp(days=5)),
        ),
        (
            "INSERT INTO orders (order_no,customer_id,status,amount,created_at,paid_at) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("O-2002", CUSTOMER, "SHIPPED", 88.00, _stamp(days=9), _stamp(days=9)),
        ),
        (
            "INSERT INTO orders (order_no,customer_id,status,amount,created_at,paid_at) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("O-9009", OTHER_CUSTOMER, "SHIPPED", 15.00, _stamp(days=2), _stamp(days=2)),
        ),
        # 工单 1｜正常：正文带订单号，已支付 5 天未发货
        (
            "INSERT INTO ticket (ticket_id,customer_id,channel,subject,body,"
            "created_at,sla_due_at,status,current_queue) "
            "VALUES (%s,%s,'email',%s,%s,%s,%s,'OPEN',%s)",
            (
                "T-1001",
                CUSTOMER,
                "订单一直没发货",
                "我的订单 O-2001 上周就付了，到现在还没发货，麻烦看一下。",
                _stamp(hours_ago=3),
                now + timedelta(hours=2),
                "履约组",
            ),
        ),
        # 工单 2｜上下文缺失：正文没有订单号
        (
            "INSERT INTO ticket (ticket_id,customer_id,channel,subject,body,"
            "created_at,sla_due_at,status,current_queue) "
            "VALUES (%s,%s,'email',%s,%s,%s,%s,'OPEN',%s)",
            (
                "T-1002",
                CUSTOMER,
                "问一下",
                "我想问一下我这个情况怎么处理，谢谢。",
                _stamp(hours_ago=1),
                now + timedelta(hours=6),
                "售后组",
            ),
        ),
        # 工单 3｜固定取数无法唯一判定：既像物流延迟，又像要退款
        (
            "INSERT INTO ticket (ticket_id,customer_id,channel,subject,body,"
            "created_at,sla_due_at,status,current_queue) "
            "VALUES (%s,%s,'email',%s,%s,%s,%s,'OPEN',%s)",
            (
                "T-1003",
                CUSTOMER,
                "上次也是这样，一直没人管",
                "订单 O-2002 到现在还没到，上次也是这样没人管，我要退款。",
                _stamp(hours_ago=5),
                now + timedelta(minutes=40),
                "投诉组",
            ),
        ),
        # 失败路径 A｜引用了不存在的订单
        (
            "INSERT INTO ticket (ticket_id,customer_id,channel,subject,body,"
            "created_at,sla_due_at,status,current_queue) "
            "VALUES (%s,%s,'email',%s,%s,%s,%s,'OPEN',%s)",
            (
                "T-1004",
                CUSTOMER,
                "查一下订单",
                "帮我看看订单 O-9999 什么情况。",
                _stamp(hours_ago=2),
                now + timedelta(hours=4),
                None,
            ),
        ),
        # 发货事实（三种语义各一条）：
        #   O-2002 → DELAYED + exception_flag=1（代表物流延迟）
        #   O-9009 → 属于别的客户，有行也读不到
        #   O-2001 → **不建行**，这才真正代表"未产生发货事实"
        (
            "INSERT INTO shipment (order_no,state,carrier,tracking_no,"
            "exception_flag,shipped_at,last_event_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                "O-2002",
                "DELAYED",
                "SF",
                "SF1234567890",
                1,
                _stamp(days=7),
                _stamp(hours_ago=6),
            ),
        ),
        (
            "INSERT INTO shipment (order_no,state,carrier,tracking_no,"
            "exception_flag,shipped_at,last_event_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                "O-9009",
                "SHIPPED",
                "YTO",
                "YT0001",
                0,
                _stamp(days=2),
                _stamp(days=2),
            ),
        ),
    ]
    with db.tx() as cur:
        cur.execute("DELETE FROM ticket")
        cur.execute("DELETE FROM shipment")
        cur.execute("DELETE FROM orders")
        for sql, params in rows:
            cur.execute(sql, params)
    return {
        "tickets": db.query_one("SELECT COUNT(*) AS n FROM ticket")["n"],
        "orders": db.query_one("SELECT COUNT(*) AS n FROM orders")["n"],
    }


if __name__ == "__main__":
    print("种子数据写入：", seed())
