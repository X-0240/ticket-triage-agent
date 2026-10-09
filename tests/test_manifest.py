"""Manifest 契约测试：三份协议哈希分别记录，且能重新读盘核对。"""

from dataclasses import replace

from ticketdesk import evidence_manifest as em


def test_protocol_hashes_recorded_separately():
    """原协议与三份修订件各有自己的字段，不能用一个通用字段反复覆盖。"""
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    fields = ("protocol_hash", "protocol_amendment_01_hash",
              "protocol_amendment_02_hash", "protocol_amendment_03_hash")
    values = {field: getattr(manifest, field) for field in fields}
    for field, attr in zip(fields, ("protocol", "amendment_01", "amendment_02",
                                    "amendment_03")):
        assert values[field] == em.sha_of(getattr(paths, attr))
        assert values[field]
    assert len(set(values.values())) == 4      # 四份文件四个不同哈希
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


def test_derived_labels_and_script_are_hashed():
    """正式运行用的是派生标签件：它和派生脚本的哈希都要进 Manifest 并被核验。"""
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    assert manifest.agent_needed_labels_hash == em.sha_of(
        paths.agent_needed_labels)
    assert manifest.label_derivation_script_hash == em.sha_of(
        paths.label_derivation_script)
    assert manifest.agent_needed_labels_hash != manifest.gate_hash
    drifted = replace(manifest, agent_needed_labels_hash="deadbeef")
    problems = em.verify_files(drifted, paths)
    assert len(problems) == 1
    assert "agent_needed_labels_hash" in problems[0]


def test_business_world_and_loader_are_hashed():
    """正式运行还要记录业务世界与数据加载器的哈希，并逐项核验。"""
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    assert manifest.business_world_hash == em.sha_of(paths.business_world)
    assert manifest.data_loader_hash == em.sha_of(paths.data_loader)
    for field in ("business_world_hash", "data_loader_hash"):
        drifted = replace(manifest, **{field: "deadbeef"})
        problems = em.verify_files(drifted, paths)
        assert len(problems) == 1 and field in problems[0]


def test_manifest_records_experiment_db_and_prompt_hash():
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(
        paths, protocol_commit="8484f5fb", prompt_hash="p9",
        model_id="deepseek-flash", model_params={"temperature": 0},
        experiment_db="ticketdesk_ac_v1", db_loaded_at="2026-10-10 03:00:26",
    )
    written = manifest.as_dict()
    assert written["experiment_db"] == "ticketdesk_ac_v1"
    assert written["db_loaded_at"] == "2026-10-10 03:00:26"
    assert written["prompt_hash"] == "p9"
    assert written["model_id"] == "deepseek-flash"


def test_verify_files_detects_hash_drift():
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    tampered = replace(manifest, protocol_amendment_02_hash="deadbeef")
    problems = em.verify_files(tampered, paths)
    assert len(problems) == 1
    assert "protocol_amendment_02_hash" in problems[0]
    assert em.verify_files(tampered, paths) != em.verify_files(manifest, paths)


def test_amendment_03_hash_is_recorded_and_verified():
    """修订 03（模型失败分类）也要进 Manifest 并被核验。"""
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    assert manifest.protocol_amendment_03_hash == em.sha_of(paths.amendment_03)
    drifted = replace(manifest, protocol_amendment_03_hash="deadbeef")
    problems = em.verify_files(drifted, paths)
    assert len(problems) == 1
    assert "protocol_amendment_03_hash" in problems[0]


def test_verify_files_reports_missing_file(tmp_path):
    paths = em.ArtifactPaths.frozen_defaults()
    manifest = em.build(paths, protocol_commit="8484f5fb")
    missing = em.ArtifactPaths(
        protocol=str(tmp_path / "不存在.md"),
        amendment_01=paths.amendment_01,
        amendment_02=paths.amendment_02,
        amendment_03=paths.amendment_03,
        inputs=paths.inputs,
        rules=paths.rules,
        gold=paths.gold,
        gate=paths.gate,
        agent_needed_labels=paths.agent_needed_labels,
        label_derivation_script=paths.label_derivation_script,
        business_world=paths.business_world,
        data_loader=paths.data_loader,
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
