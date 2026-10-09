"""三档路由的单元测试（纯逻辑，不依赖数据库与模型）。"""

from ticketdesk import routing
from ticketdesk.routing import RoutingInput


class CountingChecker:
    """假的轻量校验器：记录调用次数，返回预设结果。"""

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def __call__(self, statement, candidate):
        self.calls += 1
        return self.result


def test_hard_fact_skips_checker():
    state = RoutingInput(["履约组"], True, candidate_requires_semantics=False)
    checker = CountingChecker("CONSISTENT")
    out = routing.handle(state, statement="已付款未发货", checker=checker)
    assert out["route"] == routing.ROUTE_HARD
    assert out["action"] == "decide"
    assert checker.calls == 0


def test_hard_fact_not_triggered_when_facts_missing():
    state = RoutingInput(["履约组"], False, candidate_requires_semantics=False)
    out = routing.handle(state, statement="x", checker=CountingChecker("CONSISTENT"))
    assert out["route"] == routing.ROUTE_AMBIGUOUS
    assert out["needs_human"] is True
    assert out["reason_code"] == "FACTS_INCOMPLETE"


def test_unique_with_semantics_goes_soft_and_checks_once():
    state = RoutingInput(["物流组"], True, candidate_requires_semantics=True)
    checker = CountingChecker("CONSISTENT")
    out = routing.handle(state, statement="问保修政策", checker=checker)
    assert out["route"] == routing.ROUTE_SOFT
    assert out["action"] == "decide"
    assert checker.calls == 1
    assert len(out["checks"]) == 1


def test_inconsistent_and_uncertain_go_ambiguous():
    state = RoutingInput(["物流组"], True, candidate_requires_semantics=True)
    for result in ("INCONSISTENT", "UNCERTAIN"):
        out = routing.handle(state, statement="问保修政策",
                             checker=CountingChecker(result))
        assert out["route"] == routing.ROUTE_AMBIGUOUS
        assert out["action"] == "human_review"
        assert out["needs_human"] is True


def test_checker_returning_garbage_treated_as_uncertain():
    state = RoutingInput(["物流组"], True, candidate_requires_semantics=True)
    out = routing.handle(state, statement="x",
                         checker=CountingChecker("随便说的"))
    assert out["route"] == routing.ROUTE_AMBIGUOUS
    assert out["reason_code"] == "CHECK_UNCERTAIN"


def test_ambiguous_zero_or_multi_candidates_go_human():
    for candidates in ([], ["售后组", "物流组"]):
        state = RoutingInput(candidates, True, candidate_requires_semantics=False)
        out = routing.handle(state)
        assert out["route"] == routing.ROUTE_AMBIGUOUS
        assert out["action"] == "human_review"
        assert out["reason_code"] == "CANDIDATES_UNRESOLVED"


def test_tool_failure_forces_human_with_reason():
    state = RoutingInput(["履约组"], True, candidate_requires_semantics=False,
                         tool_failed=True)
    out = routing.handle(state)
    assert out["action"] == "human_review"
    assert out["needs_human"] is True
    assert out["reason_code"] == "TOOL_FAILED"


def test_checker_unavailable_falls_back_to_human():
    state = RoutingInput(["物流组"], True, candidate_requires_semantics=True)
    out = routing.handle(state, statement="x", checker=None)
    assert out["action"] == "human_review"
    assert out["reason_code"] == "CHECKER_UNAVAILABLE"
