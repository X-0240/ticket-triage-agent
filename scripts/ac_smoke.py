"""真实接入冒烟：三个动态取数模式各取 1 条，跑通真实模型 + 真实工具链。

只验证**接入链路**（模型调用、MySQL 取数、工具返回适配、证据引用、错误记录、
token 与耗时采集），结果不参与正式 A/C 的业务结论。

前置：实验库已加载（`python scripts/load_experiment_db.py`）、本机设置 `DEEPSEEK_API_KEY`。
用法：python scripts/ac_smoke.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticketdesk import (  # noqa: E402
    ac_harness,
    ac_runner,
    config,
    db,
    evidence_adapter,
    evidence_manifest,
    model_client,
    routing,
    tools,
)

INPUTS = ROOT / "experiments" / "discovery" / "inputs_50.json"
SMOKE_CASES = ("D-16", "D-26", "D-36")     # 三个预定义动态取数模式各一条
CUSTOMER = "C-1001"


def load_input_cases(case_ids):
    payload = json.loads(INPUTS.read_text(encoding="utf-8"))
    by_id = {case["case_id"]: case for case in payload["cases"]}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise SystemExit("输入快照里找不到这些案例: " + ",".join(missing))
    return [by_id[case_id] for case_id in case_ids]


def prepare(cases, session):
    prepared = []
    for case in cases:
        registry = evidence_adapter.EvidenceRegistry()
        prepared.append(ac_harness.prepare_case(case, session, registry))
    return prepared


def main():
    target = config.DB_NAME
    if target == "ticketdesk":
        print("[提示] 当前进程用的是日常库 %s；冒烟必须用实验库" % target)
        db.use_database("ticketdesk_ac_v1")
    session = tools.Session(customer_id=CUSTOMER)
    cases = load_input_cases(SMOKE_CASES)
    prepared = prepare(cases, session)
    for case in prepared:
        print("[基础取数] %s 事实 %d 条，候选 %s，档位 %s"
              % (case["case_id"], len(case["base_facts"]),
                 case["route_input"].candidates,
                 routing.decide_route(case["route_input"])[0]))

    client = model_client.DeepSeekClient()
    try:
        model_client.api_key()
    except model_client.ModelCallError as exc:
        raise SystemExit("冒烟未开始：%s" % exc) from exc
    recorders = {}
    workflow_factory, agent_factory, usage_factory = (
        ac_harness.make_model_factories(client, prepared, recorders))
    checker_factory = ac_harness.make_checker_factory(
        client, prepared, recorders)
    executor_factory = ac_harness.make_executor_factory(prepared, session)

    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir = ROOT / "experiments" / "ac_v1" / ("smoke_" + stamp)
    if out_dir.exists():
        raise SystemExit("产物目录已存在，拒绝覆盖: " + str(out_dir))

    paths = evidence_manifest.ArtifactPaths.frozen_defaults()
    manifest = evidence_manifest.build(
        paths,
        protocol_commit=evidence_manifest.git_commit(),
        runner_commit=evidence_manifest.git_commit(),
        model_id=client.model,
        model_params={"temperature": 0, "thinking": "disabled",
                      "response_format": "json_object",
                      "prompt_file": "src/ticketdesk/prompts.py"},
    )
    problems = evidence_manifest.verify_files(manifest, paths)
    if problems:
        raise SystemExit("冻结件哈希校验失败：\n- " + "\n- ".join(problems))

    try:
        records = ac_runner.run_experiment(
            prepared,
            {case["case_id"]: case["route_input"] for case in prepared},
            workflow_factory, executor_factory, {}, manifest,
            evidence_manifest.verify_files,
            registry_factory=lambda case: evidence_adapter.EvidenceRegistry(),
            agent_model_factory=agent_factory,
            checker_factory=checker_factory,
            usage_factory=usage_factory,
        )
    except model_client.ModelCallError as exc:
        raise SystemExit(
            "冒烟未开始：模型调用不可用（%s）%s" % (exc.kind, exc)) from exc

    out_dir.mkdir(parents=True)
    (out_dir / "runs.jsonl").write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        + "\n", encoding="utf-8", newline="\n")
    evidence_manifest.to_json(manifest, out_dir / "manifest.json")

    lines = ["# 真实接入冒烟（%s）" % stamp, "",
             "模型 %s ｜ 产物 %s" % (client.model, out_dir.name), "",
             "| case | arm | route | action | stop | failure | validation | "
             "tools | tokens | ms |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for record in records:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            record["case_id"], record["arm"], record["route"],
            record["action"], record["stop_code"] or "-",
            record["failure_code"] or "-", record["validation_code"] or "-",
            record["tool_calls"], record["tokens"], record["latency_ms"]))
    (out_dir / "smoke.md").write_text("\n".join(lines) + "\n",
                                      encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print("\n模型返回标识：%s ｜ 调用次数 %d"
          % (sorted(set(client.returned_models)), client.calls))


if __name__ == "__main__":
    main()
