"""派生标签件契约测试：原件哈希锁死、缺陷恰好一次、派生可复现、覆盖完整。"""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from ticketdesk import ac_scoring, evidence_manifest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "derive_agent_needed_labels.py"


def load_script():
    """把派生脚本当模块加载（脚本自身不 import 本项目代码，无副作用）。"""
    spec = importlib.util.spec_from_file_location("derive_labels", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_cases():
    paths = evidence_manifest.ArtifactPaths.frozen_defaults()
    payload = json.loads(Path(paths.inputs).read_text(encoding="utf-8"))
    return payload["cases"]


def test_frozen_gate_file_is_still_broken_and_untouched():
    """原件保持原样：哈希对得上，且它确实不是合法 JSON（缺陷是真实的）。"""
    module = load_script()
    raw = module.SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == module.EXPECTED_SOURCE_SHA256
    text = raw.decode("utf-8")
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    assert text.count(module.DEFECT) == 1
    # 内存修正后是合法 JSON：证明"唯一缺陷"这一判断本身成立
    json.loads(text.replace(module.DEFECT, module.FIXED))


def test_derivation_is_reproducible_and_matches_committed_file():
    """重新派生必须与已提交的派生件逐字节一致。"""
    module = load_script()
    committed = module.OUT.read_text(encoding="utf-8")
    assert module.render(module.derive()) == committed
    payload = json.loads(committed)
    assert payload["frozen_cases"] == 50
    assert payload["agent_needed_true"] == 15
    assert payload["source"]["file"] == (
        "experiments/discovery/gate_v1_decision.json")
    assert payload["source"]["sha256"] == module.EXPECTED_SOURCE_SHA256
    assert payload["derivation_script"]["sha256"] == hashlib.sha256(
        SCRIPT.read_bytes()).hexdigest()


def test_derivation_refuses_unknown_source_bytes(tmp_path, monkeypatch):
    """原件被改动（哈希不符）→ 直接失败，不做宽松解析。"""
    module = load_script()
    other = tmp_path / "gate.json"
    other.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "SOURCE", other)
    with pytest.raises(module.DerivationError) as exc:
        module.derive()
    assert "哈希不匹配" in str(exc.value)


def test_derivation_requires_exactly_one_occurrence(tmp_path, monkeypatch):
    """缺陷出现 0 次或多次都必须失败：不允许凭印象挑一处改。"""
    module = load_script()
    fixed = module.SOURCE.read_text(encoding="utf-8").replace(
        module.DEFECT, module.FIXED)
    already_fixed = tmp_path / "already_fixed.json"
    already_fixed.write_text(fixed, encoding="utf-8", newline="\n")
    monkeypatch.setattr(module, "SOURCE", already_fixed)
    monkeypatch.setattr(module, "EXPECTED_SOURCE_SHA256",
                        hashlib.sha256(fixed.encode("utf-8")).hexdigest())
    with pytest.raises(module.DerivationError) as exc:
        module.derive()
    assert "恰好出现 1 次" in str(exc.value)
    assert "实际 0 次" in str(exc.value)

    doubled = tmp_path / "doubled.json"
    doubled.write_text(fixed + "\n" + module.DEFECT, encoding="utf-8",
                       newline="\n")
    monkeypatch.setattr(module, "SOURCE", doubled)
    monkeypatch.setattr(
        module, "EXPECTED_SOURCE_SHA256",
        hashlib.sha256(doubled.read_bytes()).hexdigest())
    with pytest.raises(module.DerivationError) as exc:
        module.derive()
    assert "实际 1 次" not in str(exc.value)


def test_pattern_ranges_match_declared_labels():
    """动态模式的案例区间必须与 agent_needed 列表完全一致（3 个模式 × 5 条）。"""
    module = load_script()
    payload = module.derive()
    pattern_cases = [case_id for item in payload["patterns"]
                     for case_id in item["cases"]]
    assert len(payload["patterns"]) == 3
    assert sorted(pattern_cases) == sorted(payload["agent_needed_cases"])
    for item in payload["patterns"]:
        assert len(item["cases"]) == 5
        assert item["name"]


def test_load_labels_covers_all_frozen_cases():
    paths = evidence_manifest.ArtifactPaths.frozen_defaults()
    loaded = ac_scoring.load_labels(paths.agent_needed_labels, frozen_cases())
    assert len(loaded["agent_needed"]) == 15
    assert set(loaded["patterns"]) == set(loaded["agent_needed"])
    assert set(loaded["patterns"].values()) == {
        "履约状态 + 退款资格/取消规则 联合判断",
        "物流异常详情 + 退款规则 + 历史处理记录",
        "保修条款核查 + 商品关联",
    }


def test_load_labels_rejects_incomplete_coverage(tmp_path):
    """少一条案例的标签也要报错，不能静默当成 false。"""
    paths = evidence_manifest.ArtifactPaths.frozen_defaults()
    payload = json.loads(Path(paths.agent_needed_labels).read_text(
        encoding="utf-8"))
    payload["labels"].pop("D-01")
    broken = tmp_path / "labels.json"
    broken.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        ac_scoring.load_labels(broken, frozen_cases())
    assert "覆盖不齐" in str(exc.value)


def test_load_labels_rejects_count_mismatch(tmp_path):
    paths = evidence_manifest.ArtifactPaths.frozen_defaults()
    payload = json.loads(Path(paths.agent_needed_labels).read_text(
        encoding="utf-8"))
    payload["agent_needed_true"] = 14
    broken = tmp_path / "labels.json"
    broken.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        ac_scoring.load_labels(broken, frozen_cases())
    assert "agent_needed_true" in str(exc.value)
