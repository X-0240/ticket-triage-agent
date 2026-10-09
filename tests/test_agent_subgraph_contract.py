"""受控 Agent 子图的契约测试：入口门禁 / 停止条件 / 引用校验 / 强制人工。"""

import pytest

from ticketdesk import agent_subgraph, verdict


class FakeModel:
    """按脚本逐步给出动作；脚本用尽后直接给 final。"""

    def __init__(self, script, final=None):
        self.script = list(script)
        self.final = final
        self.seen_allowed = []

    def __call__(self, allowed_fact_ids, step):
        self.seen_allowed.append(set(allowed_fact_ids))
        if step < len(self.script):
            return self.script[step]
        return {"final": self.final}


def fake_executor(**kwargs):
    return {"fact_ids": ["fact_new_%s" % kwargs.get("tool")], "facts": []}


def test_entry_denied_for_non_ambiguous_tiers():
    for route in ("hard_fact", "soft_fact"):
        with pytest.raises(agent_subgraph.EntryDenied) as exc:
            agent_subgraph.enter(route)
        assert exc.value.code == "ENTRY_DENIED"


def test_normal_path_returns_decide_and_reference_passes():
    model = FakeModel([{"tool": "get_refund_records", "args": {"order_no": "O-1"}}],
                      final={"queue": "售后组", "priority": "P1",
                             "evidence_bundle": ["fact_new_get_refund_records"],
                             "draft_reply": "已为您核查", "needs_human": False})
    out = agent_subgraph.run("ambiguous", {"fact_01"}, model, fake_executor)
    assert out["action"] == "decide"
    result = verdict.validate_decision(out["payload"], out["allowed_fact_ids"])
    assert result.queue == "售后组"


def test_allowed_ids_include_base_and_subgraph_evidence():
    model = FakeModel([{"tool": "search_kb", "args": {"query": "退款"}}],
                      final={"queue": "售后组", "priority": "P1",
                             "evidence_bundle": ["fact_01",
                                                 "fact_new_search_kb"],
                             "draft_reply": "x", "needs_human": False})
    out = agent_subgraph.run("ambiguous", {"fact_01"}, model, fake_executor)
    assert out["allowed_fact_ids"] == {"fact_01", "fact_new_search_kb"}
    assert verdict.validate_decision(out["payload"],
                                     out["allowed_fact_ids"]).queue == "售后组"


def test_unknown_or_cross_run_fact_id_rejected():
    model = FakeModel([{"tool": "search_kb", "args": {"query": "退款"}}],
                      final={"queue": "售后组", "priority": "P1",
                             "evidence_bundle": ["fact_from_other_run"],
                             "draft_reply": "x", "needs_human": False})
    out = agent_subgraph.run("ambiguous", {"fact_01"}, model, fake_executor)
    with pytest.raises(verdict.DecisionError) as exc:
        verdict.validate_decision(out["payload"], out["allowed_fact_ids"])
    assert exc.value.code == "EVIDENCE_UNKNOWN"


def test_tool_failure_stops_and_hands_off():
    def boom(**kwargs):
        raise RuntimeError("工具炸了")

    model = FakeModel([{"tool": "get_refund_records", "args": {"order_no": "O-1"}}])
    out = agent_subgraph.run("ambiguous", set(), model, boom)
    assert out["action"] == "human_review"
    assert out["stop_code"] == "TOOL_FAILED"


def test_repeated_call_stops():
    same = {"tool": "search_kb", "args": {"query": "退款"}}
    model = FakeModel([same, same])
    out = agent_subgraph.run("ambiguous", set(), model, fake_executor)
    assert out["stop_code"] == "REPEATED_CALL"


def test_no_new_evidence_stops():
    def no_new(**kwargs):
        return {"fact_ids": [], "facts": []}

    model = FakeModel([{"tool": "search_kb", "args": {"query": "退款"}}])
    out = agent_subgraph.run("ambiguous", set(), model, no_new)
    assert out["stop_code"] == "NO_NEW_EVIDENCE"


def test_budget_exhausted_stops():
    script = [{"tool": "t%d" % i, "args": {"i": i}} for i in range(5)]
    model = FakeModel(script)
    out = agent_subgraph.run("ambiguous", set(), model, fake_executor, budget=3)
    assert out["stop_code"] == "BUDGET_EXHAUSTED"
    assert out["tool_calls"] == 3


def test_server_forces_human_over_model_false():
    model = FakeModel([], final={"queue": "售后组", "priority": "P1",
                                 "evidence_bundle": ["fact_01"],
                                 "draft_reply": "x", "needs_human": False})
    out = agent_subgraph.run("ambiguous", {"fact_01"}, model, fake_executor,
                             budget=1)
    result = verdict.validate_decision(out["payload"], out["allowed_fact_ids"],
                                       forced_human=True)
    assert result.needs_human is True
    assert result.forced_human_by_server is True
