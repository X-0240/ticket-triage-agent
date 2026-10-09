"""A/C 实验框架的自检测试：拒绝运行 / 覆盖完整 / 失败留存 / 隔离 / 统计口径。"""

import pytest

from ticketdesk import ac_runner, evidence_adapter, evidence_manifest, routing


def make_cases(n=50):
    return [{"case_id": "D-%02d" % (i + 1), "base_fact_ids": ["fact_01"]}
            for i in range(n)]


def route_inputs(cases, ambiguous_ids=()):
    out = {}
    for case in cases:
        ambiguous = case["case_id"] in ambiguous_ids
        out[case["case_id"]] = routing.RoutingInput(
            candidates=["售后组", "物流组"] if ambiguous else ["履约组"],
            required_facts_complete=True,
            candidate_requires_semantics=False,
        )
    return out


class FinalModel:
    """假模型：直接给最终结论（含一条真实 fact_id）。"""

    def __init__(self, case_id, allowed):
        self.case_id = case_id

    def __call__(self, allowed_fact_ids, step):
        return {"final": {"queue": "履约组", "priority": "P1",
                          "evidence_bundle": ["fact_01"],
                          "draft_reply": "已核查", "needs_human": False}}


def ok_executor(case_id):
    def _call(**kwargs):
        return {"fact_ids": ["fact_new"], "facts": []}
    return _call


def test_hash_mismatch_refuses_to_run():
    manifest = evidence_manifest.Manifest(
        protocol_commit="8484f5fb", runner_commit=None, worktree_dirty=True,
        protocol_hash="p0", protocol_amendment_01_hash="p1",
        protocol_amendment_02_hash="p2",
        input_hash="aaaa", rules_hash="bbbb", gold_hash="cccc", gate_hash="dddd",
    )
    with pytest.raises(ac_runner.HashMismatch):
        ac_runner.run_experiment(
            make_cases(2), route_inputs(make_cases(2)), FinalModel, ok_executor,
            {"input_hash": "zzzz"}, manifest, evidence_manifest.verify,
        )


def test_all_cases_have_records_for_both_arms():
    cases = make_cases(50)
    records = ac_runner.run_experiment(
        cases, route_inputs(cases), FinalModel, ok_executor, {}, None,
        lambda m, e: [],
    )
    assert len(records) == 100
    for case in cases:
        arms = {r["arm"] for r in records if r["case_id"] == case["case_id"]}
        assert arms == {"A", "C"}


def test_tool_execution_failure_is_recorded():
    """只声明覆盖"工具执行失败"这一类，不暗示覆盖超时与预算耗尽。"""
    cases = make_cases(3)
    ids = {c["case_id"] for c in cases}

    class ToolRequestModel:
        """先请求一次工具，才会触发工具执行失败。"""

        def __init__(self, case_id, allowed):
            self.case_id = case_id

        def __call__(self, allowed_fact_ids, step):
            return {"tool": "search_kb", "args": {"query": "退款"}}

    def boom_executor(case_id):
        def _call(**kwargs):
            raise RuntimeError("工具炸了")
        return _call

    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), ToolRequestModel,
        boom_executor, {}, None, lambda m, e: [],
    )
    c_records = [r for r in records if r["arm"] == "C"]
    assert len(c_records) == 3
    assert all(r["failed"] and r["failure_code"] == "TOOL_FAILED"
               for r in c_records)


def test_case_isolation_no_shared_state():
    cases = make_cases(2)
    records = ac_runner.run_experiment(
        cases, route_inputs(cases), FinalModel, ok_executor, {}, None,
        lambda m, e: [],
    )
    run_ids = [r["run_id"] for r in records]
    assert len(set(run_ids)) == len(run_ids)


def test_route_statistics_from_records():
    """C 臂实际进入子图的比例，可按记录算出来（口径可核）。"""
    cases = make_cases(4)
    ambiguous = {cases[0]["case_id"], cases[1]["case_id"]}
    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ambiguous), FinalModel,
        ok_executor, {}, None, lambda m, e: [],
    )
    c_records = [r for r in records if r["arm"] == "C"]
    in_subgraph = [r for r in c_records if r["route"] == routing.ROUTE_AMBIGUOUS]
    assert len(in_subgraph) == 2
    assert len(c_records) - len(in_subgraph) == 2


