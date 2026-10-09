"""A/C 实验框架的自检测试：拒绝运行 / 覆盖完整 / 失败留存 / 隔离 / 统计口径。"""

import pytest

from ticketdesk import ac_runner, evidence_manifest, routing


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
