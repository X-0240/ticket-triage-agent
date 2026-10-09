"""评分汇总的已知答案测试：断言具体数值，并覆盖三条容易错的统计口径。"""

import json
from dataclasses import asdict

import pytest

from ticketdesk import ac_runner, ac_scoring, routing


def decision(queue, priority=None, needs_human=False):
    return {"queue": queue, "priority": priority, "evidence_bundle": ["fact_01"],
            "draft_reply": "", "confidence": 0.0, "needs_human": needs_human,
            "forced_human_by_server": False}


def rec(case_id, arm, **overrides):
    """按 RunRecord 的真实字段构造记录，避免手抄字段名。"""
    fields = {"case_id": case_id, "arm": arm, "run_id": "%s-%s" % (arm, case_id),
              "route": "workflow", "route_reason": None, "action": "decide",
              "stop_code": None, "tool_calls": 0, "decision": None,
              "latency_ms": 0}
    fields.update(overrides)
    return asdict(ac_runner.RunRecord(**fields))


CASES = [
    {"case_id": "X-1", "expected_queue": "履约组", "expected_priority": "P1"},
    {"case_id": "X-2", "expected_queue": "物流组", "expected_priority": None},
    {"case_id": "X-3", "expected_queue": "售后组", "expected_priority": "P2"},
    {"case_id": "X-4", "expected_queue": "投诉组", "expected_priority": None},
]
AGENT_NEEDED = {"X-2", "X-3"}
PATTERNS = {"X-2": "物流异常详情", "X-3": "物流异常详情"}


def known_records():
    """人工构造的对照结果：每一条的预期统计后果都已事先写清。"""
    return [
        # X-1：两臂都对
        rec("X-1", "A", decision=decision("履约组", "P1"), latency_ms=10),
        rec("X-1", "C", decision=decision("履约组", "P1"), latency_ms=11,
            route="hard_fact", route_reason="DETERMINISTIC_MAPPING"),
        # X-2：A 错、C 对（改善）
        rec("X-2", "A", decision=decision("咨询组"), latency_ms=20),
        rec("X-2", "C", decision=decision("物流组"), latency_ms=21,
            route="ambiguous", route_reason="CANDIDATES_UNRESOLVED", tool_calls=2),
        # X-3：A 对、C 安全停止（回退）
        rec("X-3", "A", decision=decision("售后组", "P9"), latency_ms=30),
        rec("X-3", "C", decision=None, action="human_review", failed=True,
            stop_code="NO_NEW_EVIDENCE", route="ambiguous",
            route_reason="CANDIDATES_UNRESOLVED", tool_calls=1, latency_ms=31),
        # X-4：A 输出结构不合法、C 对（改善）
        rec("X-4", "A", decision=None, action="human_review", failed=True,
            failure_code="INVALID_SCHEMA", failure_stage="model_output",
            latency_ms=40),
        rec("X-4", "C", decision=decision("投诉组"), latency_ms=41,
            route="hard_fact", route_reason="DETERMINISTIC_MAPPING"),
    ]