def test_stage_timeout_recorded_via_runner_path():
    """超时走运行器的真实处理路径：阶段化分类 + 记录留存 + token 记为未知。"""
    cases = make_cases(1)
    ids = {c["case_id"] for c in cases}

    class ToolRequestModel:
        def __init__(self, case_id, allowed):
            self.case_id = case_id

        def __call__(self, allowed_fact_ids, step):
            return {"tool": "search_kb", "args": {"query": "退款"}}

    def timeout_executor(case_id):
        def _call(**kwargs):
            raise ac_runner.StageTimeout("tool")
        return _call

    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), ToolRequestModel,
        timeout_executor, {}, None, lambda m, e: [],
    )
    c = [r for r in records if r["arm"] == "C"][0]
    assert c["failed"] is True
    assert c["failure_code"] == "TOOL_TIMEOUT"
    assert c["tokens"] is None          # 拿不到用量 -> 未知，不是 0
    assert c["latency_ms"] >= 0         # 超时也保留了耗时


def test_budget_exhausted_propagates_to_runrecord():
    """预算耗尽必须从子图传到 RunRecord.stop_code，且不重复填 failure_code。"""
    cases = make_cases(1)
    ids = {c["case_id"] for c in cases}

    class EndlessModel:
        def __init__(self, case_id, allowed):
            self.step = 0

        def __call__(self, allowed_fact_ids, step):
            self.step += 1
            return {"tool": "t%s" % self.step, "args": {"i": self.step}}

    def unique_executor(case_id):
        """每次返回**新**的 fact id，否则第二次就因"无新证据"提前停止。"""
        counter = {"n": 0}

        def _call(**kwargs):
            counter["n"] += 1
            return {"fact_ids": ["fact_new_%d" % counter["n"]], "facts": []}
        return _call

    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), EndlessModel,
        unique_executor, {}, None, lambda m, e: [], budget=2,
    )
    c = [r for r in records if r["arm"] == "C"][0]
    assert c["stop_code"] == "BUDGET_EXHAUSTED"
    assert c["failure_code"] is None


def test_no_new_evidence_recorded_via_runner():
    """无新证据：由子图真实停止路径触发，且作为安全停止不重复计入 failure_code。"""
    cases = make_cases(1)
    ids = {c["case_id"] for c in cases}

    class OneToolModel:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            return {"tool": "search_kb", "args": {"query": "退款"}}

    def no_new_executor(case_id):
        def _call(**kwargs):
            return {"fact_ids": [], "facts": []}
        return _call

    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), OneToolModel,
        no_new_executor, {}, None, lambda m, e: [],
    )
    c = [r for r in records if r["arm"] == "C"][0]
    assert c["stop_code"] == "NO_NEW_EVIDENCE"
    assert c["decision"] is None
    assert c["failed"] is True
    assert c["failure_code"] is None      # 安全停止原因只记 stop_code


def test_repeated_call_recorded_via_runner():
    """重复取数：同一工具同参数被拦下，作为安全停止不重复计入 failure_code。"""
    cases = make_cases(1)
    ids = {c["case_id"] for c in cases}
    same = {"tool": "search_kb", "args": {"query": "退款"}}

    class SameCallModel:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            return same

    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), SameCallModel,
        ok_executor, {}, None, lambda m, e: [],
    )
    c = [r for r in records if r["arm"] == "C"][0]
    assert c["stop_code"] == "REPEATED_CALL"
    assert c["decision"] is None
    assert c["failed"] is True
    assert c["failure_code"] is None


# ---- 输出结构 vs 语义（两类错误不许串味） ----


def test_model_output_schema_error_is_model_output():
    """模型最终输出缺字段 → INVALID_SCHEMA / model_output，且原始输出留痕。"""
    cases = make_cases(2)          # 一案例歧义、一案例非歧义：两臂都要拦下
    ids = {cases[0]["case_id"]}

    class BadModel:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            return {"final": {"priority": "P1", "evidence_bundle": ["fact_01"]}}

    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), BadModel, ok_executor,
        {}, None, lambda m, e: [],
    )
    for record in records:
        assert record["failed"] is True
        assert record["failure_code"] == "INVALID_SCHEMA"
        assert record["failure_stage"] == "model_output"
        assert record["stop_code"] is None
        assert record["decision"] is None
        assert record["raw_output"] == {"priority": "P1",
                                        "evidence_bundle": ["fact_01"]}


