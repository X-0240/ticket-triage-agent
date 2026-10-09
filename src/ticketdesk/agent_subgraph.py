"""受控 Agent 子图：只有歧义档能进入，且有界、可审计、可拒绝。

评审钉住的三条：

1. **入口由代码强制**：`route != "ambiguous"` 一律拒绝并给原因码，不静默放行；
2. **停止条件不止次数**：预算耗尽、同一工具同参数重复、没有新证据、工具失败，
   都要安全停止并转人工；"没有新证据"由程序比对 `fact_id` 集合判断，不听模型自述；
3. **引用校验覆盖整个执行**：`allowed_fact_ids` = 本次执行的基础工作流证据 + 子图新增证据。

模型与工具执行器都是**可注入**的，测试不依赖真实模型或数据库。
"""

from dataclasses import dataclass, field

ROUTE_AMBIGUOUS = "ambiguous"


class EntryDenied(ValueError):
    """非歧义档尝试进入子图。"""

    def __init__(self, code, reason):
        super().__init__("%s: %s" % (code, reason))
        self.code = code
        self.reason = reason


class StageTimeout(Exception):
    """带阶段的超时：由注入的模型/工具执行器抛出，子图**透传**给运行器分类。

    `stage` 取 `"model"` 或 `"tool"`。子图不把它降级成普通人工转交结果——
    否则运行器无法还原故障类型与阶段。
    """

    def __init__(self, stage):
        super().__init__("timeout at stage: " + str(stage))
        self.stage = stage


@dataclass(frozen=True)
class RunState:
    """一次子图执行的累计状态（供审计与停止判断）。"""

    allowed_fact_ids: set = field(default_factory=set)
    calls_seen: set = field(default_factory=set)
    tool_calls: int = 0
    stop_code: str | None = None


def enter(route):
    """入口门禁：非歧义档直接拒绝（带原因码）。"""
    if route != ROUTE_AMBIGUOUS:
        raise EntryDenied(
            "ENTRY_DENIED", "只有歧义档能进入子图，当前档位: " + str(route)
        )


def _call_key(action):
    args = action.get("args") or {}
    return (action.get("tool"), tuple(sorted(args.items())))


def run(route, base_fact_ids, model, executor, budget=4):
    """跑一次受控取证循环。

    参数：
        route：来自三档路由的档位（只有 ambiguous 能进）。
        base_fact_ids：基础工作流已有的证据 id（本次执行）。
        model：`model(allowed_fact_ids, step) -> {"tool":..,"args":..}` 或 `{"final": payload}`。
        executor：`executor(tool=..., **args) -> {"fact_ids": [...], "facts": [...]}`，失败时抛异常。
        budget：工具调用预算上限。

    返回 dict：action ∈ {decide, human_review}；停止时带 stop_code 与原因。
    """
    enter(route)
    allowed = set(base_fact_ids)
    seen = set()
    for step in range(budget):
        action = model(allowed_fact_ids=sorted(allowed), step=step)
        if action.get("final") is not None:
            return {"action": "decide", "payload": action["final"],
                    "allowed_fact_ids": allowed, "tool_calls": len(seen),
                    "stop_code": None}
        key = _call_key(action)
        if key in seen:
            return {"action": "human_review", "payload": None,
                    "allowed_fact_ids": allowed, "tool_calls": len(seen),
                    "stop_code": "REPEATED_CALL"}
        seen.add(key)
        try:
            result = executor(tool=action.get("tool"), **(action.get("args") or {}))
        except StageTimeout:
            # 先于通用异常处理：带阶段信息的超时必须透传，不能被降级成 TOOL_FAILED
            raise
        except Exception:
            return {"action": "human_review", "payload": None,
                    "allowed_fact_ids": allowed, "tool_calls": len(seen),
                    "stop_code": "TOOL_FAILED"}
        new_ids = set(result.get("fact_ids") or []) - allowed
        if not new_ids:
            return {"action": "human_review", "payload": None,
                    "allowed_fact_ids": allowed, "tool_calls": len(seen),
                    "stop_code": "NO_NEW_EVIDENCE"}
        allowed |= new_ids
    return {"action": "human_review", "payload": None, "allowed_fact_ids": allowed,
            "tool_calls": len(seen), "stop_code": "BUDGET_EXHAUSTED"}
