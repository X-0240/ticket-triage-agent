"""A/C 评分汇总：逐案例指标、配对差异、整体与子集汇总、报告渲染。

口径写死在代码里（跑之前就定，结果出来不许挑解释）：

1. `output_coverage = 有有效判定的案例数 / 冻结案例总数`，分母**永远是冻结案例数**；
2. 准确率只在"有有效判定且有 gold"的案例上算，但必须同时披露 `missing_or_invalid`
   （缺失/无效）与 `not_applicable`（gold 不适用），不允许只给一个百分比；
3. **安全转人工率**、**安全停止原因分布**、**失败原因分布**三者分开统计；
4. 配对按 `case_id` 对齐；某一臂没有运行记录也要留行并标 `missing_run_record`；
5. 逐案例行覆盖每个冻结案例的每条臂，失败与无数值判定同样留行。
"""

import json
from pathlib import Path

ARMS = ("A", "C")

# 判定结果里代表"最终交给人工"的字段
HANDOFF_ACTIONS = ("human_review",)


def _p95(values):
    """P95（最近秩法）；50 条样本下只作描述性指标。"""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(0.95 * len(ordered))) - 1))
    return ordered[index]


def _mean(values):
    return round(sum(values) / len(values), 4) if values else None


def load_labels(path, cases):
    """读派生标签文件并核对覆盖；缺失、重复、多余一律报错。

    参数：
        path：`experiments/ac_v1/derived/agent_needed_labels_v1.json`。
        cases：冻结案例（核对覆盖用，避免"标签少了几条也算过"）。

    返回 dict：`{"agent_needed": [...], "patterns": {case_id: 模式名}}`。
    异常：覆盖不齐、计数不符、案例被多个模式覆盖时抛 `ValueError`。
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    labels = payload.get("labels") or {}
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("冻结案例里有重复 case_id")
    known = set(case_ids)
    missing = [case_id for case_id in case_ids if case_id not in labels]
    extra = sorted(case_id for case_id in labels if case_id not in known)
    if missing or extra:
        raise ValueError("标签覆盖不齐：缺失 %s，多余 %s" % (missing, extra))
    if payload.get("agent_needed_true") != sum(1 for value in labels.values()
                                               if value):
        raise ValueError("agent_needed_true 与逐案例标签不一致")
    needed = [case_id for case_id in case_ids if labels[case_id]]
    by_case = {}
    for item in payload.get("patterns") or []:
        for case_id in item["cases"]:
            if case_id in by_case:
                raise ValueError("案例被多个动态模式覆盖: " + case_id)
            by_case[case_id] = item["name"]
    if set(by_case) != set(needed):
        raise ValueError("动态模式覆盖与 agent_needed 标签不一致")
    return {"agent_needed": needed, "patterns": by_case}


def build_case_rows(records, cases, agent_needed=(), patterns=None):
    """逐案例（每臂一行）的评分行；缺运行记录也留行。"""
    agent_needed = set(agent_needed)
    patterns = patterns or {}
    by_key = {(r["case_id"], r["arm"]): r for r in records}
    rows = []
    for case in cases:
        case_id = case["case_id"]
        gold_queue = case.get("expected_queue")
        gold_priority = case.get("expected_priority")
        for arm in ARMS:
            record = by_key.get((case_id, arm))
            if record is None:
                rows.append({
                    "case_id": case_id, "arm": arm, "status": "missing_run_record",
                    "agent_needed": case_id in agent_needed,
                    "pattern": patterns.get(case_id),
                    "gold_queue": gold_queue, "gold_priority": gold_priority,
                    "has_decision": False, "queue_correct": None,
                    "priority_correct": None, "handoff_to_human": None,
                })
                continue
            decision = record.get("decision")
            valid = decision is not None
            predicted_queue = decision.get("queue") if valid else None
            queue_scored = valid and gold_queue is not None
            priority_scored = valid and gold_priority is not None
            rows.append({
                "case_id": case_id,
                "arm": arm,
                "status": "decided" if valid else "no_valid_decision",
                "agent_needed": case_id in agent_needed,
                "pattern": patterns.get(case_id),
                "route": record.get("route"),
                "route_reason": record.get("route_reason"),
                "action": record.get("action"),
                "stop_code": record.get("stop_code"),
                "failure_code": record.get("failure_code"),
                "failure_stage": record.get("failure_stage"),
                "timeout_stage": record.get("timeout_stage"),
                "validation_code": record.get("validation_code"),
                "tool_calls": record.get("tool_calls"),
                "tokens": record.get("tokens"),
                "latency_ms": record.get("latency_ms"),
                "has_decision": valid,
                "predicted_queue": predicted_queue,
                "predicted_priority": decision.get("priority") if valid else None,
                "needs_human": decision.get("needs_human") if valid else None,
                "gold_queue": gold_queue,
                "gold_priority": gold_priority,
                "queue_correct": (predicted_queue == gold_queue
                                  if queue_scored else None),
                "priority_correct": (
                    decision.get("priority") == gold_priority
                    if priority_scored else None
                ),
                "handoff_to_human": (not valid) or bool(
                    decision.get("needs_human")
                ),
            })
    return rows


def _arm_block(rows):
    """一条臂在某个案例集合上的指标块（分母与缺失数分别披露）。"""
    cases = len(rows)
    decided = [row for row in rows if row.get("has_decision")]
    handoff = [row for row in rows if row.get("handoff_to_human")]
    queue_applicable = [row for row in rows if row.get("gold_queue") is not None]
    queue_scored = [row for row in queue_applicable if row.get("has_decision")]
    priority_applicable = [
        row for row in rows if row.get("gold_priority") is not None
    ]
    priority_scored = [
        row for row in priority_applicable if row.get("has_decision")
    ]
    return {
        "cases": cases,
        "valid_decisions": len(decided),
        "missing_outputs": cases - len(decided),
        "output_coverage": round(len(decided) / cases, 4) if cases else None,
        "handoff_to_human": len(handoff),
        "handoff_rate": round(len(handoff) / cases, 4) if cases else None,
        "queue_accuracy": _accuracy_block(queue_applicable, queue_scored,
                                          "queue_correct"),
        "priority_accuracy": _accuracy_block(priority_applicable,
                                             priority_scored,
                                             "priority_correct"),
        "safe_stop_reasons": _counts(row.get("stop_code") for row in rows),
        "failure_reasons": _counts(
            "%s/%s" % (row.get("failure_code"), row.get("failure_stage"))
            for row in rows if row.get("failure_code")
        ),
        "validation_codes": _counts(row.get("validation_code") for row in rows),
        "tool_calls": _tool_call_block(rows),
        "tokens": _token_block(rows),
        "latency_ms": _latency_block(rows),
    }


def _accuracy_block(applicable, scored, field):
    correct = [row for row in scored if row.get(field) is True]
    return {
        "cases_with_gold": len(applicable),
        "not_applicable": None,
        "scored": len(scored),
        "correct": len(correct),
        "missing_or_invalid": len(applicable) - len(scored),
        "accuracy_on_valid": (round(len(correct) / len(scored), 4)
                              if scored else None),
        "wrong_cases": [row["case_id"] for row in scored
                        if row.get(field) is False],
    }


def _counts(values):
    out = {}
    for value in values:
        if value is None:
            continue
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def _tool_call_block(rows):
    values = [row["tool_calls"] for row in rows
              if isinstance(row.get("tool_calls"), int)]
    return {"total": sum(values), "mean": _mean(values),
            "max": max(values) if values else None}


def _token_block(rows):
    known = [row["tokens"] for row in rows if isinstance(row.get("tokens"), int)]
    return {"known": len(known), "unknown": len(rows) - len(known),
            "total": sum(known) if known else None}


def _latency_block(rows):
    values = [row["latency_ms"] for row in rows
              if isinstance(row.get("latency_ms"), int)]
    return {"mean": _mean(values), "p95": _p95(values),
            "max": max(values) if values else None}


def _paired(rows):
    """按 case_id 对齐的配对差异（只比有 gold 队列的案例）。"""
    by_key = {(row["case_id"], row["arm"]): row for row in rows}
    case_ids = sorted({row["case_id"] for row in rows})
    improved, regressed, same, incomplete = [], [], [], []
    for case_id in case_ids:
        left, right = by_key.get((case_id, "A")), by_key.get((case_id, "C"))
        if (left is None or right is None
                or left["status"] == "missing_run_record"
                or right["status"] == "missing_run_record"):
            # 某一臂根本没有运行记录：配对不成立，单独列出，不当成"持平"
            incomplete.append(case_id)
            continue
        if left.get("gold_queue") is None:
            continue
        a_ok = left.get("queue_correct")
        c_ok = right.get("queue_correct")
        if a_ok is True and c_ok is True:
            same.append(case_id)
        elif a_ok is not True and c_ok is True:
            improved.append(case_id)
        elif a_ok is True and c_ok is not True:
            regressed.append(case_id)
        else:
            same.append(case_id)
    return {
        "cases": len(case_ids),
        "incomplete_pairs": incomplete,
        "queue_improved": len(improved),
        "queue_regressed": len(regressed),
        "queue_same": len(same),
        "queue_improved_cases": improved,
        "queue_regressed_cases": regressed,
    }


def _subset(rows, case_ids):
    wanted = set(case_ids)
    return [row for row in rows if row["case_id"] in wanted]


def _routing_block(rows, agent_needed):
    agent_needed = set(agent_needed)
    c_rows = [row for row in rows if row["arm"] == "C"]
    needed = [row for row in c_rows if row["case_id"] in agent_needed]
    others = [row for row in c_rows if row["case_id"] not in agent_needed]
    entered_needed = [row for row in needed
                      if row.get("route") == "ambiguous"]
    entered_others = [row for row in others
                      if row.get("route") == "ambiguous"]
    return {
        "agent_needed_cases": len(needed),
        "agent_needed_entered_subgraph": len(entered_needed),
        "agent_needed_in_subgraph_rate": (
            round(len(entered_needed) / len(needed), 4) if needed else None
        ),
        "non_agent_needed_cases": len(others),
        "non_agent_needed_entered_subgraph": len(entered_others),
        "non_agent_needed_in_subgraph_rate": (
            round(len(entered_others) / len(others), 4) if others else None
        ),
        "agent_needed_on_fixed_path": [
            {"case_id": row["case_id"], "route": row.get("route"),
             "reason_code": row.get("route_reason")}
            for row in needed if row.get("route") != "ambiguous"
        ],
    }


def _pattern_block(rows, agent_needed):
    names = sorted({row.get("pattern") for row in rows if row.get("pattern")})
    block = {}
    for name in names:
        subset = [row for row in rows if row.get("pattern") == name]
        block[name] = {
            "cases": len({row["case_id"] for row in subset}),
            "A": _arm_block([row for row in subset if row["arm"] == "A"]),
            "C": _arm_block([row for row in subset if row["arm"] == "C"]),
            "paired": _paired(subset),
        }
    return block


def summarize(records, cases, agent_needed=(), patterns=None):
    """产出整体、Agent-needed 子集、逐模式、路由与配对汇总。"""
    rows = build_case_rows(records, cases, agent_needed, patterns)
    needed_ids = [case["case_id"] for case in cases
                  if case["case_id"] in set(agent_needed)]
    missing_records = [row for row in rows
                       if row["status"] == "missing_run_record"]
    return {
        "frozen_cases": len(cases),
        "run_records": len(records),
        # 与"有记录但没判定"分开披露：运行记录缺失是流程缺陷，不该混进覆盖率解释
        "missing_run_records": len(missing_records),
        "missing_run_record_keys": [[row["case_id"], row["arm"]]
                                    for row in missing_records],
        "arms": {arm: _arm_block([row for row in rows if row["arm"] == arm])
                 for arm in ARMS},
        "agent_needed_subset": {
            arm: _arm_block([row for row in _subset(rows, needed_ids)
                             if row["arm"] == arm])
            for arm in ARMS
        },
        "paired": _paired(rows),
        "routing": _routing_block(rows, needed_ids),
        "patterns": _pattern_block(rows, needed_ids),
        "caveat": (
            "50 条探索性对照：只作描述性报告，不构成统计显著性结论；"
            "准确率为条件准确率（只在有有效判定的案例上算），"
            "缺失与无效案例数已单独披露。"
        ),
    }


def render_report(summary):
    """把 summary 渲染成可读报告（数字全部来自 summary，不手写）。"""
    lines = ["# A/C 对照结果（自动生成）", "",
             "冻结案例 %d 条，运行记录 %d 条。" % (
                 summary["frozen_cases"], summary["run_records"]), "",
             summary["caveat"], ""]
    for arm in ARMS:
        block = summary["arms"][arm]
        lines += ["## %s 臂（整体）" % arm,
                  "- 有效判定 %d / %d，输出覆盖率 %s，安全转人工 %d（%s）"
                  % (block["valid_decisions"], block["cases"],
                     block["output_coverage"], block["handoff_to_human"],
                     block["handoff_rate"]),
                  "- 队列准确率（仅有效判定）%s，正确 %d / 已评 %d，"
                  "缺失或无效 %d" % (
                      block["queue_accuracy"]["accuracy_on_valid"],
                      block["queue_accuracy"]["correct"],
                      block["queue_accuracy"]["scored"],
                      block["queue_accuracy"]["missing_or_invalid"]),
                  "- 优先级准确率（仅有效判定）%s（已评 %d）" % (
                      block["priority_accuracy"]["accuracy_on_valid"],
                      block["priority_accuracy"]["scored"]),
                  "- 安全停止原因 %s" % (block["safe_stop_reasons"] or "无"),
                  "- 失败原因 %s" % (block["failure_reasons"] or "无"),
                  "- 语义校验错误 %s" % (block["validation_codes"] or "无"),
                  "- 工具调用 total %s / mean %s；token %s；延迟 mean %s, "
                  "p95 %s (ms)" % (
                      block["tool_calls"]["total"], block["tool_calls"]["mean"],
                      block["tokens"], block["latency_ms"]["mean"],
                      block["latency_ms"]["p95"]),
                  ""]
    subset = summary["agent_needed_subset"]
    lines += ["## Agent-needed 子集（冻结标签）",
              "- A：有效判定 %d / %d，队列准确率 %s" % (
                  subset["A"]["valid_decisions"], subset["A"]["cases"],
                  subset["A"]["queue_accuracy"]["accuracy_on_valid"]),
              "- C：有效判定 %d / %d，队列准确率 %s" % (
                  subset["C"]["valid_decisions"], subset["C"]["cases"],
                  subset["C"]["queue_accuracy"]["accuracy_on_valid"]),
              ""]
    routing = summary["routing"]
    lines += ["## 路由统计",
              "- Agent-needed 进子图 %d / %d（%s）" % (
                  routing["agent_needed_entered_subgraph"],
                  routing["agent_needed_cases"],
                  routing["agent_needed_in_subgraph_rate"]),
              "- 非 Agent-needed 进子图 %d / %d（%s）" % (
                  routing["non_agent_needed_entered_subgraph"],
                  routing["non_agent_needed_cases"],
                  routing["non_agent_needed_in_subgraph_rate"]),
              "- Agent-needed 但走固定路径：%s" % (
                  routing["agent_needed_on_fixed_path"] or "无"),
              ""]
    paired = summary["paired"]
    lines += ["## 配对差异（按 case_id 对齐，仅有 gold 队列的案例）",
              "- 改善 %d，回退 %d，持平 %d，配对缺失 %d" % (
                  paired["queue_improved"], paired["queue_regressed"],
                  paired["queue_same"], len(paired["incomplete_pairs"])),
              "- 改善案例：%s" % (paired["queue_improved_cases"] or "无"),
              "- 回退案例：%s" % (paired["queue_regressed_cases"] or "无"),
              ""]
    for name, block in summary["patterns"].items():
        lines += ["## 动态取数模式：%s" % name,
                  "- 案例 %d；A 队列准确率 %s；C 队列准确率 %s" % (
                      block["cases"],
                      block["A"]["queue_accuracy"]["accuracy_on_valid"],
                      block["C"]["queue_accuracy"]["accuracy_on_valid"]),
                  "- 配对：改善 %d，回退 %d，持平 %d" % (
                      block["paired"]["queue_improved"],
                      block["paired"]["queue_regressed"],
                      block["paired"]["queue_same"]),
                  ""]
    return "\n".join(lines)


def write_artifacts(out_dir, records, cases, agent_needed=(), patterns=None):
    """写 `case_metrics.jsonl` / `summary.json` / `report.md`。

    产物目录**不可覆盖**：已存在且非空时直接拒绝，避免重跑抹掉原始运行产物。
    """
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("产物目录已存在且非空，拒绝覆盖: " + str(out))
    out.mkdir(parents=True, exist_ok=True)
    rows = build_case_rows(records, cases, agent_needed, patterns)
    summary = summarize(records, cases, agent_needed, patterns)
    metrics_path = out / "case_metrics.jsonl"
    metrics_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    report_path = out / "report.md"
    report_path.write_text(render_report(summary), encoding="utf-8")
    return {"case_metrics": str(metrics_path), "summary": str(summary_path),
            "report": str(report_path), "rows": len(rows)}
