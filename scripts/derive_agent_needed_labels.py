"""从冻结 Gate 记录派生 A/C 的 agent_needed 标签（可复现、可核验）。

为什么需要派生：`experiments/discovery/gate_v1_decision.json` 是**冻结的原始证据**，
但它的 `notes` 数组里两个字符串字面量之间漏了一个逗号（Python 式隐式拼接在 JSON 里
非法），标准 JSON 解析器读不了它。评审决定：**不改原件**，改为做一次**明确记录的
派生**——在内存里做一次确定性修正，用标准解析器读出标签，产出独立的机器可读文件。

三条硬约束：

1. 先核对原件 SHA-256；不匹配直接失败，不做宽松解析；
2. 断言预期的唯一缺陷**恰好出现一次**；出现 0 次或多次都直接失败；
3. 修正只发生在内存里，**绝不写回原件**。

用法：

    python scripts/derive_agent_needed_labels.py          # 生成派生文件
    python scripts/derive_agent_needed_labels.py --check  # 校验现有派生件与重新派生一致
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT_VERSION = "v1"
SOURCE = ROOT / "experiments" / "discovery" / "gate_v1_decision.json"
CASES_FILE = ROOT / "experiments" / "discovery" / "inputs_50.json"
OUT = ROOT / "experiments" / "ac_v1" / "derived" / "agent_needed_labels_v1.json"

# 冻结原件的 SHA-256：不匹配就停，绝不"顺便兼容一下"
EXPECTED_SOURCE_SHA256 = (
    "307d022c3dc7b5ce36ffd7f94e390182d287791effbf351db529063ad1a4328c"
)
# 唯一语法缺陷：行尾字符串与下一行字符串直接相邻，中间缺一个逗号
DEFECT = '——"\n    "'
FIXED = '——",\n    "'

PATTERN_RE = re.compile(
    r"^(?P<name>.+?)（(?P<start>D-\d+)~(?P<end>D-\d+)(?P<tail>[^）]*)）$"
)
CASE_RE = re.compile(r"^D-(\d+)$")


class DerivationError(RuntimeError):
    """派生前置条件不成立：直接失败，不做容错。"""


def sha256_of(path):
    """LF 归一化后的 SHA-256：换行差异不算改动，避免跨平台检出的假失败。"""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")
                          ).hexdigest()


def read_gate_decision():
    """读冻结原件 → 核对哈希 → 内存内修正一次 → 标准 JSON 解析。"""
    raw = SOURCE.read_bytes()
    actual = sha256_of(SOURCE)
    if actual != EXPECTED_SOURCE_SHA256:
        raise DerivationError(
            "原件哈希不匹配：期望 %s，实际 %s（停止派生；不要改原件）"
            % (EXPECTED_SOURCE_SHA256, actual)
        )
    text = raw.decode("utf-8")
    occurrences = text.count(DEFECT)
    if occurrences != 1:
        raise DerivationError(
            "预期缺陷应恰好出现 1 次，实际 %d 次（停止派生；不要做宽松解析）"
            % occurrences
        )
    fixed = text.replace(DEFECT, FIXED)
    try:
        gate = json.loads(fixed)
    except json.JSONDecodeError as exc:
        raise DerivationError("唯一缺陷修正后仍无法解析: %s" % exc) from exc
    if gate.get("kind") != "discovery_gate_decision":
        raise DerivationError("Gate 文件类型不是 discovery_gate_decision")
    if gate.get("gate_result") != "PASS":
        raise DerivationError("Gate 记录不是 PASS，派生没有意义")
    return gate


def expand_range(start, end):
    """`D-16`~`D-20` → ["D-16", ..., "D-20"]（含两端）。"""
    first = int(CASE_RE.match(start).group(1))
    last = int(CASE_RE.match(end).group(1))
    if last < first:
        raise DerivationError("模式区间反了: %s~%s" % (start, end))
    return ["D-%02d" % number for number in range(first, last + 1)]


def patterns_from_gate(gate):
    """把 Gate 里的动态取数模式（文本区间）转成机器可读的案例清单。"""
    patterns = []
    for item in gate.get("dynamic_patterns") or []:
        match = PATTERN_RE.match(item)
        if not match:
            raise DerivationError("动态模式格式无法解析: " + str(item))
        patterns.append({
            "name": match.group("name").strip(),
            "cases": expand_range(match.group("start"), match.group("end")),
            # 区间后面的说明文字（如"唯一候选与正文语义冲突"）原样保留
            "note": match.group("tail").lstrip("，,；; ").strip(),
        })
    return patterns


def frozen_case_ids():
    payload = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    return [case["case_id"] for case in payload["cases"]]


def derive():
    """产出派生标签文件的内容（不写盘）。"""
    gate = read_gate_decision()
    declared = list(gate.get("agent_needed_cases") or [])
    if len(declared) != len(set(declared)):
        raise DerivationError("Gate 记录的 agent_needed 列表有重复: " + str(declared))
    counts = gate.get("counts") or {}
    if counts.get("agent_needed_true") != len(declared):
        raise DerivationError(
            "计数与列表不一致：counts=%s，列表 %d 条"
            % (counts.get("agent_needed_true"), len(declared))
        )

    patterns = patterns_from_gate(gate)
    pattern_cases = [case_id for item in patterns for case_id in item["cases"]]
    if len(pattern_cases) != len(set(pattern_cases)):
        raise DerivationError("动态模式之间有重复案例")
    if set(pattern_cases) != set(declared):
        raise DerivationError(
            "动态模式覆盖与 agent_needed 标签不一致：差集 %s"
            % sorted(set(pattern_cases) ^ set(declared))
        )

    case_ids = frozen_case_ids()
    if len(case_ids) != len(set(case_ids)):
        raise DerivationError("冻结输入里有重复 case_id")
    unknown = [case_id for case_id in declared if case_id not in set(case_ids)]
    if unknown:
        raise DerivationError("标签引用了冻结输入里不存在的案例: " + str(unknown))

    needed = set(declared)
    labels = {case_id: case_id in needed for case_id in case_ids}
    order = lambda case_id: int(CASE_RE.match(case_id).group(1))  # noqa: E731
    return {
        "kind": "ac_v1_agent_needed_labels",
        "version": SCRIPT_VERSION,
        "frozen_cases": len(case_ids),
        "agent_needed_true": sum(1 for value in labels.values() if value),
        "labels": labels,
        "agent_needed_cases": sorted(needed, key=order),
        "patterns": patterns,
        "source": {
            "file": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
            # sha256 按 LF 归一化计算（断言用）；raw 值同时留痕，便于对照原始字节
            "sha256": EXPECTED_SOURCE_SHA256,
            "sha256_raw_bytes": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "sha256_note": "sha256 按 LF 归一化计算；sha256_raw_bytes 为本机原始字节值",
            "kind": gate.get("kind"),
            "gate_result": gate.get("gate_result"),
            "decided_at": gate.get("decided_at"),
        },
        "conversion": (
            "原件为冻结证据且不是合法 JSON（notes 数组内两个字符串字面量之间缺一个逗号），"
            "因此不改原件：先在内存中核对 SHA-256，再断言该缺陷恰好出现一次并插入一个逗号，"
            "然后用标准 json 解析器读取 agent_needed_cases 与 dynamic_patterns，"
            "补全全部冻结案例的布尔标签。没有永久性容错解析。"
        ),
        "derivation_script": {
            "path": "scripts/derive_agent_needed_labels.py",
            "version": SCRIPT_VERSION,
            "sha256": sha256_of(Path(__file__)),
        },
    }


def render(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description="派生 A/C agent_needed 标签")
    parser.add_argument("--check", action="store_true",
                        help="只校验现有派生件与重新派生结果一致，不写盘")
    args = parser.parse_args()
    text = render(derive())
    if args.check:
        if not OUT.exists():
            raise DerivationError("派生件不存在: " + str(OUT))
        current = OUT.read_text(encoding="utf-8")
        if current != text:
            raise DerivationError("派生件与重新派生结果不一致，请重新运行派生脚本")
        print("派生件校验通过：%s" % OUT)
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 固定用 LF：换行不随平台变化，哈希才可复现
    OUT.write_text(text, encoding="utf-8", newline="\n")
    payload = json.loads(text)
    print("已生成 %s：%d 条案例，agent_needed %d 条，动态模式 %d 个，sha256 %s"
          % (OUT.relative_to(ROOT), payload["frozen_cases"],
             payload["agent_needed_true"], len(payload["patterns"]),
             hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]))


if __name__ == "__main__":
    main()
