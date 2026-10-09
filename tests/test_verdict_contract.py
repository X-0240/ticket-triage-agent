"""判定节点输出契约的单元测试（纯逻辑，不依赖数据库）。"""

import pytest

from ticketdesk import verdict

ALLOWED = {"fact_01", "fact_02", "fact_03"}


def _payload(**overrides):
    payload = {
        "queue": "履约组",
        "priority": "P1",
        "evidence_bundle": ["fact_01", "fact_02"],
        "draft_reply": "您好，我们正在核实发货进度。",
        "confidence": 0.8,
        "needs_human": False,
    }
    payload.update(overrides)
    return payload


def test_valid_decision_passes():
    result = verdict.validate_decision(_payload(), ALLOWED)
    assert result.queue == "履约组"
    assert result.priority == "P1"
    assert result.needs_human is False
    assert result.forced_human_by_server is False


def test_unknown_fact_id_rejected():
    with pytest.raises(verdict.DecisionError) as exc:
        verdict.validate_decision(_payload(evidence_bundle=["fact_99"]), ALLOWED)
    assert exc.value.code == "EVIDENCE_UNKNOWN"


def test_fact_id_from_another_execution_rejected():
    """引用其他执行记录的 fact_id（即使格式合法）同样判无效。"""
    other_run_allowed = {"fact_07", "fact_08"}
    with pytest.raises(verdict.DecisionError) as exc:
        verdict.validate_decision(
            _payload(evidence_bundle=["fact_07"]), ALLOWED
        )
    assert exc.value.code == "EVIDENCE_UNKNOWN"
    assert verdict.validate_decision(
        _payload(evidence_bundle=["fact_07"]), other_run_allowed
    ).evidence_bundle == ["fact_07"]


def test_empty_evidence_rejected():
    with pytest.raises(verdict.DecisionError) as exc:
        verdict.validate_decision(_payload(evidence_bundle=[]), ALLOWED)
    assert exc.value.code == "EVIDENCE_EMPTY"


def test_invalid_queue_and_priority_rejected():
    with pytest.raises(verdict.DecisionError) as exc:
        verdict.validate_decision(_payload(queue="随便一个组"), ALLOWED)
    assert exc.value.code == "QUEUE_INVALID"
    with pytest.raises(verdict.DecisionError) as exc2:
        verdict.validate_decision(_payload(priority="P9"), ALLOWED)
    assert exc2.value.code == "PRIORITY_INVALID"


def test_server_cannot_be_overridden_on_forced_human():
    """模型输出 needs_human=false，但服务端强制转人工时，服务端说了算。"""
    result = verdict.validate_decision(
        _payload(needs_human=False), ALLOWED, forced_human=True
    )
    assert result.needs_human is True
    assert result.forced_human_by_server is True


def test_auto_send_forbidden():
    with pytest.raises(verdict.DecisionError) as exc:
        verdict.validate_decision(_payload(auto_send=True), ALLOWED)
    assert exc.value.code == "AUTO_SEND_FORBIDDEN"
