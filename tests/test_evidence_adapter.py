"""证据适配层契约测试：真实结构适配 / 原子拒绝 / 空结果合法 / 身份稳定 / 隔离。

这些测试用的是**真实工具返回结构**（`{"tool","found","ref","facts","error"}`，
没有顶层 `fact_ids`），防止子图继续依赖一个不存在的字段。
"""

import pytest

from ticketdesk import evidence_adapter as ea


def raw_fact(field="refund_state", value="REFUNDING", ref="R-9001",
             source="refund", timestamp="2026-09-01 10:00:00"):
    return {"field": field, "value": value, "source": source, "ref": ref,
            "timestamp": timestamp}


def raw_result(*facts, tool="get_refund_records", found=True, error=None):
    """真实工具返回：结构里**没有** fact_ids。"""
    return {"tool": tool, "found": found, "ref": "O-3001",
            "facts": list(facts), "error": error}


def base_facts(*specs):
    """基础取数已有的事实（pipeline 已经分配过 fact_id）。"""
    return [dict(raw_fact(*spec), fact_id="fact_%02d" % (index + 1))
            for index, spec in enumerate(specs)]


def test_adapter_accepts_real_tool_shape():
    """真实返回（无顶层 fact_ids）→ 统一格式，且 id 与事实一一对应。"""
    registry = ea.EvidenceRegistry()
    out = registry.adapt(raw_result(raw_fact(), raw_fact(field="refund_amount",
                                                        value="199.0")))
    assert out["fact_ids"] == ["fact_01", "fact_02"]
    assert [f["fact_id"] for f in out["facts"]] == out["fact_ids"]
    assert [f["field"] for f in out["facts"]] == ["refund_state", "refund_amount"]
    assert out["new_fact_ids"] == ["fact_01", "fact_02"]
    assert registry.known_ids() == {"fact_01", "fact_02"}


@pytest.mark.parametrize("bad_fact", [
    {"value": "REFUNDING", "ref": "R-9001"},          # 缺 field
    {"field": "refund_state", "ref": "R-9001"},       # 缺 value
    {"field": "refund_state", "value": "REFUNDING"},  # 缺 ref
])
def test_invalid_fact_rejects_whole_result_atomically(bad_fact):
    """任一条事实缺字段 → 整批拒绝，且**一条 id 都不登记**。"""
    registry = ea.EvidenceRegistry()
    with pytest.raises(ea.EvidenceSchemaError) as exc:
        registry.adapt(raw_result(raw_fact(), bad_fact))
    assert exc.value.failure_code == "INVALID_SCHEMA"
    assert exc.value.failure_stage == "tool_result"
    assert registry.known_ids() == set()
    # 没有烧掉 id：下一次合法取数仍然从 fact_01 开始
    assert registry.adapt(raw_result(raw_fact()))["fact_ids"] == ["fact_01"]


def test_non_dict_result_and_bad_facts_field_rejected():
    registry = ea.EvidenceRegistry()
    for bad in ("不是 dict", {"tool": "get_refund_records"},
                {"facts": "不是列表"}, {"facts": ["不是 dict"]}):
        with pytest.raises(ea.EvidenceSchemaError):
            registry.adapt(bad)
    assert registry.known_ids() == set()


def test_empty_facts_is_valid_not_schema_error():
    """工具执行成功但没查到记录：合法结果，走业务缺失/无新证据路径。"""
    registry = ea.EvidenceRegistry()
    out = registry.adapt(raw_result(found=False, error="NO_REFUND_RECORD"))
    assert out == {"fact_ids": [], "facts": [], "new_fact_ids": []}
    assert registry.known_ids() == set()


def test_repeated_fact_reuses_id_and_is_not_new_evidence():
    """同一事实再次返回：复用原 id，且**不算新证据**（NO_NEW_EVIDENCE 的前提）。"""
    registry = ea.EvidenceRegistry()
    first = registry.adapt(raw_result(raw_fact()))
    second = registry.adapt(raw_result(raw_fact()))
    assert first["fact_ids"] == second["fact_ids"] == ["fact_01"]
    assert first["new_fact_ids"] == ["fact_01"]
    assert second["new_fact_ids"] == []


def test_new_facts_do_not_collide_with_base_facts():
    """新事实分配未使用的 id；重复返回基础事实时复用基础 id 且不算新证据。"""
    base = base_facts(("body", "查退款", "T-2001", "ticket"),
                      ("status", "PAID", "O-3001", "orders"))
    registry = ea.EvidenceRegistry()
    registry.seed(facts=base)
    assert registry.known_ids() == {"fact_01", "fact_02"}

    out = registry.adapt(raw_result(raw_fact(), raw_fact(field="refund_amount",
                                                        value="199.0")))
    assert out["fact_ids"] == ["fact_03", "fact_04"]
    assert out["new_fact_ids"] == ["fact_03", "fact_04"]

    again = registry.adapt(raw_result(base[0], raw_fact()))
    assert again["fact_ids"] == ["fact_01", "fact_03"]
    assert again["new_fact_ids"] == []
    # id 唯一：没有任何两个身份共享同一个 fact_id
    assert len(set(registry._by_key.values())) == len(registry._by_key)


def test_seed_with_ids_only_avoids_collision():
    """只给 id（没有事实内容）时，至少保证新 id 不与基础 id 冲突。"""
    registry = ea.EvidenceRegistry()
    registry.seed(fact_ids=["fact_01", "fact_02"])
    assert registry.adapt(raw_result(raw_fact()))["fact_ids"] == ["fact_03"]


def test_registries_are_isolated_between_executions():
    """案例/臂之间不共享状态：各自的 id 互不影响。"""
    arm_a, arm_c = ea.EvidenceRegistry(), ea.EvidenceRegistry()
    arm_a.seed(facts=base_facts(("status", "PAID", "O-3001", "orders")))
    out_a = arm_a.adapt(raw_result(raw_fact()))
    out_c = arm_c.adapt(raw_result(raw_fact()))
    assert out_a["fact_ids"] == ["fact_02"]
    assert out_c["fact_ids"] == ["fact_01"]      # 不受 A 臂影响
    assert arm_c.known_ids() == {"fact_01"}
