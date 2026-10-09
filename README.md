# ticket-triage-agent（项目三，W1 起步）

## 一句话

在复杂工单分诊中，**什么时候固定工作流已经足够，什么时候动态取数的受控 Agent 才产生足够的增量价值？**

先用 discovery gate 判断"动态取数"是否真实存在，再决定是否引入 Agent 子图，并用 A／C 对照验证增量价值。
LangGraph 是手段，不是本项目存在的理由。

## 状态

方案已冻结（v0.2，经两轮外部评审），当前进度 **W1**：底座 + 两个只读工具 + 一条场景纵切（判定先用确定性桩）。
W1 验收的是 **orchestration contract**，不是模型效果；任何效果数字在 W2／W5 之前一律空缺。

完整方案见上一仓库：`inventory-diagnostic-agent/docs/方案草案_工单分诊与受控Agent.md`

## W1 范围（冻结，不再加）

| 项 | 内容 |
|---|---|
| 底座 | 2 张表：`ticket`、`orders`；一个 `pre_triage_view` 取数契约 |
| 工具 | 2 个只读：`get_ticket(ticket_id)`、`get_order(order_no)`，服务端绑定 `session.customer_id` |
| 纵切 | 1 条场景（改写自 frappe/helpdesk #3465）+ 确定性桩判定 + 人工确认 + 审计 |
| 失败路径 | 2 条：数据不存在、工具异常 |
| 交付 | 一条命令复现；证据每条可追；期望值跑之前写进文件 |

## 数据契约（P0，防 label leakage）

- 底座保留 `ticket.current_queue`（真实系统确实有），**但模型与评测只看 `pre_triage_view`**；
- 该视图把 `current_queue` 固定为 `unassigned`（SQL 层强制，不靠自觉）；
- **gold 评测禁止使用既有处置队列。**

## 判失败条件（触发即停，不堆功能）

手动改库才能跑通 / 期望值事后补 / 工具返回决策字段（queue、priority、escalation）/ 加了分诊之外的功能 / 在 W1 就上 LLM 判定（吃了 W3 的范围）。

## 反膨胀规则

要新增任何东西，必须同时说出删掉什么；说不出就默认不加。

## 许可

MIT（见 `LICENSE`）。

## 怎么跑（W1 已验证）

依赖：Python 3.10；`pyproject.toml` 是依赖声明的唯一来源，`requirements.txt`
是从当前环境生成的安装快照（可复现安装用，不手写维护）。

```bash
# 1 建库建表（幂等；库名来自 .env 的 DB_NAME，默认 ticketdesk）
python scripts/migrate.py

# 2 种子数据 + 工具契约证据 + W1 纵切
python scripts/seed.py
python scripts/repro.py           # 工具契约证据：正例 / 两类失败 / 跨客户 / 缺键 / 无决策字段
python scripts/vertical_slice.py  # 纵切 harness：gold 先加载 → 桩判定 → 人工确认 → 审计，末尾给 PASS/FAIL

# 3 W2 pilot（规则分桶）
python scripts/discovery_pilot.py

# 4 测试
pytest tests -q
```

`scripts/*.py` 都会自己把 `src` 加进 `sys.path`，不需要手工设 `PYTHONPATH`；
`.env` 自行从 `.env.example` 复制并填值，密钥不入库。

## 检查规范（只写实际执行的检查）

| 检查 | 约定 |
|---|---|
| `pytest tests -q` | 完整回归，必须通过 |
| `ruff check src tests` | 强制静态检查。**范围仅限这两个路径**，不能据此宣称整仓 Ruff clean |
| 本轮新增或修改的脚本 | 单独纳入检查（如 `ruff check scripts/derive_agent_needed_labels.py`），不继承旧脚本的告警盲区 |
| `black --check` | **不作为强制验收门槛**：本仓库没有做过全仓格式化，`[tool.black]` 只是可选的排版配置 |

已知残留：`scripts/generate_cases.py`、`scripts/repro.py` 有 3 条历史 ruff 告警
（早于本规范，未清理），因此"Ruff clean"只对 `src tests` 成立。

## A/C 实验的标签派生

冻结的 Gate 记录 `experiments/discovery/gate_v1_decision.json` **不是合法 JSON**
（`notes` 数组里两个字符串字面量之间缺一个逗号），但它仍是不能改的原始证据。
正式对照用派生标签件，派生过程可复现：

```bash
python scripts/derive_agent_needed_labels.py          # 生成派生件
python scripts/derive_agent_needed_labels.py --check  # 校验派生件与重新派生一致
```

派生件：`experiments/ac_v1/derived/agent_needed_labels_v1.json`（50 条案例的布尔标签
+ 3 个动态取数模式）；脚本先核对原件哈希、断言缺陷恰好出现一次，修正只发生在内存里，
**不写回原件**。派生件与脚本的哈希都进正式 Manifest。

## 业务世界与实验库（正式对照的前提）

三条动态取数模式要查 `refund` / `kb_article` / `order_line` 与历史处置记录，仓库里
原本没有生成过这些数据（表为空）。因此新增两个脚本：

```bash
python scripts/derive_business_world.py   # 派生构造业务世界（不读 gold）
python scripts/load_experiment_db.py      # 加载进隔离实验库（默认 ticketdesk_ac_v1）
python scripts/ac_smoke.py                # 三个模式各 1 条的真实接入冒烟
```

- 世界文件 `experiments/ac_v1/derived/business_world_v1.json` 明确标注为**构造数据**；
  它只按 `business_state` / 冻结正文等业务情境生成，**不读** `expected_queue`、
  `expected_priority`、`agent_needed`；时间字段是相对偏移，加载时换算成绝对时间。
- 实验库与日常库（`DB_NAME`）**必须不同名**，否则加载器直接拒绝；日常库不受影响。
- 真实接入冒烟只验证链路（模型调用、MySQL 取数、适配、引用、错误记录、token/耗时），
  **不参与业务结论**。

模型接入固定为 DeepSeek 官方 API：模型 `deepseek-flash`、base_url
`https://api.deepseek.com`、`temperature=0`、`thinking={"type":"disabled"}`、
`response_format={"type":"json_object"}`；密钥只从环境变量 `DEEPSEEK_API_KEY` 读，
不进代码、不进 Manifest、不打印。

## 目录

```
migrations/   底座 schema（ticket / orders / pre_triage_view）
src/ticketdesk/  config（配置）· db（连接）· tools（两个只读工具）· pipeline（纵切）
scripts/       migrate · seed · repro · vertical_slice · discovery_pilot
tests/         工具契约测试（8 条，会话级 fixture 自己初始化数据）
fixtures/      gold（跑前冻结）· discovery（规则表 + pilot case）
experiments/   discovery 结果与作废记录
```