def test_overall_arm_metrics_match_known_answers():
    summary = ac_scoring.summarize(known_records(), CASES, AGENT_NEEDED, PATTERNS)
    arm_a = summary["arms"]["A"]
    assert arm_a["cases"] == 4
    assert arm_a["valid_decisions"] == 3
    assert arm_a["missing_outputs"] == 1
    assert arm_a["output_coverage"] == 0.75
    assert arm_a["handoff_to_human"] == 1
    assert arm_a["handoff_rate"] == 0.25

    # 准确率的条件分母与缺失数必须同时出现
    queue_a = arm_a["queue_accuracy"]
    assert queue_a["cases_with_gold"] == 4
    assert queue_a["scored"] == 3
    assert queue_a["correct"] == 2
    assert queue_a["missing_or_invalid"] == 1
    assert queue_a["accuracy_on_valid"] == 0.6667
    assert queue_a["wrong_cases"] == ["X-2"]

    # 优先级只在有 gold 的案例上算：X-1 对、X-3 的 P9 错
    priority_a = arm_a["priority_accuracy"]
    assert priority_a["cases_with_gold"] == 2
    assert priority_a["scored"] == 2
    assert priority_a["correct"] == 1
    assert priority_a["accuracy_on_valid"] == 0.5

    assert arm_a["failure_reasons"] == {"INVALID_SCHEMA/model_output": 1}
    assert arm_a["safe_stop_reasons"] == {}
    # A 臂不做动态取数：动态调用量全记在 C 臂，这正是要被测量的代价
    assert arm_a["tool_calls"] == {"total": 0, "mean": 0.0, "max": 0}
    assert arm_a["tokens"] == {"known": 0, "unknown": 4, "total": None}
    assert arm_a["latency_ms"] == {"mean": 25.0, "p95": 40, "max": 40}

    arm_c = summary["arms"]["C"]
    assert arm_c["valid_decisions"] == 3
    assert arm_c["output_coverage"] == 0.75
    assert arm_c["queue_accuracy"]["accuracy_on_valid"] == 1.0
    assert arm_c["queue_accuracy"]["wrong_cases"] == []
    assert arm_c["safe_stop_reasons"] == {"NO_NEW_EVIDENCE": 1}
    assert arm_c["failure_reasons"] == {}
    assert arm_c["tool_calls"] == {"total": 3, "mean": 0.75, "max": 2}


def test_safe_handoff_is_not_counted_as_correct_triage():
    """安全转人工 ≠ 成功分诊：C 的 X-3 既算转人工、也不算正确判定。"""
    summary = ac_scoring.summarize(known_records(), CASES, AGENT_NEEDED, PATTERNS)
    arm_c = summary["arms"]["C"]
    assert arm_c["handoff_to_human"] == 1
    assert arm_c["queue_accuracy"]["scored"] == 3          # 不含 X-3
    assert arm_c["queue_accuracy"]["missing_or_invalid"] == 1


def test_paired_diff_keeps_correspondence():
    summary = ac_scoring.summarize(known_records(), CASES, AGENT_NEEDED, PATTERNS)
    paired = summary["paired"]
    assert paired["cases"] == 4
    assert paired["incomplete_pairs"] == []
    assert paired["queue_improved"] == 2
    assert paired["queue_regressed"] == 1
    assert paired["queue_same"] == 1
    assert paired["queue_improved_cases"] == ["X-2", "X-4"]
    assert paired["queue_regressed_cases"] == ["X-3"]


def test_agent_needed_subset_and_routing_block():
    summary = ac_scoring.summarize(known_records(), CASES, AGENT_NEEDED, PATTERNS)
    assert summary["agent_needed_subset"]["A"]["cases"] == 2
    assert summary["agent_needed_subset"]["A"]["queue_accuracy"]["scored"] == 2
    assert summary["agent_needed_subset"]["C"]["queue_accuracy"]["scored"] == 1
    routing = summary["routing"]
    assert routing["agent_needed_cases"] == 2
    assert routing["agent_needed_entered_subgraph"] == 2
    assert routing["agent_needed_in_subgraph_rate"] == 1.0
    assert routing["non_agent_needed_cases"] == 2
    assert routing["non_agent_needed_entered_subgraph"] == 0
    assert routing["agent_needed_on_fixed_path"] == []


def test_agent_needed_on_fixed_path_is_listed_with_reason():
    """gold 标 Agent-needed ≠ 路由一定识别：没进子图要列清单和原因码。"""
    records = known_records()
    records[5] = rec("X-3", "C", decision=None, action="human_review",
                     failed=True, stop_code="NO_NEW_EVIDENCE", route="soft_fact",
                     route_reason="NEEDS_CONSISTENCY_CHECK", tool_calls=0)
    summary = ac_scoring.summarize(records, CASES, AGENT_NEEDED, PATTERNS)
    routing = summary["routing"]
    assert routing["agent_needed_entered_subgraph"] == 1
    assert routing["agent_needed_in_subgraph_rate"] == 0.5
    assert routing["agent_needed_on_fixed_path"] == [
        {"case_id": "X-3", "route": "soft_fact",
         "reason_code": "NEEDS_CONSISTENCY_CHECK"},
    ]


