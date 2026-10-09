# 更新日志

## v0.1.0（W1，2026-10-09）

W1 只做底座与管道，**不验收模型效果**。交付：两张表 + 取数视图、两个只读工具、
确定性桩判定、证据包（fact_id）、人工确认（before/after）、审计时间线（区分事实发生与系统记录）。

| 项 | 内容 | 证据 |
|---|---|---|
| 底座 | `ticket`、`orders` 两张表；`pre_triage_view` 把 `current_queue` 固定为 `unassigned` | `migrations/001_schema.sql` |
| 防 label leakage | 模型与评测只能读视图，底座真值（如"履约组"）读不到 | `scripts/repro.py`、`tests/test_tools_contract.py` |
| 工具 | `get_ticket`、`get_order`：按键查询、服务端绑定 `session.customer_id`、返回事实指针 | `src/ticketdesk/tools.py` |
| 纵切 | 取数 → 证据包（fact_id）→ 桩判定 → 人工确认 → 审计，一条命令输出 PASS/FAIL | `scripts/vertical_slice.py` |
| gold | 跑之前冻结、脚本只读：`fixtures/gold/T-1001.json` | 同上 |

### 已修的问题（W1 内）

1. **建库报 `Unknown database 'ticketdesk'`**：`db.connect(database=None)` 把 `None`
   当成"用默认库"，建库阶段就去连还不存在的库。修法：用哨兵值区分"未传参"与"显式 None"。
2. **决策字段扫描误报**：早期扫整段 `repr`，把合法的 `current_queue` 字段名判成越界。
   修法：递归扫**键名**并白名单放行 `current_queue`（它本身就是防泄漏证据）。
3. **seed 参数名不一致**：调用用 `days=`、函数签名是 `days_ago=`，建库后直接报 TypeError。
   修法：统一参数名。
4. **脚本 `ModuleNotFoundError: ticketdesk`**：脚本没把 `src` 加进 `sys.path`。
   修法：每个入口脚本自己插入 `src`（项目二的既有做法）。
5. **基础设施故障被降级成业务缺席**：`shipment` 表尚未建时，SQL 异常被 `except`
   吞成 `NO_SHIPMENT_FACT`，于是"查不了"被解释成"这单没有发货事实"，会直接污染
   discovery 分桶（把"工具没建完"算成"业务上没有事实"）。修法：**域内缺席与基础设施错误
   彻底分开**——查询成功但无行 → `NO_SHIPMENT_FACT`；查询本身失败 → 抛 `ToolError`。
   教训：「查询成功但无记录」与「查询失败」是两个不同的业务语义，不能共用同一个降级值。
   证据：`tests/test_tools_contract.py::test_shipment_domain_absence_when_no_row`
   与 `::test_shipment_infrastructure_error_raises`。

### 边界

- W1 的桩只证明"系统能容纳一个被认为有歧义的 case"，**不判定它是否真的 Agent-needed**（W2 的事）；
- 第一层止损（discovery gate）与 A/C 对照都在后续周次，未跑之前任何效果数字空缺。

## v0.2.0（A/C 实验基础设施，2026-10-10）

把 A/C 协议（`experiments/ac_v1/protocol.md` + 修订 01 + 修订 02）落成可执行、可验证的代码：
失败分类、Manifest 三份协议哈希、评分汇总、端到端自检。**本批不接真实模型、不跑正式对照、
不新增 Agent 能力**，因此没有任何业务效果结论。

| 项 | 内容 | 证据 |
|---|---|---|
| 证据适配层 | 工具返回 → 统一证据格式；结构校验 + 事实身份 + 一次执行内稳定的 `fact_id` | `src/ticketdesk/evidence_adapter.py`、`tests/test_evidence_adapter.py` |
| 失败分类 | 错误码 ↔ 阶段唯一映射；`INVALID_SCHEMA` 分 `model_output` / `tool_result`；语义错误走 `validation_code` | `src/ticketdesk/failure_contract.py`、`src/ticketdesk/verdict.py` |
| 运行记录 | 新增 `failure_stage` / `timeout_stage` / `validation_code` / `route_reason` / `raw_output` | `src/ticketdesk/ac_runner.py` |
| Manifest | 三份协议文件哈希分别记录，`verify_files()` 逐个读盘核对 | `src/ticketdesk/evidence_manifest.py`、`tests/test_manifest.py` |
| 评分汇总 | `case_metrics.jsonl` / `summary.json` / `report.md`；覆盖率与条件准确率分开、产物不可覆盖 | `src/ticketdesk/ac_scoring.py`、`tests/test_ac_scoring.py` |
| 端到端自检 | 哈希关 → 两臂记录覆盖 → 停止/失败码映射 → 评分 → 拒绝覆盖 | `tests/test_ac_e2e_selfcheck.py` |

### 已修的问题（本批）

