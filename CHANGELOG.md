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
