"""A/C 运行器骨架：逐案例隔离、可注入模型与工具执行器、失败不丢样本。

硬约束（评审要求）：

1. **逐案例隔离**：每个案例、每条臂都重新创建状态（基础事实、模型调用器、工具执行器），
   两臂只共享**冻结的输入与规则文件**，不共享可变执行状态；
2. **接口契约**：模型调用器 `model_factory(case_id, allowed_fact_ids)` 返回动作或最终结果；
   工具执行器 `executor_factory(case_id)` 返回结果 dict 或抛异常；
3. **失败保留**：异常、预算耗尽、无新证据等一律写进记录（带 `stop_code`），不丢样本；
4. **哈希不符拒绝运行**：Manifest 校验不通过时直接抛错，不产生任何运行记录。
"""

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

from ticketdesk import agent_subgraph, routing


class HashMismatch(ValueError):
    """Manifest 校验不通过：拒绝运行。"""


@dataclass(frozen=True)
class RunRecord:
    """一条逐次执行记录（A 或 C 的一案例一次）。"""

    case_id: str
    arm: str
    run_id: str
    route: str
    action: str
    stop_code: str | None
    tool_calls: int
    decision: dict | None
    latency_ms: int
    failed: bool = False
    failure_code: str | None = None
    notes: list = field(default_factory=list)


def _run_id(arm, case_id):
    stamp = datetime.now().strftime("%H%M%S%f")[:10]
    return "%s-%s-%s" % (arm, case_id, stamp)


def _workflow_decision(case_id, model_factory):
    """A 臂：基础取数 + 单次判定节点（不进入子图）。"""
    model = model_factory(case_id, [])
    action = model(allowed_fact_ids=[], step=0)
    return action.get("final")


def run_case(arm, case, route_input, model_factory, executor_factory, budget=4):
    """跑一案例的一臂；每次调用都新建模型与执行器（隔离）。"""
    started = time.perf_counter()
    allowed = set(case.get("base_fact_ids") or [])
    decision, stop_code, tool_calls, route = None, None, 0, "workflow"
    failed, failure_code, notes = False, None, []
    if arm == "A":
        decision = _workflow_decision(case["case_id"], model_factory)
    elif arm == "C":
        route, reason = routing.decide_route(route_input)
        if route == routing.ROUTE_AMBIGUOUS:
            try:
                out = agent_subgraph.run(
                    "ambiguous", allowed,
                    model_factory(case["case_id"], sorted(allowed)),
                    executor_factory(case["case_id"]), budget=budget,
                )
                decision = out["payload"]
                stop_code = out["stop_code"]
                tool_calls = out["tool_calls"]
                if out["action"] != "decide":
                    failed, failure_code = True, out["stop_code"]
            except Exception as exc:  # noqa: BLE001 - 失败必须留痕，不丢样本
                failed, failure_code = True, "RUNNER_EXCEPTION"
                notes.append(str(exc))
        else:
            decision = _workflow_decision(case["case_id"], model_factory)
            stop_code = None
    else:
        raise ValueError("未知的臂: " + str(arm))
    latency = int((time.perf_counter() - started) * 1000)
    return RunRecord(
        case_id=case["case_id"], arm=arm, run_id=_run_id(arm, case["case_id"]),
        route=route, action="decide" if decision else "human_review",
        stop_code=stop_code, tool_calls=tool_calls, decision=decision,
        latency_ms=latency, failed=failed, failure_code=failure_code, notes=notes,
    )


def run_experiment(cases, route_inputs, model_factory, executor_factory,
                   manifest_expected, manifest, problem_checker, budget=4):
    """跑完整对照。哈希不符直接拒绝，不产生记录。"""
    problems = problem_checker(manifest, manifest_expected)
    if problems:
        raise HashMismatch("Manifest 校验失败: " + "; ".join(problems))
    records = []
    for case in cases:
        for arm in ("A", "C"):
            records.append(asdict(run_case(
                arm, case, route_inputs[case["case_id"]], model_factory,
                executor_factory, budget=budget,
            )))
    return records
