"""Manifest 契约测试：三份协议哈希分别记录，且能重新读盘核对。"""

from dataclasses import replace

from ticketdesk import evidence_manifest as em


def test_three_protocol_hashes_recorded_separately():
    """原协议与两份修订件各有自己的字段，不能用一个通用字段反复覆盖。"""
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    fields = ("protocol_hash", "protocol_amendment_01_hash",
              "protocol_amendment_02_hash")
    values = {field: getattr(manifest, field) for field in fields}
    for field, attr in zip(fields, ("protocol", "amendment_01", "amendment_02")):
        assert values[field] == em.sha_of(getattr(paths, attr))
        assert values[field]
    assert len(set(values.values())) == 3      # 三份文件三个不同哈希
    # 协议冻结点与实际执行代码版本分开记录：未跑正式实验前 runner_commit 必须为空
    assert manifest.protocol_commit == "8484f5fb"
    assert manifest.runner_commit is None


def test_gold_points_to_frozen_input_snapshot():
    """50 条对照的 gold 与输入同源（expected_* 写在输入快照里），此处显式记录。"""
    paths = em.ArtifactPaths.frozen_defaults()
    assert paths.gold == paths.inputs


def test_verify_files_passes_on_frozen_artifacts():
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    assert em.verify_files(manifest, paths) == []


def test_verify_files_detects_hash_drift():
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    tampered = replace(manifest, protocol_amendment_02_hash="deadbeef")
    problems = em.verify_files(tampered, paths)
    assert len(problems) == 1
    assert "protocol_amendment_02_hash" in problems[0]
    assert em.verify_files(tampered, paths) != em.verify_files(manifest, paths)


def test_verify_files_reports_missing_file(tmp_path):
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    missing = em.ArtifactPaths(
        protocol=str(tmp_path / "不存在.md"),
        amendment_01=paths.amendment_01,
        amendment_02=paths.amendment_02,
        inputs=paths.inputs,
        rules=paths.rules,
        gold=paths.gold,
        gate=paths.gate,
    )
    problems = em.verify_files(manifest, missing)
    assert len(problems) == 1
    assert "文件不存在" in problems[0]


def test_verify_compares_expected_subset():
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    assert em.verify(manifest, {"protocol_commit": "8484f5fb"}) == []
    problems = em.verify(manifest, {"runner_commit": "abc"})
    assert len(problems) == 1


def test_to_json_round_trips(tmp_path):
    import json

    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    target = tmp_path / "manifest.json"
    em.to_json(manifest, target)
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["protocol_amendment_01_hash"] == manifest.protocol_amendment_01_hash
    assert set(written) == set(manifest.as_dict())
