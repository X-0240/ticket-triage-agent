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

from ticketdesk import (
    agent_subgraph,
    evidence_adapter,
    failure_contract,
    model_client,
    routing,
    verdict,
)


class HashMismatch(ValueError):
    """Manifest 校验不通过：拒绝运行。"""


# 安全停止原因：说明"系统为什么停止继续尝试"，**只记 stop_code，不计入失败分布**
SAFE_STOP_CODES = frozenset({
    "BUDGET_EXHAUSTED",
    "NO_NEW_EVIDENCE",
    "REPEATED_CALL",
})


# 阶段超时由子图定义并透传到这里分类（见 agent_subgraph.StageTimeout）
StageTimeout = agent_subgraph.StageTimeout
@dataclass(frozen=True)
class RunRecord:
    """一条逐次执行记录（A 或 C 的一案例一次）。

    字段语义（三者不可互相替代）：

    - `stop_code`：系统**为什么停止继续尝试**（安全停止原因），此时 `failure_code` 为空；
    - `failure_code` + `failure_stage`：**发生了什么故障、发生在哪一侧**；
    - `validation_code`：模型输出**语义**不合法（队列/优先级取值、证据引用等），
      它不是执行故障，所以**不写进 `failure_code`**；
    - `failed`：本次**自动判定未完成**，不代表发生了执行故障；
    - `timeout_stage`：超时来源（能识别时填写，无法识别时为 `unknown`）。

    `tool_calls` 计的是工具调用**尝试次数**，含失败或被拒绝的那一次。
    """

    case_id: str
    arm: str
    run_id: str
    route: str
    route_reason: str | None
    action: str
    stop_code: str | None
    tool_calls: int
    decision: dict | None
    latency_ms: int
    tokens: int | None = None
    failed: bool = False
    failure_code: str | None = None
    failure_stage: str | None = None
    timeout_stage: str | None = None
    validation_code: str | None = None
    raw_output: dict | None = None
    tool_trace: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def _run_id(arm, case_id):
    stamp = datetime.now().strftime("%H%M%S%f")[:10]
    return "%s-%s-%s" % (arm, case_id, stamp)


def _workflow_decision(case_id, model_factory, allowed_ids):
    """固定工作流：基础取数 + 单次判定节点（不进入子图）。

    判定节点必须拿到**本次执行已有的基础证据**：传空列表会让固定工作流"看不到证据"，
    那样 A 臂就不是被比较的那个固定工作流，对照直接失效。
    """
    model = model_factory(case_id, sorted(allowed_ids))
    action = agent_subgraph.call_model(model, sorted(allowed_ids), 0)
    kind, value, _args = agent_subgraph.normalize_action(action)
    if kind == "tool":
        # 固定工作流没有工具：模型请求取数属于输出结构问题，
        # 记 INVALID_SCHEMA / model_output，不是工具执行失败
        raise verdict.DecisionSchemaError(
            "固定工作流没有可用工具，模型却请求了: " + str(value))
    return value


def _record_failure(record, exc):
    """把异常翻译成记录的故障字段（唯一映射出口）。"""
    record["failed"] = True
    if isinstance(exc, evidence_adapter.EvidenceSchemaError):
        record["failure_code"] = exc.failure_code
        record["failure_stage"] = exc.failure_stage
        record["tool_calls"] = getattr(exc, "tool_calls", 0)
        record["tool_trace"] = getattr(exc, "tool_trace", [])
        record["notes"].append(exc.reason)
    elif isinstance(exc, verdict.DecisionSchemaError):
        record["failure_code"] = exc.code
        record["failure_stage"] = exc.stage
        record["notes"].append(exc.reason)
    elif isinstance(exc, StageTimeout):
        record.update(failure_contract.timeout_record_fields(exc.stage))
        record["tool_trace"] = getattr(exc, "tool_trace", [])
        record["notes"].append("stage timeout: " + str(exc.stage))
    elif isinstance(exc, TimeoutError):
        # 能识别阶段的超时在模型/工具调用点已经标好阶段；走到这里说明来源无法识别，
        # 用通用 TIMEOUT + timeout_stage，**不冒充** RUNNER_TIMEOUT
        record.update(failure_contract.timeout_record_fields())
        record["notes"].append(str(exc))
    elif isinstance(exc, model_client.ModelCallError):
        _record_model_failure(record, exc)
    else:
        record["failure_code"] = "RUNNER_EXCEPTION"
        record["failure_stage"] = "runner"
        record["notes"].append(str(exc))


def _record_model_failure(record, exc):
    """模型阶段的故障分类（协议修订 03）：来源已明确，不再推给运行器。

    - 超时 → `MODEL_TIMEOUT / model`（并填 `timeout_stage`）；
    - 接口已响应但内容为空 / 不是合法 JSON → `INVALID_SCHEMA / model_output`；
    - 其余接口或连接失败 → `MODEL_FAILED / model`。
    """
    if exc.kind == "timeout":
        record.update(failure_contract.timeout_record_fields("model"))
    elif exc.kind in ("empty_content", "bad_json"):
        record["failure_code"] = "INVALID_SCHEMA"
        record["failure_stage"] = "model_output"
    else:
        record["failure_code"] = "MODEL_FAILED"
        record["failure_stage"] = "model"
    # 原始类别留在 notes（不含密钥与完整响应体），便于坏例分析
    record["notes"].append("model_call:%s %s" % (exc.kind, exc))