def test_semantic_value_error_is_not_schema_error():
    """结构合法但取值非法 → 具体语义码进 validation_code，不冒充 INVALID_SCHEMA。"""
    cases = make_cases(1)

    class BadValueModel:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            return {"final": {"queue": "随便一个组", "priority": "P1",
                              "evidence_bundle": ["fact_01"], "needs_human": True}}

    records = ac_runner.run_experiment(
        cases, route_inputs(cases), BadValueModel, ok_executor, {}, None,
        lambda m, e: [],
    )
    for record in records:
        assert record["failed"] is True
        assert record["validation_code"] == "QUEUE_INVALID"
        assert record["failure_code"] is None
        assert record["decision"] is None


def test_missing_final_output_is_schema_error():
    """模型没有给出最终输出也是结构问题，不能静默算成"无判定"。"""
    cases = make_cases(1)

    class NoFinalModel:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            return {}

    records = ac_runner.run_experiment(
        cases, route_inputs(cases), NoFinalModel, ok_executor, {}, None,
        lambda m, e: [],
    )
    for record in records:
        assert record["failure_code"] == "INVALID_SCHEMA"
        assert record["failure_stage"] == "model_output"


def test_decision_node_receives_base_facts_on_both_arms():
    """判定节点必须看到基础取数证据（A 臂与固定路径都一样），否则对照失效。"""
    cases = make_cases(1)
    seen = []

    class Recorder:
        def __init__(self, case_id, allowed):
            seen.append(sorted(allowed))

        def __call__(self, allowed_fact_ids, step):
            assert allowed_fact_ids == ["fact_01"]
            return {"final": {"queue": "履约组", "priority": "P1",
                              "evidence_bundle": ["fact_01"],
                              "needs_human": True}}

    records = ac_runner.run_experiment(
        cases, route_inputs(cases), Recorder, ok_executor, {}, None,
        lambda m, e: [],
    )
    assert seen == [["fact_01"], ["fact_01"]]
    assert all(record["decision"]["queue"] == "履约组" for record in records)


# ---- 超时：按真实来源分阶段，不按捕获位置 ----


def test_bare_timeout_at_model_call_is_model_timeout():
    """模型调用点抛裸 TimeoutError：来源可识别 → MODEL_TIMEOUT / model。"""
    cases = make_cases(1)
    ids = {c["case_id"] for c in cases}

    class TimeoutModel:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            raise TimeoutError("模型超时")

    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), TimeoutModel,
        ok_executor, {}, None, lambda m, e: [],
    )
    for record in records:
        assert record["failed"] is True
        assert record["failure_code"] == "MODEL_TIMEOUT"
        assert record["failure_stage"] == "model"
        assert record["timeout_stage"] == "model"


def test_bare_timeout_at_tool_call_is_tool_timeout():
    """工具执行器抛裸 TimeoutError：来源可识别 → TOOL_TIMEOUT / tool（不是 TOOL_FAILED）。"""
    cases = make_cases(1)
    ids = {c["case_id"] for c in cases}

    class ToolRequestModel:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            return {"tool": "search_kb", "args": {"query": "退款"}}

    def timeout_executor(case_id):
        def _call(**kwargs):
            raise TimeoutError("工具超时")
        return _call

    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), ToolRequestModel,
        timeout_executor, {}, None, lambda m, e: [],
    )
    c = [r for r in records if r["arm"] == "C"][0]
    assert c["failure_code"] == "TOOL_TIMEOUT"
    assert c["failure_stage"] == "tool"
    assert c["timeout_stage"] == "tool"


def test_unidentifiable_timeout_is_generic_not_runner_timeout():
    """阶段无法识别的超时（这里发生在模型工厂构造阶段）→ TIMEOUT + timeout_stage=unknown。"""
    cases = make_cases(1)

    def exploding_factory(case_id, allowed):
        raise TimeoutError("不知道哪一侧")

    records = ac_runner.run_experiment(
        cases, route_inputs(cases), exploding_factory, ok_executor, {}, None,
        lambda m, e: [],
    )
    for record in records:
        assert record["failure_code"] == "TIMEOUT"
        assert record["failure_stage"] == "unknown"
        assert record["timeout_stage"] == "unknown"
        assert record["failure_code"] != "RUNNER_TIMEOUT"