1. **工具结果契约错位（会让真实模型路径直接失效）**：工具返回的是
   `{"tool","found","ref","facts","error"}`，**没有顶层 `fact_ids`**；子图却按
   `{"fact_ids","facts"}` 消费。根因是两头各自假定契约。修法：新增唯一适配层
   （`evidence_adapter`）负责结构校验、事实登记与 `fact_id` 分配。
2. **裸超时按"捕获位置"分类**：模型调用点没有 try/except，工具侧的 `except Exception`
   把裸 `TimeoutError` 吃成 `TOOL_FAILED`。修法：在**调用点**就近标阶段
   （`StageTimeout("model")` / `StageTimeout("tool")`），来源无法识别时才用
   `TIMEOUT` + `timeout_stage="unknown"`；`RUNNER_TIMEOUT` 不当作兜底。教训：
   异常的捕获位置不等于故障的发生位置。
3. **"是否取得新证据"依赖会漂移的编号**：适配层若每次调用重新从 `fact_01` 编号，
   重复事实会被当成新证据，`NO_NEW_EVIDENCE` 永不触发。修法：一次执行内的事实注册表，
   同一条事实复用同一个 `fact_id`，新事实占用未使用的编号。
4. **A 臂的判定节点拿不到基础证据**：`_workflow_decision` 用空列表调用模型，
   等于让固定工作流"看不到证据"，对照会失效。修法：把本次执行的基础 evidence id
   传给判定节点，并加回归测试。
5. **`EvidenceRegistry` 引用了未初始化的 `_seen_ids`**：`new_fact_ids` 恒为空，
   该字段语义实际未生效。修法：改为显式维护"本次执行已知 id 集合"。

### 已登记、未修的问题

1. **`experiments/discovery/gate_v1_decision.json` 不是合法 JSON**：`notes` 数组里
   两个字符串字面量之间漏了逗号（Python 式的隐式拼接在 JSON 里非法），
   `json.load()` 会直接报 `Expecting ',' delimiter: line 36`。它是冻结证据，
   **本轮不改**；评分层因此把 `agent_needed` 标签做成外部入参，而不是自己去解析该文件。
   正式运行前需要决定：单独出一份机器可读的标签派生件，还是先修冻结件语法（需明确授权）。
2. **`scripts/` 有 3 条 ruff 告警**（`generate_cases.py` 的 I001/F401、`repro.py` 的 F401），
   都是本批之前提交的代码，未在本次一并清理，避免把无关重排混进本批 diff。

### 边界

- 本批只证明**框架**可信（哈希关、覆盖、失败留痕、统计口径），**不证明 Agent 有业务增益**；
- 是否保留 Agent，仍由正式 A/C 对照（一批、只跑一轮）按修订 02 的止损规则决定；
- 正式运行产物写入独立目录，已存在即拒绝覆盖。

## v0.2.1（批次二起步：标签派生与检查规范，2026-10-10）

正式 A/C 需要的 `agent_needed` 标签来自冻结 Gate 记录，而那份记录不是合法 JSON。
按评审决定：**不改原件**，改为一次可复现的派生；同时把项目的检查规范改成如实描述。

| 项 | 内容 | 证据 |
|---|---|---|
| 派生脚本 | 核对原件哈希 → 断言缺陷恰好出现一次 → 内存内修正 → 标准解析 → 生成标签 | `scripts/derive_agent_needed_labels.py` |
| 派生件 | 50 条案例布尔标签 + 15 条 agent_needed + 3 个动态取数模式 | `experiments/ac_v1/derived/agent_needed_labels_v1.json` |
| Manifest | 新增 `agent_needed_labels_hash`、`label_derivation_script_hash`，`verify_files()` 一并核对 | `tests/test_manifest.py` |
| 标签消费 | `load_labels()` 核对覆盖（缺失/重复/多余即报错） | `src/ticketdesk/ac_scoring.py`、`tests/test_label_derivation.py` |
| 检查规范 | 明确 `ruff check src tests` 为强制项、Black 不作门槛 | `README.md`、`pyproject.toml` |

### 已修的问题（本批）

1. **哈希对换行敏感**：直接对原始字节算 SHA-256，同一份内容在 CRLF 与 LF 检出下会得到
   两个哈希，`verify_files()` 会报假漂移（本仓库 `inputs_50.json` 在盘上是 CRLF，
   其余冻结件是 LF，混在一起更明显）。修法：`sha_of()` 与派生脚本都按 LF 归一化后计算，
   派生件同时记录原始字节值 `sha256_raw_bytes` 备查。
2. **派生脚本首次运行就暴露"缺陷不止一种形态"**：第三个动态模式是
   `（D-36~D-40，唯一候选与正文语义冲突）`，区间后面还带说明文字，按"区间必须在末尾"
   解析会失败。修法：允许区间后带尾巴，并把尾巴作为 `note` 原样保留。

### 边界

- 原件 `gate_v1_decision.json` 保持原样（哈希锁死，改动即失败），派生件是**新增产物**；
- 本批仍**没有**跑正式 A/C，也没有真实模型接入，因此没有任何业务效果结论。
