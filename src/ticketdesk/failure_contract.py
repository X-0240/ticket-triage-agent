"""失败分类契约（唯一事实来源）：错误码 ↔ 阶段的允许映射与必填约束。

冻结依据：A/C 协议修订 01（`a59f4a76`）第 1、2 节。这是**实现已冻结口径**，
不新增协议修订。

两条必须守住的区别：

- `model` 与 `model_output`：前者是**调用阶段**，后者是**结果校验阶段**；
- `tool` 与 `tool_result`：同上。

字段语义（与 `ac_runner` 的注释一致）：

- `stop_code`：系统**为什么停止**（安全停止原因）；
- `failure_code` + `failure_stage`：**发生了什么故障、发生在哪一侧**；
- `failed`：本次自动判定**是否完成**，**不代表发生故障**，不得据它推导技术失败率。
"""

ALLOWED_STAGES = frozenset({
    "model_output",
    "tool_result",
    "tool",
    "model",
    "runner",
    "unknown",
})

# 失败码 → 允许的阶段集合。`INVALID_SCHEMA` 必须带输出侧阶段，
# 不允许写成裸调用阶段（model / tool）。
FAILURE_MAP = {
    "INVALID_SCHEMA": frozenset({"model_output", "tool_result"}),
    "TOOL_FAILED": frozenset({"tool"}),
    "TOOL_TIMEOUT": frozenset({"tool"}),
    "MODEL_TIMEOUT": frozenset({"model"}),
    "RUNNER_TIMEOUT": frozenset({"runner"}),
    "TIMEOUT": frozenset({"unknown"}),
    "RUNNER_EXCEPTION": frozenset({"runner"}),
}

# 语义校验失败（如 queue 值非法）保留各自的具体错误码，**不得**并入 INVALID_SCHEMA，
# 也**不得写入 `failure_code`**——它们属于判定校验结果，走独立字段 `validation_code`。
SEMANTIC_CODES = frozenset({
    "QUEUE_INVALID",
    "PRIORITY_INVALID",
    "EVIDENCE_EMPTY",
    "EVIDENCE_UNKNOWN",
    "AUTO_SEND_FORBIDDEN",
})

# 语义校验错误的存放字段：与 failure_code 物理隔离，避免混进失败原因分布
VALIDATION_FIELD = "validation_code"

# 通用超时的三元组：`failure_stage` 满足故障分类契约，`timeout_stage` 记录超时来源，
# 两者职责不同、值恰好相同也必须**同时**填写；只填一个视为记录不完整。
GENERIC_TIMEOUT_CODE = "TIMEOUT"
GENERIC_TIMEOUT_STAGE = "unknown"


def timeout_record_fields(timeout_stage=None):
    """构造超时的记录字段（唯一出口，避免各调用点各填一半）。"""
    stage = timeout_stage or GENERIC_TIMEOUT_STAGE
    if stage == GENERIC_TIMEOUT_STAGE:
        # 来源无法识别：通用码 + 两个阶段字段同时填 unknown
        return {
            "failure_code": GENERIC_TIMEOUT_CODE,
            "failure_stage": GENERIC_TIMEOUT_STAGE,
            "timeout_stage": GENERIC_TIMEOUT_STAGE,
        }
    # 能识别来源：阶段化错误码，timeout_stage 与 failure_stage 一致记录来源
    code = "MODEL_TIMEOUT" if stage == "model" else "TOOL_TIMEOUT"
    return {
        "failure_code": code,
        "failure_stage": stage,
        "timeout_stage": stage,
    }


def stage_required(code):
    """该错误码是否强制要求 `failure_stage`。"""
    return code in FAILURE_MAP


def validate_failure(code, stage):
    """校验 (错误码, 阶段) 组合；返回问题清单，空表示合法。

    规则：
    1. 错误码必须在 `FAILURE_MAP` 或 `SEMANTIC_CODES` 内；
    2. `FAILURE_MAP` 里的码**必须**给阶段，且阶段属于该码的允许集合；
    3. `INVALID_SCHEMA` 不允许用 `model` / `tool` 这类调用阶段冒充；
    4. 语义错误码（`SEMANTIC_CODES`）不属于故障分类，不应带 `failure_stage`。
    """
    problems = []
    if code in SEMANTIC_CODES:
        # 语义错误不是故障码：不得写入 failure_code，应放进 validation_code
        return [
            "%s 属于语义校验错误，不得作为 failure_code 使用；"
            "请写入 %s 字段" % (code, VALIDATION_FIELD)
        ]
    if code not in FAILURE_MAP:
        return ["未知 failure_code: " + str(code)]
    if not stage:
        return ["%s 必须带 failure_stage" % code]
    if stage not in ALLOWED_STAGES:
        return ["failure_stage 不在允许集合内: " + str(stage)]
    if stage not in FAILURE_MAP[code]:
        problems.append(
            "%s 的 failure_stage 只能是 %s，实际 %s"
            % (code, sorted(FAILURE_MAP[code]), stage)
        )
    return problems
