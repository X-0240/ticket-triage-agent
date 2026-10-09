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

## v0.2.2（批次二：业务世界 + 真实接入，2026-10-10）

正式 A/C 的两个前提补齐：① 三条动态取数模式要查的退款/政策/商品/历史数据，
仓库里从来没有生成过（`refund` / `kb_article` / `order_line` 全为空）；
② 真实模型与真实工具还没有接入代码。本批只补这两件事，**仍未跑正式对照**。

| 项 | 内容 | 证据 |
|---|---|---|
| 业务世界 | 按业务情境确定性构造 50 条案例的世界（ticket 50 / orders 40 / order_line 40 / shipment 20 / refund 15 / kb_article 6），明确标注构造数据 | `scripts/derive_business_world.py`、`experiments/ac_v1/derived/business_world_v1.json` |
| 隔离实验库 | 加载进 `ticketdesk_ac_v1`（可用 `DB_NAME_AC` 覆盖），与日常库同名即拒绝；加载后核对行数、主外键、工具可查性 | `scripts/load_experiment_db.py` |
| 模型接入 | DeepSeek 官方 API：`deepseek-flash`、`temperature=0`、`thinking=disabled`、JSON 输出；空内容按输出结构失败处理 | `src/ticketdesk/model_client.py` |
| 提示词 | 固定工作流判定与子图取证两套提示词，含 json 契约与示例；**不读 gold** | `src/ticketdesk/prompts.py` |
| 真实接入 | 基础取数走真实工具、路由输入按规则 v1 确定性计算、tools 执行器与模型工厂可注入、token 用量回传运行记录 | `src/ticketdesk/ac_harness.py` |
| 冒烟脚本 | 三个模式各 1 条，跑通链路并落盘 runs.jsonl / manifest.json / smoke.md | `scripts/ac_smoke.py` |

### 本批定位到的接口缺口（已修）

1. **"必要事实齐全"不能用全局词汇表判断**：`rule_status()` 只判断"工具理论上能不能取到"，
   与"这次执行实际取到了没有"是两件事。若不区分，缺订单号的案例会被误判为事实齐全。
   修法：路由输入按本次执行实际取到的事实类别（`FACT_CLASS`）判断，缺一类就不进硬事实档。
2. **唯一候选 + 正文在问政策**：D-36~D-40 的唯一候选来自结构化事实，正文却在问保修。
   修法：正文出现政策/商品类关键词（保修、质保、配件、换新…）时，唯一候选也必须先做
   轻量一致性校验 → 进软事实档，而不是直接按硬事实放行。
3. **软事实档此前没有真实校验器**：运行器只区分"歧义档"与"其余"，软档等价于固定路径。
   修法：运行器接入 `checker_factory`，校验结果 `INCONSISTENT/UNCERTAIN` 安全转入歧义档。
4. **token 用量恒为 None**：运行记录没有采集入口。修法：新增 `usage_factory`，
   真实用量回传记录；拿不到仍是 None，不记 0。

### 已知边界

- 冒烟需要本机设置 `DEEPSEEK_API_KEY`；未设置时脚本**明确失败**而不是空跑；
- 模型调用失败（HTTP / 空内容 / 坏 JSON）在冻结契约里没有独立错误码，当前按
  `RUNNER_EXCEPTION / runner` 记录，并把真实类别写进 `notes`（如 `model_call:http_402`）；
  若要给它独立错误码，需要新的协议修订；
- 冒烟数字（事实条数、档位）只证明链路可用，**不是业务效果证据**。

## v0.2.3（协议修订 03：模型失败分类，2026-10-10）

真实模型接入必须先解决一处错误分类：模型接口返回 401/402/429/5xx 时被记成
`RUNNER_EXCEPTION / runner`，等于把明确的模型阶段故障推给运行器。按评审决定新增
**协议修订 03**（`experiments/ac_v1/protocol_amendment_03.md`），原协议与修订 01/02 不改。

| 情况 | 记录 |
|---|---|
| 模型 API 调用失败（401/402/429/5xx、连接失败、缺密钥） | `MODEL_FAILED / model` |
| 模型调用超时 | `MODEL_TIMEOUT / model`（并填 `timeout_stage`） |
| 接口已响应但内容为空 / 非法 JSON / 结构不合法 | `INVALID_SCHEMA / model_output` |
| 来源无法识别的超时 | `TIMEOUT / unknown` |
| 运行器自身未分类异常 | `RUNNER_EXCEPTION / runner` |

落地改动：

- `src/ticketdesk/failure_contract.py`：`FAILURE_MAP` 增加 `MODEL_FAILED → {model}`；
- `src/ticketdesk/model_client.py`：超时单独归为 `timeout` 类别（不再混进 `network`）；
- `src/ticketdesk/ac_runner.py`：模型阶段故障统一走 `_record_model_failure()`，
  `RUNNER_EXCEPTION` 只留给运行器自身确实无法归类的异常；原始类别写进 `notes`
  （`model_call:http_402`），不含密钥与完整响应体；
- `src/ticketdesk/evidence_manifest.py`：Manifest 增加 `protocol_amendment_03_hash`，
  `verify_files()` 一并核验（四份协议文件四个哈希）。

### 边界

- 本批不改路由规则、提示词、预算与停止条件，也不新增 Agent 能力；
- 生成参数按评审决定固定为 `thinking=disabled` + `temperature=0`（思考模式下
  temperature 不生效，若两臂模式不同就不能声称控制了随机性）；A、C 两臂共用同一配置；
