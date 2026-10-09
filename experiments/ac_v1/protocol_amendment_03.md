# A/C 协议修订 03：模型调用失败的分类口径

- **关联原协议**：`experiments/ac_v1/protocol.md`（冻结 `8484f5fb`）
- **关联修订**：`protocol_amendment_01.md`（`a59f4a76`）、`protocol_amendment_02.md`（`db3d3429`）
- **生效版本**：`ac_v1 + amendment_01 + amendment_02 + amendment_03`；**首次正式运行前生效**
- **为何新增**：真实模型接入后，模型接口的故障会被记成 `RUNNER_EXCEPTION / runner`。
  接口返回 402/401/429/5xx 与"运行器自身抛异常"不是同一件事，来源已经明确就不该推给运行器——
  这与之前纠正裸 `TimeoutError` 的原则一致（**捕获位置 ≠ 故障来源**）。

## 1 唯一新增的错误码

| 情况 | `failure_code` | `failure_stage` |
|---|---|---|
| 模型 API 调用失败、非超时（401/402/429/5xx、连接失败等） | `MODEL_FAILED` | `model` |
| 模型调用超时 | `MODEL_TIMEOUT` | `model` |
| 接口已响应，但内容为空、不是合法 JSON 或结构不合法 | `INVALID_SCHEMA` | `model_output` |
| 来源确实无法识别的超时 | `TIMEOUT` | `unknown`（并填 `timeout_stage`） |
| 运行器自身的未分类异常 | `RUNNER_EXCEPTION` | `runner` |

其余既有映射（`TOOL_FAILED` / `TOOL_TIMEOUT` / `INVALID_SCHEMA / tool_result` /
`RUNNER_TIMEOUT`）与"安全停止只记 `stop_code`、执行失败只记 `failure_code`"的分离规则
**全部保持不变**。

## 2 两条实现纪律

1. **不得用 `RUNNER_EXCEPTION` 兜底有明确来源的故障**：只要故障发生在模型阶段、
   工具阶段或结果校验阶段，就必须用上表对应的码；`RUNNER_EXCEPTION` 只留给
   运行器自身确实无法归类的异常。
2. **超时与失败分开**：模型侧的 `TimeoutError` 记 `MODEL_TIMEOUT`，
   不能用 `MODEL_FAILED` 或 `TIMEOUT` 顶替。

## 3 边界（本修订不改变的东西）

- 不新增 Agent 能力，不改变任何提示词、预算、停止条件或路由规则；
- 不改变失败样本的保留规则：错误案例仍留在样本里，并按安全转人工计入结果；
- `failure_code` 与 `validation_code` 仍然分离：模型输出**结构**问题进
  `failure_code`，**取值**问题（队列/优先级非法等）仍只进 `validation_code`。

## 4 实现说明（落地记录，便于复核）

- 本机配置类问题（例如缺 `DEEPSEEK_API_KEY`）不产生 API 响应，但它同样意味着
  "模型阶段拿不到输出"，因此按 `MODEL_FAILED / model` 记录，并在 `notes` 写明
  `model_call:missing_key`，不与运行器自身异常混记；
- `notes` 里保留原始类别（`http_402` / `network` / `empty_content` / `bad_json`），
  便于坏例分析；密钥、请求头与完整响应体**不写进任何记录**。
