"""三档路由（确定性规则驱动）：硬事实 / 软事实 / 歧义。

关键约束（评审补充）：

1. **unique ≠ 硬事实档**：唯一候选也可能与正文语义冲突（第一层 Gate 复核出的
   D-36〜D-40 就是这样）。所以"硬事实"要看规则自身的映射是否确定，不看候选个数。
2. **档位由确定性规则决定**，模型不能自选；校验器只判 `CONSISTENT / INCONSISTENT /
   UNCERTAIN`，**不得改队列、优先级或编造候选**。
3. **服务端护栏优先**：工具失败、必要事实缺失等强制人工条件，不能被模型
   `needs_human=false` 覆盖，并要留下可审计的原因码。

歧义档在 Agent 子图接入前**稳定转人工**，不做任何隐式继续。
"""

from dataclasses import dataclass

ROUTE_HARD = "hard_fact"
ROUTE_SOFT = "soft_fact"
ROUTE_AMBIGUOUS = "ambiguous"

CHECK_RESULTS = ("CONSISTENT", "INCONSISTENT", "UNCERTAIN")


@dataclass(frozen=True)
class RoutingInput:
    """路由判定所需的全部输入（都由上游确定性计算给出）。"""

    candidates: list
    required_facts_complete: bool
    candidate_requires_semantics: bool
    tool_failed: bool = False


def decide_route(state):
    """确定性路由：返回档位与原因码（不调用任何模型）。"""
    if state.tool_failed:
        return ROUTE_AMBIGUOUS, "TOOL_FAILED"
    if not state.required_facts_complete:
        return ROUTE_AMBIGUOUS, "FACTS_INCOMPLETE"
    if len(state.candidates) != 1:
        return ROUTE_AMBIGUOUS, "CANDIDATES_UNRESOLVED"
    if state.candidate_requires_semantics:
        return ROUTE_SOFT, "NEEDS_CONSISTENCY_CHECK"
    return ROUTE_HARD, "DETERMINISTIC_MAPPING"


def run_light_check(checker, statement, candidate):
    """跑一次轻量一致性校验：只允许三种结果，其它一律按 UNCERTAIN 处理。"""
    result = checker(statement=statement, candidate=candidate)
    if result not in CHECK_RESULTS:
        return "UNCERTAIN"
    return result


def handle(state, statement=None, checker=None):
    """按档位给出处置；不产出草稿、不调用补充工具。

    返回 dict：route / action / needs_human / reason_code / checks
    action ∈ {"decide", "human_review"}；歧义档在子图接入前一律 human_review。
    """
    route, reason_code = decide_route(state)
    checks = []
    if route == ROUTE_HARD:
        return {"route": route, "action": "decide", "needs_human": False,
                "reason_code": reason_code, "checks": checks}
    if route == ROUTE_SOFT:
        if checker is None:
            return {"route": ROUTE_AMBIGUOUS, "action": "human_review",
                    "needs_human": True, "reason_code": "CHECKER_UNAVAILABLE",
                    "checks": checks}
        result = run_light_check(checker, statement, state.candidates[0])
        checks.append({"checker_result": result})
        if result == "CONSISTENT":
            return {"route": ROUTE_SOFT, "action": "decide", "needs_human": False,
                    "reason_code": "CHECK_CONSISTENT", "checks": checks}
        return {"route": ROUTE_AMBIGUOUS, "action": "human_review",
                "needs_human": True,
                "reason_code": "CHECK_" + result, "checks": checks}
    # 歧义档：子图未接入，稳定转人工（不抛异常、不继续往下走）
    return {"route": ROUTE_AMBIGUOUS, "action": "human_review",
            "needs_human": True, "reason_code": reason_code, "checks": checks}
