"""判定节点的输入输出契约与事实引用校验（W3 第二阶段第 1 步）。

三条硬约束（评审要求）：

1. **事实引用必须属于本次执行**：`evidence_bundle` 里的 fact_id 只能来自
   本次执行产生的工具结果集合；不存在、伪造、或引用其他执行记录的 ID 一律判无效。
2. **服务端拥有最终护栏决定权**：模型可以提出 `needs_human`，但**不能用 false
   覆盖系统强制的转人工**（强制时由服务端置为 True 并记录 override 原因）。
3. **失败结果必须可拒绝**：枚举错误、证据引用无效、证据为空、出现 `auto_send=true`
   （本期不做自动发送）都不能作为正常结果放行，且要带上可记录的原因码。
"""

from dataclasses import dataclass, field

QUEUES = ("履约组", "物流组", "售后组", "投诉组", "咨询组")
PRIORITIES = ("P0", "P1", "P2", "P3")


class DecisionError(ValueError):
    """判定结果不合法：带原因码，供审计与坏例分析。"""

    def __init__(self, code, reason):
        super().__init__("%s: %s" % (code, reason))
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class Decision:
    """通过校验的判定结果。`needs_human` 以服务端结论为准。"""

    queue: str | None
    priority: str | None
    evidence_bundle: list = field(default_factory=list)
    draft_reply: str = ""
    confidence: float = 0.0
    needs_human: bool = True
    forced_human_by_server: bool = False


def validate_decision(payload, allowed_fact_ids, forced_human=False):
    """校验判定结果；不合法直接抛 `DecisionError`，不放行。

    参数：
        payload：模型或桩的输出（dict）。
        allowed_fact_ids：**本次执行**产生的 fact_id 集合（工具结果的并集）。
        forced_human：服务端是否强制转人工（例如工具失败、证据不足）。
    """
    if payload.get("auto_send"):
        raise DecisionError(
            "AUTO_SEND_FORBIDDEN", "本期不做自动发送，出现 auto_send=true"
        )

    evidence = payload.get("evidence_bundle") or []
    if not isinstance(evidence, list) or not evidence:
        raise DecisionError("EVIDENCE_EMPTY", "证据包为空，不能作为正常结果放行")

    unknown = [item for item in evidence if item not in allowed_fact_ids]
    if unknown:
        raise DecisionError(
            "EVIDENCE_UNKNOWN",
            "证据引用不属于本次执行: " + ",".join(map(str, unknown)),
        )

    queue = payload.get("queue")
    priority = payload.get("priority")
    if queue is not None and queue not in QUEUES:
        raise DecisionError("QUEUE_INVALID", "队列不在配置枚举内: " + str(queue))
    if priority is not None and priority not in PRIORITIES:
        raise DecisionError(
            "PRIORITY_INVALID", "优先级不在枚举内: " + str(priority)
        )

    # 服务端护栏优先：模型说不需要人工，但系统判定必须转人工时，服务端说了算
    server_human = bool(forced_human)
    model_human = payload.get("needs_human", True)
    needs_human = True if server_human else bool(model_human)
    if server_human and not model_human:
        needs_human = True

    return Decision(
        queue=queue,
        priority=priority,
        evidence_bundle=list(evidence),
        draft_reply=str(payload.get("draft_reply") or ""),
        confidence=float(payload.get("confidence") or 0.0),
        needs_human=needs_human,
        forced_human_by_server=server_human and not model_human,
    )