- 仍未跑正式对照：真实冒烟需要本机设置 `DEEPSEEK_API_KEY`。

## v0.3.0（正式 A/C 一轮结果，2026-10-10）

唯一一轮冻结对照已跑完：`experiments/ac_v1/run_20261010T031551/`，
执行提交 `6e415d82`（工作区干净），模型 `deepseek-flash`，实验库
`ticketdesk_ac_v1`（加载于 2026-10-10 03:00:26），129 次真实模型调用。

### 结果（队列为主输出；gold 队列只覆盖 20/50 条案例）

| 指标 | A（固定工作流） | C（级联 + 受控 Agent） |
|---|---|---|
| 有效判定覆盖率 | 48/50 = 0.96 | 42/50 = 0.84 |
| 队列准确率（仅有效判定） | 19/19 = 1.0 | 20/20 = 1.0 |
| Agent-needed 子集（15 条）队列准确率 | 5/5 | 5/5 |
| 无判定（转人工） | 2（1×SSL、1×网络） | 8（全部 `NO_NEW_EVIDENCE`） |
| 工具调用 | 0 | 27 次（每次子图运行恰好 1 次） |
| tokens（合计） | 35,905 | 100,270 |
| 延迟（均值 / p95） | 998 / 1262 ms | 1363 / 2499 ms |

配对（20 条有 gold 队列的案例）：改善 1、回退 0、持平 19。**那唯一的"改善"（D-02）
来自 A 臂一次 TLS 失败没有产出判定，不是动态证据带来的增益**，按修订 02 不能算 Agent 价值。

路由：Agent-needed 15/15 全部进子图（召回 1.0）；非 Agent-needed 35 条里有 12 条
（34.3%）也进了子图 → 级联在不需要的案例上照样付 Agent 成本。
证据归因：C 臂 19 条取到新证据并给出判定的案例，**19/19 都引用了新事实**
（说明"证据可见性"修复生效）。

### 按修订 02 的项目定位决定

规则 3 要求"跨多个案例、多个预定义模式的可追溯改善"。本轮**没有**观察到：
三个模式里没有任何一个 C 优于 A；Agent-needed 子集两臂完全一致；C 覆盖率更低、
tokens 约为 A 的 2.8 倍、还多付 12 条不必要的子图调用。按规则 4：

- **停止扩展 Agent 路线**，项目定位改为**"证据驱动的工单分诊工作流"**；
- 结论如实写为"**本轮探索性实验未能建立 Agent 的增量价值**"，
  **不写**"已证明 Agent 完全没有价值"（单轮、50 条构造世界）。

### 本轮暴露的两处问题

1. **SSL 错误被记成运行器故障**：A 臂 D-02 的 `[SSL: SSLV3_ALERT_BAD_RECORD_MAC]`
   冒到运行器，被记 `RUNNER_EXCEPTION / runner`；按修订 03 应记
   `MODEL_FAILED / model`。已修 `model_client`（捕获 `ssl.SSLError`）并加测试。
   **这是一处标注缺陷，不改变上面任何比例，因此按规则 2 不重跑**；
   冻结产物保留当时的原始记录，缺陷只在 CHANGELOG 与本条里披露。
2. **优先级指标不可解释**：gold 为 P0 的 5 条模型给 P1、gold 为 P1 的 3 条给 P2
   （系统性低一档）。根因是提示词里**没有给优先级政策**（SLA 临近→高优先级、
   退款诉求→次高），两臂都只能靠猜。所以队列那一半结果可用，
   **优先级那一半本轮无效**，不能拿它评价任一条臂。

### 记录口径的已知缺口

- 只记了 token 总量（`prompt_tokens + completion_tokens`），**没有分开记输入与输出**，
  因此不能从产物直接算出准确费用（官方对输入/输出、缓存命中分别计价）；
- 8 条 `NO_NEW_EVIDENCE` 的 gold `expected_handoff` 都是 `human_review`，
  与 A 臂"有判定但 needs_human=True"实际同去人工——覆盖率把 C 这 8 条记成"缺失"，
  是口径差异，不是业务错误。

## v0.3.1（公开发布准备，2026-10-10）

项目进入收尾与求职材料阶段，功能开发停止，只做公开发布所需的整理。

### 依赖声明收敛

`requirements.txt` 原来是本机环境导出的安装快照（75 行，含 LangGraph、FastAPI、pandas
等本项目**从未导入**的包）。这种快照放进公开仓库会误导读者，也让"技术栈"无法核对。
现在拆成两份，按代码实际导入核对：

- `requirements.txt`：运行依赖，只有 `PyMySQL` 与 `python-dotenv`，其余全是标准库；
- `requirements-dev.txt`：`pytest` 与 `ruff`。

旧快照不再保留为文件（需要时可以从 git 历史里取回）。

### 公开发布前的扫描

按"推送公开仓库前先扫描"的规则，对**全部 24 个提交**（不只当前工作树）扫描：
本机绝对路径、机器名、`sk-`／`ghp_`／`gho_` 形态令牌、私钥块、邮箱串、密钥赋值。
结果：全部无命中。唯一的 `DB_PASSWORD` 命中是 `src/ticketdesk/config.py` 里读取环境变量
的源码行，`.env.example` 的值为空，`.env` 从未被跟踪且已被忽略。

已知事项：提交作者为 `X-0240 <1601317784@qq.com>`（GitHub 关联邮箱）与
`codex <codex@local>`，公开后这些元数据可见；不改写历史。
