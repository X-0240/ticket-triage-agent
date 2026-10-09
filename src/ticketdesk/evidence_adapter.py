"""工具结果 → 证据的唯一适配层：结构校验 + 事实身份 + 一次执行内稳定的 fact_id。

为什么需要它（真实契约错位）：真实工具返回 `{"tool","found","ref","facts","error"}`，
**没有顶层 `fact_ids`**；而 `fact_id` 目前由 `pipeline._with_fact_ids()` 分配。
子图若继续假定工具直接给 `fact_ids`，真实模型路径会立刻失效。

三条硬约束：

1. **原子拒绝**：结构不合法 → 整批拒绝（`INVALID_SCHEMA / tool_result`），
   **任何 fact_id 都不登记**，不触发后续判定；
2. **身份稳定**：同一事实再次返回时**沿用原 fact_id**，新事实分配未使用的 ID，
   避免"重复事实被当成新证据"从而破坏 `NO_NEW_EVIDENCE` 的判定；
3. **状态隔离**：注册表按案例/按臂创建，不跨案例共享。

合法的 `facts == []` **不是**结构错误：它走既有的业务缺失/无新证据路径。
"""

from dataclasses import dataclass, field

# 事实身份键（用于判定"是不是同一条事实"）——取自真实契约的字段
IDENTITY_FIELDS = ("field", "value", "source", "ref", "timestamp")
# 结构必填字段（缺一即整批拒绝）
REQUIRED_FIELDS = ("field", "value", "ref")

FAILURE_CODE = "INVALID_SCHEMA"
FAILURE_STAGE = "tool_result"


@dataclass
class EvidenceSchemaError(Exception):
    """工具结果结构不合法：原子拒绝，不登记任何事实。

    `tool_calls` 记录"被拒绝前已经发生的工具调用尝试次数"，由调用方在抛出点补上，
    否则记录里会丢掉"到底取过几次数"这条审计信息。
    """

    reason: str
    failure_code: str = FAILURE_CODE
    failure_stage: str = FAILURE_STAGE
    tool_calls: int = 0

    def __str__(self):
        return "%s/%s: %s" % (self.failure_code, self.failure_stage, self.reason)


@dataclass
class EvidenceRegistry:
    """一次执行（一个案例的一条臂）内的事实注册表。

    `_by_key`：事实身份 → fact_id，保证**同一事实复用同一个 id**；
    `_known_ids`：本次执行已知的全部 id（基础取数 + 已登记的动态取数），
    用于判定"这次调用有没有取得新证据"；
    `_seq`：ID 分配序号，保证新事实不与基础取数或先前取数冲突。
    """

    _by_key: dict = field(default_factory=dict)
    _known_ids: set = field(default_factory=set)
    _seq: int = 0

    def seed(self, facts=None, fact_ids=None):
        """登记基础取数结果。

        `facts` 给的是带 `fact_id` 的事实记录（同时登记身份，使再次返回同一事实时
        复用原 id）；`fact_ids` 只给 id（只保证不冲突）。两者都登记为"已知"，
        因为基础取数的证据在子图进入前就已经属于本次执行。
        """
        for fact in facts or []:
            fact_id = fact.get("fact_id")
            if not fact_id:
                continue
            self._by_key[self.identity(fact)] = fact_id
            self._note(fact_id)
        for fact_id in fact_ids or []:
            self._note(fact_id)

    def _note(self, fact_id):
        """登记一个已知 id，并推进分配序号（id 形如 `fact_07`）。"""
        self._known_ids.add(fact_id)
        suffix = str(fact_id).rsplit("_", 1)[-1]
        if suffix.isdigit():
            self._seq = max(self._seq, int(suffix))

    def known_ids(self):
        """本次执行已知的全部 fact_id（用于 `allowed_fact_ids` 与审计）。"""
        return set(self._known_ids)

    def identity(self, fact):
        """事实身份键：身份相同即视为同一条事实，复用同一个 fact_id。"""
        return tuple(str(fact.get(name)) for name in IDENTITY_FIELDS)

    def _validate(self, result):
        if not isinstance(result, dict):
            raise EvidenceSchemaError("工具结果不是 dict")
        facts = result.get("facts")
        if facts is None:
            raise EvidenceSchemaError("缺少 facts 字段")
        if not isinstance(facts, list):
            raise EvidenceSchemaError("facts 不是列表")
        for index, fact in enumerate(facts):
            if not isinstance(fact, dict):
                raise EvidenceSchemaError("第 %d 条 fact 不是 dict" % index)
            missing = [n for n in REQUIRED_FIELDS if fact.get(n) in (None, "")]
            if missing:
                raise EvidenceSchemaError(
                    "第 %d 条 fact 缺字段: %s" % (index, ",".join(missing))
                )
        return facts

    def adapt(self, result):
        """校验 + 登记 + 返回 `{"fact_ids", "facts", "new_fact_ids"}`。

        先全量校验、再统一登记：任何一条不合法都整批拒绝，不登记一半。
        `new_fact_ids` 由注册表判定（不是由模型自述），重复事实不会算作新证据。
        """
        facts = self._validate(result)
        fact_ids, new_fact_ids = [], []
        for fact in facts:
            key = self.identity(fact)
            if key not in self._by_key:
                self._seq += 1
                self._by_key[key] = "fact_%02d" % self._seq
            fact_id = self._by_key[key]
            if fact_id not in self._known_ids:
                new_fact_ids.append(fact_id)
            fact_ids.append(fact_id)
        self._known_ids.update(fact_ids)
        return {
            "fact_ids": fact_ids,
            "facts": [
                dict(fact, fact_id=fact_id)
                for fact, fact_id in zip(facts, fact_ids)
            ],
            "new_fact_ids": new_fact_ids,
        }
