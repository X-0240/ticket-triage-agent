"""真实接入层的契约测试：提示词、模型客户端、路由输入、运行器扩展点（不联网）。"""

import json

import pytest

from ticketdesk import (
    ac_harness,
    ac_runner,
    model_client,
    prompts,
    routing,
)


def test_prompts_satisfy_json_mode_requirements():
    """DeepSeek JSON 模式要求提示词里出现 json 字样并给出示例。"""
    for text in (prompts.WORKFLOW_SYSTEM, prompts.AGENT_SYSTEM):
        assert "json" in text.lower()
        assert '"queue"' in text and '"evidence_bundle"' in text
    assert prompts.QUEUE_LIST and prompts.PRIORITY_LIST


def test_prompts_never_carry_gold():
    """真正发给模型的消息里不允许出现答案字段或标签。"""
    case = {"ticket_id": "T-9001", "decision_question": "queue",
            "body": "已经付款好几天了", "order_no": "O-3001",
            "business_state": "paid_no_shipment"}
    facts = [fact("body", case["body"], "fact_01")]
    messages = (prompts.workflow_messages(case, facts)
                + prompts.agent_messages(case, facts, 0, []))
    text = json.dumps(messages, ensure_ascii=False)
    for forbidden in ("expected_queue", "expected_priority", "expected_handoff",
                      "agent_needed"):
        assert forbidden not in text
    assert "json" in text.lower()


def test_client_payload_pins_non_thinking_and_json():
    client = model_client.DeepSeekClient()
    payload = client.payload([{"role": "user", "content": "x"}])
    assert payload["model"] == "deepseek-flash"
    assert payload["temperature"] == 0
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["stream"] is False


def test_usage_tokens_never_invents_zero():
    assert model_client.usage_tokens({}) is None
    assert model_client.usage_tokens(None) is None
    assert model_client.usage_tokens({"prompt_tokens": 10,
                                      "completion_tokens": 5}) == 15
    assert model_client.usage_tokens({"total_tokens": 42}) == 42


def test_parse_json_object_rejects_non_object():
    assert model_client.parse_json_object('{"a": 1}') == {"a": 1}
    with pytest.raises(model_client.ModelCallError) as exc:
        model_client.parse_json_object("[1, 2]")
    assert exc.value.kind == "bad_json"
    with pytest.raises(model_client.ModelCallError):
        model_client.parse_json_object("不是 json")


class FakeResponse:
    def __init__(self, body):
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_opener(body):
    def _open(request, timeout=None):
        return FakeResponse(body)
    return _open