def test_missing_run_record_keeps_a_row():
    """某一臂没有运行记录也要留行，且计入缺失，不从分母里消失。"""
    records = [r for r in known_records() if r["case_id"] != "X-4"]
    rows = ac_scoring.build_case_rows(records, CASES, AGENT_NEEDED, PATTERNS)
    assert len(rows) == 8
    holes = [row for row in rows if row["status"] == "missing_run_record"]
    assert [(row["case_id"], row["arm"]) for row in holes] == [("X-4", "A"),
                                                              ("X-4", "C")]
    summary = ac_scoring.summarize(records, CASES, AGENT_NEEDED, PATTERNS)
    # 缺失运行记录同时体现在覆盖率（少了 1 条有效判定）与单独的缺失计数上
    assert summary["arms"]["A"]["missing_outputs"] == 1
    assert summary["arms"]["A"]["output_coverage"] == 0.75
    assert summary["missing_run_records"] == 2
    assert summary["missing_run_record_keys"] == [["X-4", "A"], ["X-4", "C"]]
    assert summary["paired"]["incomplete_pairs"] == ["X-4"]


def test_pattern_block_reports_per_pattern():
    summary = ac_scoring.summarize(known_records(), CASES, AGENT_NEEDED, PATTERNS)
    block = summary["patterns"]["物流异常详情"]
    assert block["cases"] == 2
    assert block["A"]["queue_accuracy"]["accuracy_on_valid"] == 0.5
    assert block["C"]["queue_accuracy"]["accuracy_on_valid"] == 1.0
    assert block["paired"]["queue_improved"] == 1
    assert block["paired"]["queue_regressed"] == 1


def test_write_artifacts_creates_three_files(tmp_path):
    out = tmp_path / "run-1"
    paths = ac_scoring.write_artifacts(out, known_records(), CASES,
                                      AGENT_NEEDED, PATTERNS)
    assert paths["rows"] == 8
    metrics = [json.loads(line) for line
               in (out / "case_metrics.jsonl").read_text(
                   encoding="utf-8").splitlines()]
    assert len(metrics) == 8
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["arms"]["C"]["valid_decisions"] == 3
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "输出覆盖率" in report
    assert "配对差异（按 case_id 对齐" in report
    assert "不构成统计显著性结论" in report


def test_write_artifacts_refuses_to_overwrite(tmp_path):
    out = tmp_path / "run-1"
    ac_scoring.write_artifacts(out, known_records(), CASES, AGENT_NEEDED, PATTERNS)
    with pytest.raises(FileExistsError):
        ac_scoring.write_artifacts(out, known_records(), CASES, AGENT_NEEDED,
                                  PATTERNS)


def test_scoring_runs_on_runner_output():
    """与运行器串起来：运行记录能直接喂进评分层，失败行不丢。"""
    cases = [{"case_id": "D-01", "base_fact_ids": ["fact_01"],
              "expected_queue": "履约组", "expected_priority": "P1"}]
    routes = {"D-01": routing.RoutingInput(candidates=["履约组"],
                                          required_facts_complete=True,
                                          candidate_requires_semantics=False)}

    class Model:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            return {"final": {"queue": "履约组", "priority": "P1",
                              "evidence_bundle": ["fact_01"],
                              "needs_human": True}}

    records = ac_runner.run_experiment(cases, routes, Model, lambda c: None,
                                       {}, None, lambda m, e: [])
    summary = ac_scoring.summarize(records, cases, agent_needed=["D-01"])
    assert summary["arms"]["A"]["output_coverage"] == 1.0
    assert summary["arms"]["A"]["queue_accuracy"]["accuracy_on_valid"] == 1.0
    assert summary["routing"]["agent_needed_on_fixed_path"] == [
        {"case_id": "D-01", "route": "hard_fact",
         "reason_code": "DETERMINISTIC_MAPPING"},
    ]
