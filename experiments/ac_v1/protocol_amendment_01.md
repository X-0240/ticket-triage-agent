# A/C v1 协议修订 01：失败码与停止原因口径

- **关联原协议**：`experiments/ac_v1/protocol.md`，冻结提交 `8484f5fb`
- **本修订提交**：见 git log 中 `docs(experiment): amend A/C v1 protocol (failure codes)`
- **生效版本**：`ac_v1 + amendment_01`；**首次正式运行前生效**
- **为何不覆盖原文件**：原协议是冻结件，后续运行者需要能看出"原协议约定了什么、后来补充了什么"；
  正式 A/C 尚未启动，因此本次无需作废旧结果，只做口径补充。

## 1 两类信息必须分开记录

| 类别 | 取值 | 含义 |
|---|---|---|
| **安全停止原因**（`stop_code`） | `BUDGET_EXHAUSTED`、`NO_NEW_EVIDENCE`、`REPEATED_CALL` | 系统**为什么停止继续尝试**（有界、可解释） |
| **执行/输出失败**（`failure_code`） | `TOOL_FAILED`、`TOOL_TIMEOUT`、`MODEL_TIMEOUT`、`RUNNER_TIMEOUT`、`INVALID_SCHEMA`、`RUNNER_EXCEPTION` | **具体发生了什么故障** |

**超时按阶段区分**：运行器能识别阶段时必须分开记
`TOOL_TIMEOUT`（工具调用超时）/ `MODEL_TIMEOUT`（模型调用超时）/
`RUNNER_TIMEOUT`（整次运行超时）。只有无法可靠识别阶段时，才用统一 `TIMEOUT`，
并在结构化字段里补 `timeout_stage`。

## 2 避免同一原因重复计数

- 预算耗尽**只记在 `stop_code`**，汇总时计入"安全停止原因分布"；
  **不再**为了让它进失败统计而在 `failure_code` 里重复记一次。
- 工具执行异常既可能是停止原因也可能是失败：本协议约定 **`failure_code` 记故障类型**
  （如 `TOOL_FAILED`），`stop_code` 留空；汇总时按 `failure_code` 进失败分布。
- 一句话原则：**协议、运行记录、汇总逻辑三者对同一原因的归属必须一致**，
  否则 `failure-reason distribution` 不可信。

## 3 Manifest 要求

执行清单必须**同时记录两份文件的哈希**：`protocol.md`（`protocol_hash`）与
本修订件（`protocol_amendment_hash`），并声明执行口径为 `ac_v1 + amendment_01`。

## 4 本轮测试收紧（按此执行）

1. 原测试**改名**为 `test_tool_execution_failure_is_recorded`，只声明覆盖"工具执行失败"，
   不再暗示覆盖超时与预算耗尽；
2. **新增超时测试**：验证运行器的**真实超时处理路径**会留下完整记录
   （而不是只验证某处能抛 `TimeoutError`）；
3. **新增运行器级预算耗尽测试**：验证子图的停止原因能正确传递到 `RunRecord.stop_code`，
   而不只依赖已有的子图单元测试。

## 5 与评分汇总的衔接

汇总层必须**分开报告**：

- **安全转人工率**（最终处理结果）
- **安全停止原因分布**（`stop_code` 各值计数）
- **失败原因分布**（`failure_code` 各值计数）

**缺失输出的披露要求（写死）**：缺失输出**不等于**案例不存在，
不得只对"成功输出的案例"算准确率却不披露缺了多少。汇总里必须同时给出三样：

1. **保留案例记录**：每个冻结案例（A、C 各一条）在 `case_metrics.jsonl` 里都有明确状态，
   失败或无数值判定也要留行；
2. **分母与缺失数分别披露**：准确率要写明"分母是多少、其中多少条缺失/无效"，
   不能只给一个百分比；
3. **输出覆盖率**：单列 `output_coverage = 有有效判定的案例数 / 冻结案例总数`。