def test_client_reports_empty_content_as_failure(monkeypatch):
    """官方说明 JSON 模式可能返回空内容：这里必须按失败处理，不能当合法输出。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-used")
    body = json.dumps({"model": "DeepSeek-V4.1-Flash",
                       "choices": [{"message": {"content": "  "}}],
                       "usage": {"prompt_tokens": 7, "completion_tokens": 0}})
    client = model_client.DeepSeekClient(opener=fake_opener(body))
    with pytest.raises(model_client.ModelCallError) as exc:
        client.complete([{"role": "user", "content": "x"}])
    assert exc.value.kind == "empty_content"


def test_client_returns_content_and_model_id(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-used")
    body = json.dumps({"model": "DeepSeek-V4.1-Flash",
                       "choices": [{"message": {"content": '{"ok": true}'}}],
                       "usage": {"prompt_tokens": 11, "completion_tokens": 3}})
    client = model_client.DeepSeekClient(opener=fake_opener(body))
    reply = client.complete([{"role": "user", "content": "x"}])
    assert reply["content"] == '{"ok": true}'
    assert reply["usage"]["prompt_tokens"] == 11
    assert client.returned_models == ["DeepSeek-V4.1-Flash"]


def test_request_body_really_carries_thinking_and_temperature(monkeypatch):
    """不只看 payload()：实际发出去的 HTTP 请求体必须带 thinking / temperature。

    我们直接发 JSON（不走 SDK），所以 `thinking` 就写在请求体里，不需要
    SDK 的 `extra_body`；这条测试用捕获到的请求字节证明这一点。
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-used")
    captured = {}

    def opener(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        headers = {key.lower(): value for key, value in request.headers.items()}
        captured["auth"] = headers.get("authorization", "")
        body = json.dumps({"model": "DeepSeek-V4.1-Flash",
                           "choices": [{"message": {"content": '{"ok": 1}'}}],
                           "usage": {}})
        return FakeResponse(body)

    client = model_client.DeepSeekClient(opener=opener)
    client.complete([{"role": "user", "content": "x"}], max_tokens=321)
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["body"]["model"] == "deepseek-flash"
    assert captured["body"]["temperature"] == 0
    assert captured["body"]["thinking"] == {"type": "disabled"}
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["max_tokens"] == 321
    assert captured["auth"].startswith("Bearer ")
    assert "test-key-not-used" not in json.dumps(captured["body"])


def test_api_key_follows_env_or_dotenv_convention(monkeypatch):
    """密钥来源遵循项目约定：环境变量，或由 config 导入时加载的项目 .env。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    assert model_client.api_key() == "dummy-key"
    # model_client 导入 config 即触发 load_dotenv(.env)，两条来源读取同一个变量
    assert model_client.config.ROOT.name == "ticket-triage-agent"


def test_missing_key_fails_before_request(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(model_client.ModelCallError) as exc:
        model_client.api_key()
    assert exc.value.kind == "missing_key"


def fact(field, value, fact_id):
    return {"fact_id": fact_id, "field": field, "value": value,
            "source": "test", "ref": "R-1"}


def synthetic_case(body, question="queue"):
    return {"case_id": "T-1", "ticket_id": "T-9001", "decision_question": question,
            "body": body, "business_state": "synthetic"}


def test_route_input_hard_when_structured_mapping_is_unambiguous():
    case = synthetic_case("已经付款好几天了，一直没发货，订单号 O-3001")
    facts = [fact("body", case["body"], "fact_01"),
             fact("status", "PAID", "fact_02")]
    state = ac_harness.route_input_for(case, facts, "O-3001",
                                       available={"body", "status", "shipment"})
    assert state.candidates == ["履约组"]
    assert routing.decide_route(state)[0] == routing.ROUTE_HARD


def test_route_input_soft_for_unique_but_policy_question():
    """唯一候选 + 正文在问保修（D-36~D-40 的形态）→ 软事实档，不是硬事实档。"""
    case = synthetic_case("收到货了，想问下保修政策")
    facts = [fact("body", case["body"], "fact_01"),
             fact("status", "SHIPPED", "fact_02"),
             fact("shipment_state", "SHIPPED", "fact_03")]
    state = ac_harness.route_input_for(case, facts, "O-3001",
                                       available={"body", "status", "shipment"})
    assert state.candidates == ["物流组"]
    assert routing.decide_route(state) == (
        routing.ROUTE_SOFT, "NEEDS_CONSISTENCY_CHECK")


def test_route_input_ambiguous_for_conflicting_signals():
    case = synthetic_case("货没到，我要退款")
    facts = [fact("body", case["body"], "fact_01"),
             fact("status", "SHIPPED", "fact_02"),
             fact("shipment_state", "DELAYED", "fact_03")]
    state = ac_harness.route_input_for(case, facts, "O-3001",
                                       available={"body", "status", "shipment"})
    assert state.candidates == ["售后组", "物流组"]
    assert routing.decide_route(state)[0] == routing.ROUTE_AMBIGUOUS


def test_route_input_marks_missing_key_facts():
    """规则需要一个当前拿不到的事实 → 不进硬事实档（FACTS_INCOMPLETE）。"""
    case = synthetic_case("已经付款好几天了，一直没发货")
    facts = [fact("body", case["body"], "fact_01")]
    # available 表示"本次执行实际取到了哪些事实类别"：只有 body 时，R-01 需要的
    # status/shipment 都没取到，不能算事实齐全
    state = ac_harness.route_input_for(case, facts, None, available={"body"})
    assert state.required_facts_complete is False
    assert routing.decide_route(state)[1] == "FACTS_INCOMPLETE"


# ---- 运行器扩展点：子图模型、软档校验器、用量采集 ----


def make_cases(ids):
    return [{"case_id": case_id, "base_fact_ids": ["fact_01"]}
            for case_id in ids]


def ambiguous_inputs(cases):
    return {case["case_id"]: routing.RoutingInput(
        candidates=["售后组", "物流组"], required_facts_complete=True,
        candidate_requires_semantics=False) for case in cases}


def soft_inputs(cases):
    return {case["case_id"]: routing.RoutingInput(
        candidates=["物流组"], required_facts_complete=True,
        candidate_requires_semantics=True) for case in cases}


class FinalModel:
    def __init__(self, case_id, allowed):
        pass

    def __call__(self, allowed_fact_ids, step):
        return {"final": {"queue": "履约组", "priority": "P1",
                          "evidence_bundle": ["fact_01"], "needs_human": True}}


def ok_executor(case_id):
    return lambda **kwargs: {"fact_ids": ["fact_new"], "facts": []}


def test_agent_model_factory_is_used_inside_subgraph():
    cases = make_cases(["D-01"])
    used = {"workflow": 0, "agent": 0}

    class Workflow:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            used["workflow"] += 1
            return {"final": {"queue": "履约组", "priority": "P1",
                              "evidence_bundle": ["fact_01"],
                              "needs_human": True}}

    class Agent:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            used["agent"] += 1
            return {"final": {"queue": "物流组", "priority": "P1",
                              "evidence_bundle": sorted(allowed_fact_ids),
                              "needs_human": True}}

    records = ac_runner.run_experiment(
        cases, ambiguous_inputs(cases), Workflow, ok_executor, {}, None,
        lambda m, e: [], agent_model_factory=Agent,
    )
    assert used == {"workflow": 1, "agent": 1}
    c = [record for record in records if record["arm"] == "C"][0]
    assert c["decision"]["queue"] == "物流组"


def test_soft_tier_consistent_stays_on_fixed_path():
    cases = make_cases(["D-01"])
    calls = {"workflow": 0, "agent": 0}

    class Workflow:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            calls["workflow"] += 1
            return {"final": {"queue": "物流组", "priority": "P1",
                              "evidence_bundle": ["fact_01"],
                              "needs_human": True}}

    class Agent:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            calls["agent"] += 1
            return {"final": {}}

    records = ac_runner.run_experiment(
        cases, soft_inputs(cases), Workflow, ok_executor, {}, None,
        lambda m, e: [], agent_model_factory=Agent,
        checker_factory=lambda case_id: (lambda statement, candidate: "CONSISTENT"),
    )
    c = [record for record in records if record["arm"] == "C"][0]
    assert c["route"] == routing.ROUTE_SOFT
    assert c["route_reason"] == "CHECK_CONSISTENT"
    assert calls["agent"] == 0


@pytest.mark.parametrize("checker_result", ["INCONSISTENT", "UNCERTAIN"])
def test_soft_tier_inconsistent_or_uncertain_enters_subgraph(checker_result):
    """软档校验不一致/不确定都必须安全转入歧义档（进子图，而不是直接放行）。"""
    cases = make_cases(["D-01"])
    entered = {"subgraph": 0}

    class Agent:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            entered["subgraph"] += 1
            return {"final": {"queue": "售后组", "priority": "P1",
                              "evidence_bundle": ["fact_01"],
                              "needs_human": True}}

    records = ac_runner.run_experiment(
        cases, soft_inputs(cases), FinalModel, ok_executor, {}, None,
        lambda m, e: [], agent_model_factory=Agent,
        checker_factory=lambda case_id: (
            lambda statement, candidate: checker_result),
    )
    c = [record for record in records if record["arm"] == "C"][0]
    assert c["route"] == routing.ROUTE_AMBIGUOUS
    assert c["route_reason"] == "CHECK_" + checker_result
    assert entered["subgraph"] == 1


def test_usage_factory_feeds_run_record():
    cases = make_cases(["D-01"])
    usage = {"D-01": 0}

    def counter():
        return usage["D-01"]

    records = ac_runner.run_experiment(
        cases, ambiguous_inputs(cases), FinalModel, ok_executor, {}, None,
        lambda m, e: [], usage_factory=lambda case_id: counter,
    )
    assert all(record["tokens"] == 0 for record in records)
    assert records[0]["tokens"] is not None      # 明确采集到 0 ≠ 拿不到用量


# ---- 协议修订 03：模型阶段故障不许记成运行器故障 ----


@pytest.mark.parametrize("kind,expected", [
    ("http_401", ("MODEL_FAILED", "model")),
    ("http_402", ("MODEL_FAILED", "model")),
    ("http_429", ("MODEL_FAILED", "model")),
    ("http_500", ("MODEL_FAILED", "model")),
    ("network", ("MODEL_FAILED", "model")),
    ("missing_key", ("MODEL_FAILED", "model")),
    ("empty_content", ("INVALID_SCHEMA", "model_output")),
    ("bad_json", ("INVALID_SCHEMA", "model_output")),
])
def test_model_call_failures_are_classified(kind, expected):
    """来源明确的模型故障按修订 03 分类；RUNNER_EXCEPTION 不再兜底。"""
    cases = make_cases(["D-01"])

    class BrokenModel:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            raise model_client.ModelCallError(kind, "脱敏摘要")

    records = ac_runner.run_experiment(
        cases, ambiguous_inputs(cases), BrokenModel, ok_executor, {}, None,
        lambda m, e: [],
    )
    for record in records:
        assert (record["failure_code"], record["failure_stage"]) == expected
        assert record["failure_code"] != "RUNNER_EXCEPTION"
        assert any(note.startswith("model_call:" + kind)
                   for note in record["notes"])


def test_model_timeout_kind_maps_to_model_timeout():
    """模型侧超时 → MODEL_TIMEOUT / model，并填 timeout_stage。"""
    cases = make_cases(["D-01"])

    class SlowModel:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            raise model_client.ModelCallError("timeout", "读超时")

    records = ac_runner.run_experiment(
        cases, ambiguous_inputs(cases), SlowModel, ok_executor, {}, None,
        lambda m, e: [],
    )
    for record in records:
        assert record["failure_code"] == "MODEL_TIMEOUT"
        assert record["failure_stage"] == "model"
        assert record["timeout_stage"] == "model"


def test_unknown_runner_exception_still_runner_exception():
    """反例保护：确属运行器自身、无法归类的异常仍记 RUNNER_EXCEPTION。"""
    cases = make_cases(["D-01"])

    class ExplodingModel:
        def __init__(self, case_id, allowed):
            pass

        def __call__(self, allowed_fact_ids, step):
            raise RuntimeError("运行器内部的意外")

    records = ac_runner.run_experiment(
        cases, ambiguous_inputs(cases), ExplodingModel, ok_executor, {}, None,
        lambda m, e: [],
    )
    for record in records:
        assert record["failure_code"] == "RUNNER_EXCEPTION"
        assert record["failure_stage"] == "runner"
