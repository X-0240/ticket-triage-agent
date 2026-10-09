"""失败分类契约的正反例测试（纯逻辑）。"""

from ticketdesk import failure_contract as fc


def test_all_mapped_pairs_are_valid():
    for code, stages in fc.FAILURE_MAP.items():
        for stage in stages:
            assert fc.validate_failure(code, stage) == [], (code, stage)


def test_invalid_schema_rejects_call_stage():
    """结构错误必须说清是输出侧：不能用 model / tool 这类调用阶段冒充。"""
    for bad in ("model", "tool"):
        problems = fc.validate_failure("INVALID_SCHEMA", bad)
        assert problems, bad
    assert fc.validate_failure("INVALID_SCHEMA", "model_output") == []
    assert fc.validate_failure("INVALID_SCHEMA", "tool_result") == []


def test_missing_stage_rejected():
    assert fc.validate_failure("TOOL_FAILED", None)
    assert fc.validate_failure("INVALID_SCHEMA", None)


def test_unknown_code_rejected():
    assert fc.validate_failure("WHATEVER", "runner")


def test_semantic_codes_are_not_failure_codes():
    """语义校验错误不得写入 failure_code，应走独立的 validation_code 字段。"""
    for code in sorted(fc.SEMANTIC_CODES):
        problems = fc.validate_failure(code, None)
        assert problems and fc.VALIDATION_FIELD in problems[0]


def test_generic_timeout_requires_unknown_stage():
    assert fc.validate_failure("TIMEOUT", "unknown") == []
    assert fc.validate_failure("TIMEOUT", "model")       # 不允许冒充模型阶段
    assert fc.validate_failure("TIMEOUT", None)


def test_timeout_record_fields_are_consistent():
    """通用超时：三个字段同时填 unknown；能识别来源则用阶段化错误码。"""
    generic = fc.timeout_record_fields()
    assert generic["failure_code"] == "TIMEOUT"
    assert generic["failure_stage"] == "unknown"
    assert generic["timeout_stage"] == "unknown"
    assert fc.validate_failure(
        generic["failure_code"], generic["failure_stage"]
    ) == []

    model = fc.timeout_record_fields("model")
    assert model["failure_code"] == "MODEL_TIMEOUT"
    assert model["failure_stage"] == "model"
    assert model["timeout_stage"] == "model"
    assert fc.validate_failure(
        model["failure_code"], model["failure_stage"]
    ) == []


def test_runner_timeout_is_reserved_not_fabricated():
    """RUNNER_TIMEOUT 保留在契约里，但当前没有运行器超时机制，不应被当通用兜底。"""
    assert "RUNNER_TIMEOUT" in fc.FAILURE_MAP
    assert fc.timeout_record_fields()["failure_code"] != "RUNNER_TIMEOUT"
