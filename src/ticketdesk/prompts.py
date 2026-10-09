"""A/C 实验的提示词（唯一来源：Manifest 直接哈希本文件）。

两条要求来自 DeepSeek 官方 JSON 输出说明：提示词里必须出现 "json" 字样，
并给出期望 **json** 结构的示例。所以两个提示词都带明确的 json 契约与示例。

口径纪律：

- 提示词里**不含 gold**：不给 expected_queue / expected_priority / agent_needed，
  也不暗示"这题需要补取证"；模型只看案例事实与可用证据列表；
- 证据引用必须来自给定的事实列表（fact_id），模型不能自造；
- 本期**不做自动发送**：草稿只是副输出，`auto_send` 一律不出现。
"""

from ticketdesk import verdict

QUEUE_LIST = "/".join(verdict.QUEUES)
PRIORITY_LIST = "/".join(verdict.PRIORITIES)

DECISION_CONTRACT = (
    "只输出一个 json 对象，字段固定为：\n"
    '{"queue": "<%s 之一或 null>", "priority": "<%s 之一或 null>", '
    '"evidence_bundle": ["<证据 id>", "..."], "draft_reply": "<可选的首回复草稿>", '
    '"needs_human": <true|false>, "confidence": <0~1 的小数>}\n'
    "示例 json 输出：\n"
    '{"queue": "物流组", "priority": "P1", "evidence_bundle": ["fact_03", '
    '"fact_07"], "draft_reply": "已核实物流轨迹异常，正在跟进。", '
    '"needs_human": true, "confidence": 0.7}\n'
) % (QUEUE_LIST, PRIORITY_LIST)

WORKFLOW_SYSTEM = (
    "你是客服工单分诊助手。你只能依据给定的事实做判断，不能凭常识补充事实，"
    "也不能引用列表里没有的证据 id。\n"
    "证据不足以支持结论时，把 queue/priority 设为 null 并让 needs_human 为 true，"
    "不要硬猜。\n\n" + DECISION_CONTRACT
)

AGENT_SYSTEM = (
    "你是客服工单分诊助手，可以申请补充证据。每一步只能输出一个 json 对象：\n"
    '需要补查时：{"tool": "<工具名>", "args": {<工具参数>}}\n'
    '可以给结论时：{"final": {<判定 json>}}\n'
    "可用工具（只能从这里选，参数填业务键）：\n"
    "- get_refund_records：参数 order_no，返回该订单的退款记录（state/amount）\n"
    "- search_kb：参数 query（关键词，如 退款/取消/保修/物流/超时），"
    "返回已发布政策条款（title/snippet/version）\n"
    "- get_ticket_history：无参数，返回本客户早于当前工单的历史处置结论\n"
    "同一工具同一参数不要重复调用；已经拿到足够证据就必须给出 final，"
    "不要无限补查。\n"
    "判定 json 的字段与上面示例一致（queue/priority/evidence_bundle/draft_reply/"
    "needs_human/confidence），evidence_bundle 只能引用已经出现过的事实 id。\n\n"
    + DECISION_CONTRACT
)


def _facts_block(facts):
    lines = []
    for fact in facts:
        lines.append("%s | %s = %s（来源 %s，引用键 %s）" % (
            fact["fact_id"], fact["field"], fact["value"],
            fact.get("source"), fact.get("ref")))
    return "\n".join(lines) if lines else "（当前没有任何事实）"


def case_brief(case_view):
    """案例简述：只写业务事实，不写任何 gold。"""
    return (
        "工单号：%s\n决策问题：%s\n工单正文：%s\n"
        "订单号：%s\n已知订单/物流事实：%s"
        % (case_view["ticket_id"], case_view["decision_question"],
           case_view["body"], case_view.get("order_no") or "无",
           case_view.get("business_state") or "未知")
    )


def workflow_messages(case_view, facts):
    """固定工作流判定节点：只有一次机会，没有工具。"""
    user = (
        "%s\n\n本次可用的证据（只能引用这些 id）：\n%s\n\n"
        "请直接给出判定 json。"
        % (case_brief(case_view), _facts_block(facts))
    )
    return [{"role": "system", "content": WORKFLOW_SYSTEM},
            {"role": "user", "content": user}]


def agent_messages(case_view, facts, step, history):
    """子图某一步：可以补查，也可以给结论。"""
    trace = "\n".join(history) if history else "（还没有补查）"
    user = (
        "%s\n\n当前可用证据（引用时只能写这些 id）：\n%s\n\n"
        "已经做过的补查：\n%s\n\n"
        "这是第 %d 步：需要补查就输出工具 json，够了下结论就输出 final json。"
        % (case_brief(case_view), _facts_block(facts), trace, step + 1)
    )
    return [{"role": "system", "content": AGENT_SYSTEM},
            {"role": "user", "content": user}]
