"""端到端框架自检：冻结件哈希 → 运行 → 评分 → 产物不可覆盖。

不接真实模型：模型与工具执行器都是测试替身，验证的是**框架可信度**，
不是 Agent 的业务效果。
"""

import json
from pathlib import Path

import pytest

from ticketdesk import (
    ac_runner,
    ac_scoring,
    evidence_adapter,
    evidence_manifest,
    routing,
)

FROZEN_CASES = 50


def frozen_cases():
    """从冻结的输入快照里读案例（只读）。"""
    paths = evidence_manifest.ArtifactPaths.frozen_defaults()
    payload = json.loads(Path(paths.inputs).read_text(encoding="utf-8"))
    return payload["cases"]


def tiny_fixture():
    """三条案例，各对应一种结局：正常判定 / 工具失败 / 预算耗尽。"""
    return [
        {"case_id": "S-1", "base_fact_ids": ["fact_01"],
         "expected_queue": "售后组", "expected_priority": "P1"},
        {"case_id": "S-2", "base_fact_ids": ["fact_01"],
         "expected_queue": "物流组", "expected_priority": None},
        {"case_id": "S-3", "base_fact_ids": ["fact_01"],
         "expected_queue": "履约组", "expected_priority": None},
    ]


def case_routes(cases):
    """三条都判为歧义档，保证 C 臂都进子图。"""
    return {case["case_id"]: routing.RoutingInput(
        candidates=["售后组", "物流组"], required_facts_complete=True,
        candidate_requires_semantics=False) for case in cases}


def raw_result(*facts):
    return {"tool": "get_refund_records", "found": bool(facts), "ref": "O-3001",
            "facts": list(facts), "error": None if facts else "NO_REFUND_RECORD"}


def fact(value="REFUNDING", ref="R-9001"):
    return {"field": "refund_state", "value": value, "source": "refund",
            "ref": ref, "timestamp": "2026-09-01 10:00:00"}


class OutcomeModel:
    """按 case_id 决定结局的假模型。"""

    def __init__(self, case_id, allowed):
        self.case_id = case_id

    def __call__(self, allowed_fact_ids, step):
        if self.case_id == "S-1":
            if step == 0:
                return {"tool": "get_refund_records", "args": {"order_no": "O"}}
            return {"final": {"queue": "售后组", "priority": "P1",
                              "evidence_bundle": sorted(allowed_fact_ids),
                              "draft_reply": "已核查", "needs_human": False}}
        return {"tool": "get_refund_records", "args": {"page": step}}


def outcome_executor(case_id):
    def _call(**kwargs):
        if case_id == "S-2":
            raise RuntimeError("工具炸了")
        return raw_result(fact(ref=kwargs.get("page", "R-9001")))
    return _call


def test_frozen_artifacts_are_unchanged_before_running():
    """正式运行前必须先过哈希关；这里同时证明 50 条输入快照完整可读。"""
    paths = evidence_manifest.ArtifactPaths.frozen_defaults()
    manifest = evidence_manifest.build(paths, protocol_commit="8484f5fb")
    assert evidence_manifest.verify_files(manifest, paths) == []
    cases = frozen_cases()
    assert len(cases) == FROZEN_CASES
    assert len({case["case_id"] for case in cases}) == FROZEN_CASES


def test_hash_mismatch_produces_no_records():
    paths = evidence_manifest.ArtifactPaths.frozen_defaults()
    manifest = evidence_manifest.build(paths, protocol_commit="8484f5fb")
    cases = tiny_fixture()
    with pytest.raises(ac_runner.HashMismatch):
        ac_runner.run_experiment(
            cases, case_routes(cases), OutcomeModel, outcome_executor,
            {"input_hash": "不是真哈希"}, manifest, evidence_manifest.verify_files,
            registry_factory=lambda case: evidence_adapter.EvidenceRegistry(),
        )


def test_end_to_end_records_and_metrics(tmp_path):
    """两臂各一条记录；停止/失败原因各归各位；评分层能直接消费。"""
    paths = evidence_manifest.ArtifactPaths.frozen_defaults()
    manifest = evidence_manifest.build(paths, protocol_commit="8484f5fb")
    cases = tiny_fixture()
    records = ac_runner.run_experiment(
        cases, case_routes(cases), OutcomeModel, outcome_executor, {},
        manifest, evidence_manifest.verify_files,
        registry_factory=lambda case: evidence_adapter.EvidenceRegistry(),
    )
    assert len(records) == 6
    by_key = {(r["case_id"], r["arm"]): r for r in records}
    assert set(by_key) == {(case["case_id"], arm) for case in cases
                           for arm in ("A", "C")}

    # S-2：工具执行失败 → failure_code，stop_code 留空
    assert by_key[("S-2", "C")]["failure_code"] == "TOOL_FAILED"
    assert by_key[("S-2", "C")]["failure_stage"] == "tool"
    assert by_key[("S-2", "C")]["stop_code"] is None
    # S-3：预算耗尽 → stop_code，failure_code 留空
    assert by_key[("S-3", "C")]["stop_code"] == "BUDGET_EXHAUSTED"
    assert by_key[("S-3", "C")]["failure_code"] is None
    # S-1：正常判定，引用了本次执行真实存在的证据
    assert by_key[("S-1", "C")]["decision"]["queue"] == "售后组"
    # 引用同时覆盖基础取数（fact_01）与子图新增（fact_02）：allowed 是整个执行
    assert by_key[("S-1", "C")]["decision"]["evidence_bundle"] == [
        "fact_01", "fact_02"]

    out = tmp_path / "ac_v1_run_1"
    paths_written = ac_scoring.write_artifacts(
        out, records, cases, agent_needed=["S-1"], patterns={"S-1": "退款资格"},
    )
    assert paths_written["rows"] == 6
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["frozen_cases"] == 3
    assert summary["arms"]["C"]["output_coverage"] == round(1 / 3, 4)
    assert summary["arms"]["C"]["failure_reasons"] == {"TOOL_FAILED/tool": 1}
    assert summary["arms"]["C"]["safe_stop_reasons"] == {"BUDGET_EXHAUSTED": 1}
    assert summary["routing"]["agent_needed_entered_subgraph"] == 1

    # 原始产物不可覆盖：同一目录再跑一次必须直接拒绝
    with pytest.raises(FileExistsError):
        ac_scoring.write_artifacts(out, records, cases, agent_needed=["S-1"])


def test_empty_result_is_handled():
    """空结果不是崩，而是覆盖率不可算 + 明确披露。"""
    cases = tiny_fixture()
    summary = ac_scoring.summarize([], cases, agent_needed=[])
    assert summary["arms"]["A"]["cases"] == 3
    assert summary["arms"]["A"]["valid_decisions"] == 0
    assert summary["arms"]["A"]["output_coverage"] == 0.0
    assert summary["arms"]["A"]["queue_accuracy"]["accuracy_on_valid"] is None
    assert summary["missing_run_records"] == 6

    empty = ac_scoring.summarize([], [], agent_needed=[])
    assert empty["frozen_cases"] == 0
    assert empty["arms"]["A"]["output_coverage"] is None
