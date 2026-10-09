"""正式 A/C 运行入口：只跑一轮，产物不可覆盖。

开跑前做**机械核验**，任何一条不通过就拒绝运行：

1. 四份协议 + 输入 + 规则 + gold + 派生标签 + 业务世界 + 数据加载器 + 提示词的哈希全部匹配；
2. `runner_commit` == 当前 HEAD，且工作区干净（`worktree_dirty=False`）；
3. 实验库与日常库不同名。

产物：`<run_dir>/{manifest.json, runs.jsonl, case_metrics.jsonl, summary.json, report.md}`，
其中 `runs.jsonl` 是逐案例两臂的原始运行记录（含 `tool_trace`），`summary.json`/`report.md`
由评分层生成。运行一次即固定，不因结果不理想而重跑。

用法：python scripts/run_ac_v1.py [--run-dir experiments/ac_v1/run_<stamp>]
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticketdesk import (  # noqa: E402
    ac_harness,
    ac_runner,
    ac_scoring,
    config,
    db,
    evidence_adapter,
    evidence_manifest,
    model_client,
    tools,
)

INPUTS = ROOT / "experiments" / "discovery" / "inputs_50.json"
PROTOCOL_COMMIT = "8484f5fb"          # 原协议冻结点，不随代码版本变化
CUSTOMER = "C-1001"
BUDGET = 4                            # 协议第 2 节：单次子图最多 4 次工具调用
MAX_TOKENS = 1200


def load_cases():
    payload = json.loads(INPUTS.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if len(cases) != 50:
        raise SystemExit("冻结案例数不是 50：%d" % len(cases))
    return cases


def db_loaded_at():
    """实验库的加载时刻。

    世界文件里 D-50 的 `created_offset_hours=0`，因此 `MAX(created_at)` 就等于加载时刻；
    这样不用额外产物，也能在 Manifest 里留痕。
    """
    row = db.query_one("SELECT MAX(created_at) AS loaded_at FROM ticket")
    return str(row["loaded_at"]) if row and row["loaded_at"] else None


def check_ready(paths, manifest):
    """开跑前的机械核验；返回问题清单。"""
    problems = list(evidence_manifest.verify_files(manifest, paths))
    head = evidence_manifest.git_commit()
    if manifest.worktree_dirty:
        problems.append("工作区不干净：拒绝正式运行（先提交再跑）")
    if manifest.runner_commit != head:
        problems.append("runner_commit 不是当前 HEAD：%s != %s"
                        % (manifest.runner_commit, head))
    if manifest.protocol_commit != PROTOCOL_COMMIT:
        problems.append("protocol_commit 不是原协议冻结点")
    if manifest.model_id != model_client.DEFAULT_MODEL:
        problems.append("模型标识不是 %s" % model_client.DEFAULT_MODEL)
    if manifest.model_params.get("thinking") != "disabled":
        problems.append("thinking 未固定为 disabled")
    return problems


def main():
    parser = argparse.ArgumentParser(description="正式 A/C 运行（一轮）")
    parser.add_argument("--run-dir", default=None)
    args = parser.parse_args()

    # 与加载器同一规则：实验库默认 ticketdesk_ac_v1，可用 DB_NAME_AC 覆盖；
    # 与日常库同名直接拒绝，避免把正式运行打到日常数据上
    target = os.getenv("DB_NAME_AC", "ticketdesk_ac_v1")
    if target == config.DB_NAME:
        raise SystemExit("拒绝运行：实验库与日常库同名（%s）" % target)
    db.use_database(target)

    session = tools.Session(customer_id=CUSTOMER)
    cases = load_cases()
    prepared = [ac_harness.prepare_case(case, session,
                                       evidence_adapter.EvidenceRegistry())
                for case in cases]
    loaded_at = db_loaded_at()
    paths = evidence_manifest.ArtifactPaths.frozen_defaults()
    manifest = evidence_manifest.build(
        paths, protocol_commit=PROTOCOL_COMMIT,
        runner_commit=evidence_manifest.git_commit(),
        prompt_hash=evidence_manifest.sha_of(
            ROOT / "src" / "ticketdesk" / "prompts.py"),
        model_id=model_client.DEFAULT_MODEL,
        model_params={"temperature": 0, "thinking": "disabled",
                      "response_format": "json_object",
                      "max_tokens": MAX_TOKENS, "subgraph_budget": BUDGET,
                      "decision_question_from": "inputs_50.json"},
        experiment_db=target, db_loaded_at=loaded_at,
    )
    problems = check_ready(paths, manifest)
    if problems:
        raise SystemExit("机械核验未通过，拒绝开跑：\n- " + "\n- ".join(problems))

    client = model_client.DeepSeekClient()
    recorders, registries = {}, {}
    workflow_factory, agent_factory, usage_factory = (
        ac_harness.make_model_factories(client, prepared, recorders, registries,
                                        max_tokens=MAX_TOKENS))
    checker_factory = ac_harness.make_checker_factory(client, prepared, recorders)
    executor_factory = ac_harness.make_executor_factory(prepared, session)

    records = ac_runner.run_experiment(
        prepared,
        {case["case_id"]: case["route_input"] for case in prepared},
        workflow_factory, executor_factory, {}, manifest,
        evidence_manifest.verify_files, budget=BUDGET,
        registry_factory=ac_harness.make_registry_factory(registries),
        agent_model_factory=agent_factory, checker_factory=checker_factory,
        usage_factory=usage_factory,
    )

    run_dir = Path(args.run_dir or (ROOT / "experiments" / "ac_v1"
                                   / ("run_" + datetime.now().strftime(
                                       "%Y%m%dT%H%M%S"))))
    labels = ac_scoring.load_labels(paths.agent_needed_labels, cases)
    written = ac_scoring.write_artifacts(run_dir, records, cases,
                                         labels["agent_needed"],
                                         labels["patterns"])
    (run_dir / "runs.jsonl").write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        + "\n", encoding="utf-8", newline="\n")
    evidence_manifest.to_json(manifest, run_dir / "manifest.json")

    summary = json.loads(Path(written["summary"]).read_text(encoding="utf-8"))
    print("run_dir: %s" % run_dir)
    print("模型调用 %d 次｜返回模型 %s｜实验库 %s（加载于 %s）"
          % (client.calls, sorted(set(client.returned_models)), target, loaded_at))
    for arm in ("A", "C"):
        block = summary["arms"][arm]
        print("[%s] 有效判定 %d/%d（覆盖率 %s）｜队列准确率 %s（已评 %d，缺失 %d）"
              "｜安全转人工 %d｜失败 %s｜停止 %s｜tokens %s｜延迟均值 %s ms"
              % (arm, block["valid_decisions"], block["cases"],
                 block["output_coverage"],
                 block["queue_accuracy"]["accuracy_on_valid"],
                 block["queue_accuracy"]["scored"],
                 block["queue_accuracy"]["missing_or_invalid"],
                 block["handoff_to_human"], block["failure_reasons"] or "无",
                 block["safe_stop_reasons"] or "无", block["tokens"],
                 block["latency_ms"]["mean"]))
    paired = summary["paired"]
    print("配对：改善 %d，回退 %d，持平 %d，配对缺失 %d"
          % (paired["queue_improved"], paired["queue_regressed"],
             paired["queue_same"], len(paired["incomplete_pairs"])))


if __name__ == "__main__":
    main()