def run_case(arm, case, route_input, model_factory, executor_factory, budget=4,
             registry_factory=None, agent_model_factory=None,
             checker_factory=None, usage_factory=None):
    """跑一案例的一臂；每次调用都新建模型与执行器（隔离）。

    `registry_factory`：给出证据适配层（`evidence_adapter.EvidenceRegistry`）时，
    工具返回会先做结构校验与事实登记；不给则直接消费注入执行器给的结构（测试替身）。
    `agent_model_factory`：子图内部的模型调用器（带工具）；不传则复用 `model_factory`。
    `checker_factory`：软事实档的轻量一致性校验器；不传则该档按固定路径处理。
    `usage_factory`：`(case_id) -> () -> token 数或 None`，用于采集真实用量。
    """
    started = time.perf_counter()
    allowed = set(case.get("base_fact_ids") or [])
    tokens = None  # 无法获取用量时必须为 None，不能记成 0
    registry = registry_factory(case) if registry_factory else None
    if registry is not None:
        # 基础取数的证据在子图之前就属于本次执行：登记后新事实不会与它撞 id
        registry.seed(facts=case.get("base_facts"), fact_ids=sorted(allowed))
    record = {"failed": False, "notes": [], "payload": None, "stop_code": None,
              "tool_calls": 0, "route": "workflow", "route_reason": None,
              "tool_trace": [],
              "validation_code": None,
              "failure_code": None, "failure_stage": None, "timeout_stage": None}
    try:
        if arm == "A":
            record["payload"] = _workflow_decision(case["case_id"], model_factory,
                                                   allowed)
        elif arm == "C":
            route, reason = routing.decide_route(route_input)
            record["route"] = route
            # 路由原因码要留痕：协议要求给出"被路由到固定路径的原因码"
            record["route_reason"] = reason
            if route == routing.ROUTE_SOFT and checker_factory is not None:
                # 软事实档：跑一次轻量一致性校验；不一致/不确定都安全转入歧义档
                outcome = routing.handle(
                    route_input,
                    statement=case.get("body"),
                    checker=checker_factory(case["case_id"]),
                )
                route = outcome["route"]
                record["route"] = route
                record["route_reason"] = outcome.get("reason_code") or reason
            if route == routing.ROUTE_AMBIGUOUS:
                out = agent_subgraph.run(
                    "ambiguous", allowed,
                    (agent_model_factory or model_factory)(
                        case["case_id"], sorted(allowed)),
                    executor_factory(case["case_id"]), budget=budget,
                    registry=registry,
                )
                record["payload"] = out["payload"]
                record["stop_code"] = out["stop_code"]
                record["tool_calls"] = out["tool_calls"]
                record["tool_trace"] = out.get("tool_trace", [])
                allowed = out["allowed_fact_ids"]
                if out["action"] != "decide":
                    # 没产出自动判定：failed=True，但原因分两类落到 stop_code / failure_code
                    record["failed"] = True
                    if out["stop_code"] in SAFE_STOP_CODES:
                        # 安全停止：原因只落在 stop_code，不进失败分布
                        record["failure_code"] = None
                    else:
                        # 工具失败等：规范化为 failure_code，内部表示不残留
                        record["failure_code"] = out["stop_code"]
                        record["failure_stage"] = "tool"
                        record["stop_code"] = None
            else:
                record["payload"] = _workflow_decision(case["case_id"],
                                                       model_factory, allowed)
        else:
            raise ValueError("未知的臂: " + str(arm))

        decision = None
        if record["failed"]:
            pass  # 已经是安全停止或故障：不再校验输出
        else:
            try:
                decision = asdict(verdict.validate_decision(
                    record["payload"], sorted(allowed),
                ))
            except verdict.DecisionError as exc:
                # 语义错误：只记 validation_code，不进失败原因分布
                record["failed"] = True
                record["validation_code"] = exc.code
                record["notes"].append(exc.reason)
    except Exception as exc:  # noqa: BLE001 - 失败必须留痕，不丢样本
        _record_failure(record, exc)
        decision = None
    latency = int((time.perf_counter() - started) * 1000)
    if usage_factory is not None:
        tokens = usage_factory(case["case_id"])()
    problems = (failure_contract.validate_failure(
        record["failure_code"], record["failure_stage"],
    ) if record["failure_code"] else [])
    for problem in problems:
        # 契约违规本身就是缺陷：留在记录里，不静默吞掉
        record["notes"].append("failure_contract: " + problem)
    return RunRecord(
        case_id=case["case_id"], arm=arm, run_id=_run_id(arm, case["case_id"]),
        route=record["route"], route_reason=record["route_reason"],
        action="decide" if decision else "human_review",
        stop_code=record["stop_code"], tool_calls=record["tool_calls"],
        decision=decision,
        latency_ms=latency, tokens=tokens, failed=record["failed"],
        failure_code=record["failure_code"],
        failure_stage=record["failure_stage"],
        timeout_stage=record["timeout_stage"],
        validation_code=record["validation_code"],
        raw_output=record["payload"], tool_trace=record["tool_trace"],
        notes=record["notes"],
    )


def run_experiment(cases, route_inputs, model_factory, executor_factory,
                   manifest_expected, manifest, problem_checker, budget=4,
                   registry_factory=None, agent_model_factory=None,
                   checker_factory=None, usage_factory=None):
    """跑完整对照。哈希不符直接拒绝，不产生记录。"""
    problems = problem_checker(manifest, manifest_expected)
    if problems:
        raise HashMismatch("Manifest 校验失败: " + "; ".join(problems))
    records = []
    for case in cases:
        for arm in ("A", "C"):
            records.append(asdict(run_case(
                arm, case, route_inputs[case["case_id"]], model_factory,
                executor_factory, budget=budget, registry_factory=registry_factory,
                agent_model_factory=agent_model_factory,
                checker_factory=checker_factory, usage_factory=usage_factory,
            )))
    return records