# ---- 工具结果结构：适配层接入后原子拒绝，且不泄漏事实 ----


def real_raw_result(*facts):
    """真实工具返回结构（没有顶层 fact_ids）。"""
    return {"tool": "get_refund_records", "found": True, "ref": "O-3001",
            "facts": list(facts), "error": None}


def good_fact(**overrides):
    fact = {"field": "refund_state", "value": "REFUNDING", "source": "refund",
            "ref": "R-9001", "timestamp": "2026-09-01 10:00:00"}
    fact.update(overrides)
    return fact


class CountingToolModel:
    """先取一次数，拿到新证据后再给结论；用于数模型被调用了几次。"""

    calls = 0

    def __init__(self, case_id, allowed):
        pass

    def __call__(self, allowed_fact_ids, step):
        type(self).calls += 1
        if step == 0:
            return {"tool": "get_refund_records", "args": {"order_no": "O-3001"}}
        return {"final": {"queue": "售后组", "priority": "P1",
                          "evidence_bundle": sorted(allowed_fact_ids),
                          "needs_human": True}}


def test_tool_result_schema_error_rejects_whole_result_via_runner():
    """工具返回里有一条事实缺字段 → 整批拒绝、无事实泄漏、不再调用模型。"""
    cases = make_cases(1)
    ids = {c["case_id"] for c in cases}
    CountingToolModel.calls = 0
    bad = real_raw_result(good_fact(), {"field": "refund_amount", "value": 199.0})

    def bad_executor(case_id):
        return lambda **kwargs: bad

    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), CountingToolModel,
        bad_executor, {}, None, lambda m, e: [],
        registry_factory=lambda case: evidence_adapter.EvidenceRegistry(),
    )
    c = [r for r in records if r["arm"] == "C"][0]
    assert c["failure_code"] == "INVALID_SCHEMA"
    assert c["failure_stage"] == "tool_result"
    assert c["stop_code"] is None
    assert c["failed"] is True
    assert c["decision"] is None
    assert c["tool_calls"] == 1
    # 一共只调用过 2 次模型：A 臂 1 次（没给最终输出）+ C 臂 1 次（请求取数）。
    # 若拒绝后还继续取数，这里会大于 2。
    assert CountingToolModel.calls == 2


def test_adapter_stable_ids_drive_no_new_evidence():
    """同一事实被再次取回：id 复用 → 判为无新证据，安全停止转人工。"""
    cases = make_cases(1)
    ids = {c["case_id"] for c in cases}
    same = real_raw_result(good_fact())

    class TwoStepModel:
        """两次取数参数不同（所以不是 REPEATED_CALL），但工具返回同一事实。"""

        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            return {"tool": "get_refund_records",
                    "args": {"order_no": "O-3001", "page": step}}

    def repeat_executor(case_id):
        return lambda **kwargs: same

    registry = evidence_adapter.EvidenceRegistry()
    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), TwoStepModel,
        repeat_executor, {}, None, lambda m, e: [],
        registry_factory=lambda case: registry,
    )
    c = [r for r in records if r["arm"] == "C"][0]
    assert c["stop_code"] == "NO_NEW_EVIDENCE"
    assert c["failure_code"] is None
    assert c["failed"] is True


def test_adapter_path_allows_citing_dynamic_facts():
    """适配层接入后，动态取数拿到的新事实可以被结论合法引用。"""
    cases = make_cases(1)
    ids = {c["case_id"] for c in cases}
    CountingToolModel.calls = 0

    def good_executor(case_id):
        return lambda **kwargs: real_raw_result(good_fact())

    records = ac_runner.run_experiment(
        cases, route_inputs(cases, ambiguous_ids=ids), CountingToolModel,
        good_executor, {}, None, lambda m, e: [],
        registry_factory=lambda case: evidence_adapter.EvidenceRegistry(),
    )
    c = [r for r in records if r["arm"] == "C"][0]
    assert c["failed"] is False
    assert c["failure_code"] is None
    assert c["validation_code"] is None
    assert c["decision"]["queue"] == "售后组"
    # 引用了本次执行里真实存在的 fact_02（fact_01 是基础取数那条）
    assert c["decision"]["evidence_bundle"] == ["fact_01", "fact_02"]
