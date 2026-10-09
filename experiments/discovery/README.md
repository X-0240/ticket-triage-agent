# discovery 记录

## 版本与作废规则（评审冻结口径）

规则表冻结后原则上不可改；确需改 → **新版本号 + 旧结果标 INVALID + 全量重跑**。
历史结果一律保留，不覆盖。

| 版本 | 规则 hash | 状态 | 说明 |
|---|---|---|---|
| v1-draft | `b4fa659293ce2cb5` | **INVALIDATED**（2026-10-09） | pilot 首跑暴露三个口径问题：R-01 依赖取不到的事实（发货）、`output=null` 与分桶语义冲突、桶与期望值的对应关系未定义 |
| v1 | 见 `pilot_v1_*.json` 的 `rules_hash` | pilot 修订版 | 修订内容：`required_facts` + `UNEXECUTABLE`；`effect=CANDIDATE/UNDECIDABLE`；队列归属与人工接管拆成 `expected_queue` / `expected_handoff`；分桶只由执行器算 |

### 第二次 INVALIDATED：baseline 前置条件未满足（2026-10-09）

第二次跑（hash `c62169b620ebb867`）也不是因为修订错，而是发现 **discovery 的 baseline
前置条件尚未满足**：规则表里最像业务的 R-01 依赖发货事实，而 W1 只有两个工具，
取不到发货 → R-01 一直是 `UNEXECUTABLE` → `UNIQUE` 与 `ZERO_CANDIDATE` 都是 0。

此时算出来的"多候选比例"反映的是**工具面窄**，不是场景性质，因此结果作废。

修法（按冻结顺序）：只补现有规则真正需要的工具（`get_shipment`），**不改规则条件、
不加规则、不加 case、不调期望值**；重跑同一批 5 条 pilot 作为工程信号。

**口径提醒**：pilot 出现 `UNIQUE / ZERO_CANDIDATE / MULTI_CANDIDATE` 三态只是
**工程通过信号**，不是 W2 正式 Gate。正式 Gate 仍只有：
`Agent-needed ≥ 10 / 50` 且覆盖 `≥3 种动态取数模式`。

## 50 条 benchmark 的规格表 schema（2026-10-09 冻结）

| 字段 | 含义 | 允许写 |
|---|---|---|
| `case_id` | D-01…D-50 | 是 |
| `decision_question` | `queue` / `priority` | 是 |
| `provenance` | `issue_derived#<issue>` 或 `synthetic_with_basis#<依据>` | 是 |
| `business_state` | 业务世界状态（如 `paid_no_shipment`、`shipped_delayed`） | 是 |
| `business_intent` | 客户真实诉求（只用于生成自然文本，**不当模板关键词**） | 是 |
| `surface_form_variant` | `direct` / `complaint` / `timeline` / `rhetorical` / `missing_context` / `mixed_intent` | 是 |
| `expected_queue` / `expected_priority` | gold，**跑之前冻结** | 是 |
| `expected_handoff` | `auto` / `human_review` | 是 |
| `scenario_type` | 场景大类，仅供分层统计 | 是 |
| `bucket` / `agent_needed` / `dynamic_pattern` | — | **否：只由执行结果显示** |

### 两条硬守卫

1. **`agent_needed` 不进入生成器输入**：链条只能是
   `spec → 生成业务世界 → 冻结规则执行 → 得桶 → 再按三条判据判 Agent-needed`；
   规格表里不出现该字段，生成器也不接受它。
2. **`dynamic_pattern` 与第②条判据后置**：规格表里的 `scenario_type` 只是分层标签；
   最终统计的 `dynamic_pattern`（如 `shipment`）来自判据执行与审核结果，
   不是"spec 里写了 shipment 就算一种模式"。

### 口径澄清（防误读）

`expected_handoff=auto` 表示**预期无需人工接管、允许自动通过当前流程**，
**不是本项目实际执行自动发送**——本期不做自动发送（阶段 3 只做设计预留）。

## 修订纪律

这一轮只允许改**已发现的三个口径问题**与 `expected_queue` / `expected_handoff` 的字段分离；
**不得新增规则、不得新增 case、不得调整期望值**——否则"发现 → 修订一次 → 作废 → 重跑"这条证据链不成立。
