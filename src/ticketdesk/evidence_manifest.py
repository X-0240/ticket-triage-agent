"""Manifest schema：**协议版本与实际执行代码版本必须分开记录**。

评审口径：协议提交是实验规则的冻结点，不等于运行器的代码版本。运行器尚未提交时，
`runner_commit` 必须为 None，**不得把当前 HEAD 冒充成未来的执行版本**。

三份协议文件（原协议 + 修订 01 + 修订 02）的哈希**分别记录**，不用一个通用字段反复覆盖；
`verify_files()` 会重新读盘逐个核对，防止冻结件在正式运行前被改动。

冻结 Gate 记录不是合法 JSON（见 `scripts/derive_agent_needed_labels.py` 的说明），
因此正式运行用的是**派生标签文件**；它的哈希与派生脚本的哈希同样进 Manifest。
"""

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PROTOCOL_DIR = ROOT / "experiments" / "ac_v1"
DISCOVERY_DIR = ROOT / "experiments" / "discovery"
GOLD_DIR = ROOT / "fixtures" / "gold"


@dataclass(frozen=True)
class ArtifactPaths:
    """一次实验用到的只读文件清单。"""

    protocol: str
    amendment_01: str
    amendment_02: str
    inputs: str
    rules: str
    gold: str
    gate: str
    agent_needed_labels: str
    label_derivation_script: str

    @classmethod
    def frozen_defaults(cls):
        """本轮冻结件路径。

        `gold` 与 `inputs` 指向同一个文件：50 条对照的 gold（`expected_queue` /
        `expected_priority` / `expected_handoff`）就写在输入快照里；
        `fixtures/gold/T-1001.json` 是 W1 纵切的 gold，不属于本次对照。
        """
        return cls(
            protocol=str(PROTOCOL_DIR / "protocol.md"),
            amendment_01=str(PROTOCOL_DIR / "protocol_amendment_01.md"),
            amendment_02=str(PROTOCOL_DIR / "protocol_amendment_02.md"),
            inputs=str(DISCOVERY_DIR / "inputs_50.json"),
            rules=str(ROOT / "fixtures" / "discovery" / "rules_v1.json"),
            gold=str(DISCOVERY_DIR / "inputs_50.json"),
            gate=str(DISCOVERY_DIR / "gate_v1_decision.json"),
            agent_needed_labels=str(PROTOCOL_DIR / "derived"
                                    / "agent_needed_labels_v1.json"),
            label_derivation_script=str(ROOT / "scripts"
                                        / "derive_agent_needed_labels.py"),
        )


def sha_of(path):
    """冻结件哈希（前 16 位）。

    先把 CRLF 归一化成 LF 再算：否则同一份内容在 Windows 检出与 Linux 检出上会得到
    两个哈希，`verify_files()` 就会报假漂移。归一化只影响换行，不改内容。
    """
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()[:16]


def git_commit(path="HEAD"):
    out = subprocess.run(["git", "rev-parse", path], cwd=str(ROOT),
                         capture_output=True, text=True)
    return out.stdout.strip() or None


def worktree_dirty():
    out = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                         capture_output=True, text=True)
    return bool(out.stdout.strip())


@dataclass(frozen=True)
class Manifest:
    """一次实验的版本与哈希清单。

    `protocol_commit` 是**协议冻结点**（原协议提交），`runner_commit` 是**实际执行代码**
    的提交；两者不是一回事，也不能互相顶替。
    """

    protocol_commit: str
    runner_commit: str | None
    worktree_dirty: bool
    protocol_hash: str
    protocol_amendment_01_hash: str
    protocol_amendment_02_hash: str
    input_hash: str
    rules_hash: str
    gold_hash: str
    gate_hash: str
    agent_needed_labels_hash: str
    label_derivation_script_hash: str
    prompt_hash: str | None = None
    model_id: str | None = None
    model_params: dict = field(default_factory=dict)

    def as_dict(self):
        return asdict(self)


def build(paths, protocol_commit, runner_commit=None, prompt_hash=None,
          model_id=None, model_params=None):
    """按冻结件路径生成 Manifest（哈希全部现算，不手抄）。"""
    return Manifest(
        protocol_commit=protocol_commit,
        runner_commit=runner_commit,
        worktree_dirty=worktree_dirty(),
        protocol_hash=sha_of(paths.protocol),
        protocol_amendment_01_hash=sha_of(paths.amendment_01),
        protocol_amendment_02_hash=sha_of(paths.amendment_02),
        input_hash=sha_of(paths.inputs),
        rules_hash=sha_of(paths.rules),
        gold_hash=sha_of(paths.gold),
        gate_hash=sha_of(paths.gate),
        agent_needed_labels_hash=sha_of(paths.agent_needed_labels),
        label_derivation_script_hash=sha_of(paths.label_derivation_script),
        prompt_hash=prompt_hash,
        model_id=model_id,
        model_params=model_params or {},
    )


def verify(manifest, expected):
    """返回不匹配项清单；空列表表示可运行。"""
    problems = []
    for key, want in (expected or {}).items():
        got = getattr(manifest, key, None)
        if got != want:
            problems.append("%s: 期望 %s，实际 %s" % (key, want, got))
    return problems


# Manifest 字段 → 冻结件路径属性：三份协议分别校验，不用一个通用字段代替
FILE_FIELDS = (
    ("protocol_hash", "protocol"),
    ("protocol_amendment_01_hash", "amendment_01"),
    ("protocol_amendment_02_hash", "amendment_02"),
    ("input_hash", "inputs"),
    ("rules_hash", "rules"),
    ("gold_hash", "gold"),
    ("gate_hash", "gate"),
    ("agent_needed_labels_hash", "agent_needed_labels"),
    ("label_derivation_script_hash", "label_derivation_script"),
)


def verify_files(manifest, paths=None):
    """逐个重新读盘核对冻结件哈希；返回问题清单，空表示可以运行。

    缺少文件、文件被改动都会出现在清单里——正式运行前必须先过这一关。
    """
    paths = paths or ArtifactPaths.frozen_defaults()
    problems = []
    for manifest_field, attr in FILE_FIELDS:
        want = getattr(manifest, manifest_field, None)
        target = getattr(paths, attr, None)
        if not target or not Path(target).exists():
            problems.append("%s: 文件不存在 %s" % (manifest_field, target))
            continue
        got = sha_of(target)
        if got != want:
            problems.append("%s: 期望 %s，实际 %s（%s）"
                            % (manifest_field, want, got, target))
    return problems


def to_json(manifest, path):
    Path(path).write_text(
        json.dumps(manifest.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path)
