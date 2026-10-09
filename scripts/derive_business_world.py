"""为冻结的 50 条案例派生"可加载的业务世界"（确定、可核验、**不读答案**）。

为什么需要它：三条动态取数模式要查 `refund` / `kb_article` / `order_line` 与历史工单
处置记录，但仓库里从来没有生成过这些数据（表是空的），正式 A/C 就无法检验动态取数
是否真的能拿到新证据。本脚本按**业务情境**构造一份一致的世界，写入
`experiments/ac_v1/derived/business_world_v1.json`，再由 `scripts/load_experiment_db.py`
加载到隔离的实验库，让正式运行继续走真实 `tools.py` 查库。

四条硬约束（评审要求）：

1. **不许读答案**：只读 business_state / scenario_type / business_intent /
   surface_form_variant / 冻结正文与工单号；**不读** `expected_queue`、
   `expected_priority`、`expected_handoff`，也不读 `agent_needed` 标签；
2. **构造数据必须标明**：输出带 `data_origin` 与 `disclaimer`，不伪装成真实业务记录；
3. **50 条都要有明确的数据世界**，不是只给 Agent-needed 的 15 条造数据；
4. **时间字段写成偏移**（`*_offset_hours`），加载时按加载时刻换算成绝对时间，
   这样 SLA 与"历史工单早于当前工单"的关系在运行当天成立，文件本身保持确定。

用法：

    python scripts/derive_business_world.py          # 生成世界文件
    python scripts/derive_business_world.py --check  # 校验现有文件与重新派生一致
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticketdesk import verdict  # noqa: E402

SPEC = ROOT / "experiments" / "discovery" / "spec_50.json"
INPUTS = ROOT / "experiments" / "discovery" / "inputs_50.json"
OUT = ROOT / "experiments" / "ac_v1" / "derived" / "business_world_v1.json"

VERSION = "v1"
CUSTOMER = "C-1001"
ORDER_AMOUNT = 199.00
KB_UPDATED_AT = "2026-09-01 12:00:00"

# 业务情境 → 世界数据（只看情境，不看 gold；处置备注里不出现任何队列名）
STATE_FACTS = {
    "paid_no_shipment": dict(
        order="PAID", ship=None, refund=None, sku="SKU-1001",
        resolution="已催单并告知预计发货时间"),
    "shipped_delayed": dict(
        order="SHIPPED", ship=("DELAYED", 1), refund=None, sku="SKU-1001",
        resolution="已按物流异常流程登记，承运商排查中"),
    "shipped_normal": dict(
        order="SHIPPED", ship=("SHIPPED", 0), refund=None, sku="SKU-1001",
        resolution="已按在途查询答复最新轨迹"),
    "refund_requested": dict(
        order="PAID", ship=None, refund="APPLIED", sku="SKU-1001",
        resolution="已登记退款申请，等待审核"),
    "no_order_context": dict(
        order=None, ship=None, refund=None, sku=None,
        resolution="已请客户补充订单号"),
    "multi_signal": dict(
        order="SHIPPED", ship=("DELAYED", 1), refund="REJECTED", sku="SKU-1001",
        resolution="已拆成物流与退款两个事项分别跟进"),
    "order_not_found": dict(
        order=None, ship=None, refund=None, sku=None,
        resolution="已请客户核对订单号后重开"),
    "delivered_policy_question": dict(
        order="SHIPPED", ship=("SHIPPED", 0), refund=None, sku="SKU-2002",
        resolution="已按保修条款答复客户"),
    "sla_soon": dict(
        order="PAID", ship=None, refund=None, sku="SKU-1001",
        resolution="已优先响应并升级处理"),
    "refund_priority": dict(
        order="PAID", ship=None, refund="APPLIED", sku="SKU-1001",
        resolution="已加急登记退款申请"),
}

# SLA 剩余时间：临近超时的那一类给 1 小时，其余 6 小时（与既有生成脚本口径一致）
SLA_OFFSET_HOURS = {"sla_soon": 1.0}
DEFAULT_SLA_OFFSET_HOURS = 6.0

SKUS = {
    "SKU-1001": ("无线蓝牙耳机", 199.00),
    "SKU-2002": ("智能手环（整机保修 12 个月）", 299.00),
}

REFUND_REASON = {
    "APPLIED": "客户申请退款：改变主意",
    "REJECTED": "客户申请退款：商品已发出，未达退款条件",
}

# 全局政策知识库：构造文本，覆盖三类动态取数会遇到的关键词
KB_ARTICLES = [
    {
        "kb_id": "K-1001", "policy_type": "refund",
        "title": "退款政策：申请条件与到账时效",
        "body": ("未发货订单可全额退款，审核通过后 3 个工作日退回原支付渠道；"
                 "已发货订单需先拦截或签收后退回，退款在签收后 7 个工作日内处理；"
                 "退款申请被拒时须说明原因并给客户留申诉入口。"),
    },
    {
        "kb_id": "K-1002", "policy_type": "cancel",
        "title": "取消订单规则：未发货与已发货的区别",
        "body": ("未发货订单可即时取消并原路退回；已发货订单不能直接取消，"
                 "只能走拦截或拒收流程；取消与退款是两步，取消成功不等于退款到账。"),
    },
    {
        "kb_id": "K-1003", "policy_type": "warranty",
        "title": "商品保修政策：整机与配件",
        "body": ("整机保修 12 个月，配件保修 3 个月，自签收之日起算；"
                 "保修需提供订单号与签收凭证；人为损坏、进液、私自拆修不在保修范围；"
                 "保修期内非人为故障免费维修，超过 30 天未修复可申请换新。"),
    },
    {
        "kb_id": "K-1004", "policy_type": "logistics",
        "title": "物流异常处理与赔付标准",
        "body": ("物流延迟超过 72 小时按每天 20 元赔付，单笔上限 100 元；"
                 "包裹丢失按实付金额全额赔付；物流异常需先核实承运商轨迹与异常标记，"
                 "再决定赔付或补发，不能只看客户描述就承诺赔付。"),
    },
    {
        "kb_id": "K-1005", "policy_type": "sla",
        "title": "工单响应时效与超时升级（SLA）",
        "body": ("普通工单 6 小时内首次响应；临近超时（2 小时内到期）须优先响应并升级；"
                 "超时未响应由值班主管跟进，加急工单需在 1 小时内给出结论。"),
    },
    {
        "kb_id": "K-1006", "policy_type": "missing_order",
        "title": "缺少订单号时的处理规范",
        "body": ("客户未提供订单号且无法定位时，先按客户账号维度检索；"
                 "仍无法定位则请客户补充订单号或下单手机号，不得凭猜测指定订单，"
                 "也不得据此承诺退款或赔付。"),
    },
]


class WorldError(RuntimeError):
    """世界构造的前置条件不成立：直接失败，不产出可疑数据。"""


def sha256_lf(path):
    return hashlib.sha256(
        Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def state_facts(state):
    if state not in STATE_FACTS:
        raise WorldError("未知 business_state: " + str(state))
    return STATE_FACTS[state]


def guard_no_answer_leak(world):
    """输出里不得出现队列名或优先级取值——那些是 gold，不是业务世界该有的东西。"""
    banned = list(verdict.QUEUES) + list(verdict.PRIORITIES)
    for table, rows in world["tables"].items():
        for row in rows:
            for key, value in row.items():
                hits = [token for token in banned if token in str(value)]
                if hits:
                    raise WorldError(
                        "%s.%s 出现 gold 取值 %s" % (table, key, hits))


def build_world(spec, inputs):
    """按业务情境构造世界（纯函数：同样的输入必然得到同样的输出）。"""
    cases = {case["case_id"]: case for case in inputs["cases"]}
    if set(cases) != {row["case_id"] for row in spec}:
        raise WorldError("spec_50 与 inputs_50 的案例编号不一致")
    if len(cases) != 50:
        raise WorldError("案例数不是 50：%d" % len(cases))

    tickets, orders, shipments, lines, refunds = [], [], [], [], []
    ordered = sorted(spec, key=lambda row: int(row["case_id"].split("-")[1]))
    total = len(ordered)
    for position, row in enumerate(ordered, start=1):
        case = cases[row["case_id"]]
        facts = state_facts(row["business_state"])
        # D-01 最早（-49 小时），D-50 最新（0 小时）：历史工单天然早于当前工单
        ticket_offset = float(position - total)
        order_no = case["order_no"]
        tickets.append({
            "ticket_id": case["ticket_id"],
            "customer_id": CUSTOMER,
            "channel": "email",
            "subject": row["business_intent"][:20],
            "body": case["body"],
            "status": "OPEN",
            "current_queue": None,
            # 处置备注供 get_ticket_history 使用；当前工单的 resolution 不会被任何工具返回
            "resolution": facts["resolution"],
            "created_offset_hours": ticket_offset,
            "sla_due_offset_hours": SLA_OFFSET_HOURS.get(
                row["business_state"], DEFAULT_SLA_OFFSET_HOURS),
        })
        if facts["order"]:
            orders.append({
                "order_no": order_no,
                "customer_id": CUSTOMER,
                "status": facts["order"],
                "amount": ORDER_AMOUNT,
                "created_offset_hours": ticket_offset - 8 * 24,
                "paid_offset_hours": (ticket_offset - 8 * 24
                                      if facts["order"] != "CREATED" else None),
            })
        if facts["sku"]:
            name, price = SKUS[facts["sku"]]
            lines.append({"order_no": order_no, "sku_code": facts["sku"],
                          "sku_name": name, "qty": 1, "unit_price": price})
        if facts["ship"]:
            state, exception = facts["ship"]
            shipments.append({
                "order_no": order_no,
                "state": state,
                "carrier": "SF",
                "tracking_no": "SF%04d" % position,
                "exception_flag": exception,
                "shipped_offset_hours": ticket_offset - 6 * 24,
                "last_event_offset_hours": ticket_offset - 6,
            })
        if facts["refund"]:
            refunds.append({
                "refund_no": "RF-%04d" % position,
                "order_no": order_no,
                "amount": ORDER_AMOUNT,
                "state": facts["refund"],
                "reason": REFUND_REASON[facts["refund"]],
                "created_offset_hours": ticket_offset - 3,
            })

    kb_articles = [dict(article, version="v1", status="PUBLISHED",
                        updated_at=KB_UPDATED_AT) for article in KB_ARTICLES]
    world = {
        "kind": "ac_v1_business_world",
        "version": VERSION,
        "data_origin": "constructed_for_ac_v1",
        "disclaimer": (
            "本文件是**为 A/C 对照构造的数据**，不是真实业务记录："
            "它按每条案例的业务情境（business_state / scenario_type / 冻结正文）"
            "确定性地生成退款、政策知识库、商品关联与历史处置数据，"
            "加载进隔离的实验库供真实 tools.py 查询。"
        ),
        "forbidden_inputs": ["expected_queue", "expected_priority",
                             "expected_handoff", "agent_needed"],
        "time_convention": (
            "所有 `*_offset_hours` 都是相对加载时刻的偏移，由加载器换算成绝对时间；"
            "知识库 updated_at 为固定日期。"
        ),
        "derived_from": {
            "spec_file": "experiments/discovery/spec_50.json",
            "spec_sha256_lf": sha256_lf(SPEC),
            "inputs_file": "experiments/discovery/inputs_50.json",
            "inputs_sha256_lf": sha256_lf(INPUTS),
            "rules_file": "fixtures/discovery/rules_v1.json",
        },
        "tables": {
            "ticket": tickets,
            "orders": orders,
            "order_line": lines,
            "shipment": shipments,
            "refund": refunds,
            "kb_article": kb_articles,
        },
    }
    world["counts"] = {name: len(rows)
                       for name, rows in world["tables"].items()}
    guard_no_answer_leak(world)
    return world


def render(world):
    return json.dumps(world, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description="派生 A/C 业务世界")
    parser.add_argument("--check", action="store_true",
                        help="只校验现有世界文件与重新派生结果一致，不写盘")
    args = parser.parse_args()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    inputs = json.loads(INPUTS.read_text(encoding="utf-8"))
    text = render(build_world(spec, inputs))
    if args.check:
        if not OUT.exists():
            raise WorldError("世界文件不存在: " + str(OUT))
        if OUT.read_text(encoding="utf-8") != text:
            raise WorldError("世界文件与重新派生结果不一致，请重新生成")
        print("世界文件校验通过：%s" % OUT)
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    world = json.loads(text)
    print("已生成 %s：%s ｜ sha256 %s"
          % (OUT.relative_to(ROOT), world["counts"],
             hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]))


if __name__ == "__main__":
    main()
