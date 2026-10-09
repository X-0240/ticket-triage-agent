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

## 目录

```
migrations/   底座 schema（ticket / orders / pre_triage_view）
src/ticketdesk/  config（配置）· db（连接）· tools（两个只读工具）· pipeline（纵切）
scripts/       migrate · seed · repro · vertical_slice · discovery_pilot
tests/         工具契约测试（8 条，会话级 fixture 自己初始化数据）
fixtures/      gold（跑前冻结）· discovery（规则表 + pilot case）
experiments/   discovery 结果与作废记录
```
