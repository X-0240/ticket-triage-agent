"""Manifest schema：**协议版本与实际执行代码版本必须分开记录**。

评审口径：协议提交是实验规则的冻结点，不等于运行器的代码版本。运行器尚未提交时，
`runner_commit` 必须为 None，**不得把当前 HEAD 冒充成未来的执行版本**。
"""

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


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
    """一次实验的版本与哈希清单。"""

    protocol_commit: str
    runner_commit: str | None
    worktree_dirty: bool
    input_hash: str
    rules_hash: str
    gold_hash: str
    gate_hash: str
    prompt_hash: str | None = None
    model_id: str | None = None
    model_params: dict = field(default_factory=dict)

    def as_dict(self):
        return asdict(self)


def build(protocol_commit, input_path, rules_path, gold_path, gate_path,
          runner_commit=None, prompt_hash=None, model_id=None,
          model_params=None):
    return Manifest(
        protocol_commit=protocol_commit,
        runner_commit=runner_commit,
        worktree_dirty=worktree_dirty(),
        input_hash=sha_of(input_path),
        rules_hash=sha_of(rules_path),
        gold_hash=sha_of(gold_path),
        gate_hash=sha_of(gate_path),
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


def to_json(manifest, path):
    Path(path).write_text(
        json.dumps(manifest.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path)
