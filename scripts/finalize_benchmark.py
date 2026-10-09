"""收口：逐条差异清单 + v2 盲审包（只读 inputs_50.json）+ 50/50 核验 + 版本记录。

纪律：
- 不覆盖旧的 review_packet_v1.md；v2 用新版本名；
- 版本记录里的 commit 取自实际执行时的 `git rev-parse`，拿不到就写 null，不填假值；
- 逐条差异只描述历史结果之间的差异，**不用于反推旧输入**。

用法：python scripts/finalize_benchmark.py
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "discovery"
FIXTURES = ROOT / "fixtures" / "discovery"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(case_id, ticket_id, question, body, facts, order_no):
    return json.dumps(
        {"case_id": case_id, "ticket_id": ticket_id,
         "decision_question": question, "body": body, "facts": facts,
         "order_no": order_no},
        ensure_ascii=False, sort_keys=True,
    )


def main():
    snap_doc = json.loads((OUT / "inputs_50.json").read_text(encoding="utf-8"))
    snapshot = snap_doc["cases"]
    new_path = sorted(OUT.glob("benchmark50_repro_*.json"))[-1]
    old_path = sorted(OUT.glob("benchmark50_2*.json"))[0]
    new = json.loads(new_path.read_text(encoding="utf-8"))
    old = json.loads(old_path.read_text(encoding="utf-8"))
    new_by = {c["case_id"]: c for c in new["cases"]}
    old_by = {c["case_id"]: c for c in old["cases"]}

    diff = []
    for case in snapshot:
        cid = case["case_id"]
        old_b = old_by.get(cid, {}).get("bucket")
        new_b = new_by.get(cid, {}).get("bucket")
        diff.append({"case_id": cid, "old_bucket": old_b, "new_bucket": new_b,
                     "changed": old_b != new_b})
    changed = [d for d in diff if d["changed"]]

    lines = [
        "# 工单分诊 benchmark·盲审包 v2（只读 inputs_50.json）",
        "",
        "v1 已作废：它由独立 derive() 重建，与快照不是同一来源。",
        "本包内容**逐条来自 inputs_50.json**，与规则执行所用输入同源。",
        "",
        "三条判据（冻结口径）：",
        "1. 固定取数 + 结构化规则后仍给不出唯一结论，**或唯一候选与正文语义冲突**；",
        "2. **必须根据工单正文语义决定下一步查什么**；",
        "3. 该形态在真实场景存在（见 provenance，可核查）。",
        "",
        "提醒：0 候选也可能是 agent_needed（满足②③即可）；因事实缺失造成的零命中不算。",
        "",
        "cases：%d 条" % len(snapshot),
        "",
    ]
    verified = 0
    for case in snapshot:
        result = new_by[case["case_id"]]
        digest = sha(canonical(case["case_id"], case["ticket_id"],
                               case["decision_question"], case["body"],
                               case["facts"], case["order_no"]))
        if digest == case["input_sha256"]:
            verified += 1
        facts_text = "；".join("%s=%s" % (k, v) for k, v in case["facts"].items())
        lines.extend([
            "### %s（%s）" % (case["case_id"], case["decision_question"]),
            "",
            "- provenance：%s" % case["provenance"],
            "- scenario_type：%s" % case["scenario_type"],
            "- 工单正文：%s" % case["body"],
            "- baseline 事实：%s" % facts_text,
            "- 候选结果：%s（命中规则 %s）"
            % (result["candidate_outputs"] or "无候选",
               ",".join(result["hit_rules"]) or "无"),
            "- 当前分桶：%s" % result["bucket"],
            "- 输入 sha256：%s" % case["input_sha256"],
            "",
            "```",
            "criterion_1_met: true/false",
            "criterion_2_met: true/false",
            "criterion_3_met: true/false",
            "agent_needed: true/false",
            "required_next_lookup: <还需查什么，或 none>",
            "reason: <一句话>",
            "```",
            "",
        ])
    packet = OUT / "review_packet_v2.md"
    packet.write_text("\n".join(lines), encoding="utf-8")

    rules_hash = sha((FIXTURES / "rules_v1.json").read_text(encoding="utf-8"))[:16]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                            capture_output=True, text=True).stdout.strip()
    record = {
        "kind": "benchmark50_finalize",
        "rules_version": new["rules_version"],
        "rules_hash": rules_hash,
        "input_dataset_sha256": snap_doc["dataset_sha256"],
        "executed_commit": commit or None,
        "bucketing_result": new_path.name,
        "packet": packet.name,
        "packet_reads": "inputs_50.json",
        "verification": {"cases": len(snapshot), "matched": verified},
        "old_result": old_path.name,
        "old_result_note": "缺少历史输入快照，历史输入一致性无法验证，保留但不作可复现记录",
        "bucket_diff": diff,
        "changed_count": len(changed),
    }
    (OUT / "benchmark50_finalize.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print("v2 盲审包：%s" % packet.name)
    print("核验：%d/%d 条正文与事实与快照一致" % (verified, len(snapshot)))
    print("逐条差异：%d 条变化 / 共 %d 条" % (len(changed), len(diff)))
    for item in changed:
        print("   %s：%s → %s" % (item["case_id"], item["old_bucket"],
                                  item["new_bucket"]))
    print("规则 hash %s ｜ 输入 hash %s" % (rules_hash, snap_doc["dataset_sha256"]))
    print("执行 commit：%s" % (commit or "null（代码尚未提交）"))
    print("记录：benchmark50_finalize.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
