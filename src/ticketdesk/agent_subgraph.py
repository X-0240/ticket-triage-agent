"""受控 Agent 子图：只有歧义档能进入，且有界、可审计、可拒绝。

评审钉住的三条：

1. **入口由代码强制**：`route != "ambiguous"` 一律拒绝并给原因码，不静默放行；
2. **停止条件不止次数**：预算耗尽、同一工具同参数重复、没有新证据、工具失败，
   都要安全停止并转人工；"没有新证据"由程序比对 `fact_id` 集合判断，不听模型自述；
3. **引用校验覆盖整个执行**：`allowed_fact_ids` = 本次执行的基础工作流证据 + 子图新增证据。

模型与工具执行器都是**可注入**的，测试不依赖真实模型或数据库。

两层异常边界（顺序不能颠倒，否则故障原因会丢）：

- **模型调用**：裸 `TimeoutError` 在调用点就被标成 `StageTimeout("model")`
  （`call_model`），运行器才知道超时发生在模型阶段；
- **工具调用**：`StageTimeout` 与 `EvidenceSchemaError` 原样上抛（由运行器分类），
  裸 `TimeoutError` 标成 `StageTimeout("tool")`，其余异常才是 `TOOL_FAILED`。
"""

from dataclasses import dataclass, field

from ticketdesk import evidence_adapter

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


def call_model(model, allowed_fact_ids, step):
    """模型调用的**唯一入口**：把发生在模型阶段的超时标上阶段，不冒充其他阶段。

    捕获范围贴着模型调用本身，不放在外层函数上——否则模型调用之后的解析、校验
    步骤抛出的 `TimeoutError` 也会被误记成 `MODEL_TIMEOUT`。
    """
    try:
        return model(allowed_fact_ids=allowed_fact_ids, step=step)
    except StageTimeout:
        raise
    except TimeoutError as exc:
        raise StageTimeout("model") from exc


def run(route, base_fact_ids, model, executor, budget=4, registry=None):
    """跑一次受控取证循环。

    参数：
        route：来自三档路由的档位（只有 ambiguous 能进）。
        base_fact_ids：基础工作流已有的证据 id（本次执行）。
        model：`model(allowed_fact_ids, step) -> {"tool":..,"args":..}` 或 `{"final": payload}`。
        executor：`executor(tool=..., **args) -> 原始工具返回`（真实契约见 `tools.py`），失败时抛异常。
        budget：工具调用预算上限。
        registry：证据适配层（`evidence_adapter.EvidenceRegistry`）。给了它，工具返回
            会先做结构校验与事实登记；非法结构整批拒绝并抛 `EvidenceSchemaError`。

    返回 dict：action ∈ {decide, human_review}；停止时带 stop_code 与原因。
    """
    enter(route)
    allowed = set(base_fact_ids)
    seen = set()
    for step in range(budget):
        action = call_model(model, sorted(allowed), step)
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
            if registry is not None:
                result = registry.adapt(result)
        except StageTimeout:
            # 先于通用异常处理：带阶段信息的超时必须透传，不能被降级成 TOOL_FAILED
            raise
        except evidence_adapter.EvidenceSchemaError as exc:
            # 工具结果结构不合法：原子拒绝（适配层未登记任何事实），
            # 由运行器分类为 INVALID_SCHEMA / tool_result
            exc.tool_calls = len(seen)   # 保留已发生的调用次数，供审计
            raise
        except TimeoutError as exc:
            # 裸超时贴着工具调用点标阶段：不能因为"运行器最终捕获"就记成运行器超时
            raise StageTimeout("tool") from exc
        except Exception:
            return {"action": "human_review", "payload": None,
                    "allowed_fact_ids": allowed, "tool_calls": len(seen),
                    "stop_code": "TOOL_FAILED"}
        fact_ids = set(result.get("fact_ids") or [])
        if "new_fact_ids" in result:
            # 适配层是"是否取得新证据"的唯一判定者（重复事实复用 id → 不算新证据）
            new_ids = set(result["new_fact_ids"])
        else:
            new_ids = fact_ids - allowed
        if not new_ids:
            return {"action": "human_review", "payload": None,
                    "allowed_fact_ids": allowed, "tool_calls": len(seen),
                    "stop_code": "NO_NEW_EVIDENCE"}
        allowed |= fact_ids
    return {"action": "human_review", "payload": None, "allowed_fact_ids": allowed,
            "tool_calls": len(seen), "stop_code": "BUDGET_EXHAUSTED"}
