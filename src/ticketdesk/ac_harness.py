"""A/C 真实接入：基础取数、路由输入、工具执行器、模型调用器（都可注入、可核验）。

分工（避免实验绕开被测对象）：

- **基础取数**走真实 `tools.py`（只读 MySQL），事实 id 由 `evidence_adapter` 统一分配，
  同一个注册表随后交给子图，因此动态取数的新事实不会和基础事实撞 id；
- **路由输入**由规则 v1 确定性算出（复用 `scripts/discovery_pilot.py` 的规则表达式，
  不另写一套），模型无权选档；
- **工具执行器**只暴露四组只读工具，并按案例绑定 `ticket_id` / `order_no`；
- **模型调用器**分两个：固定工作流判定（无工具）与子图取证（有工具），
  真实用量通过 `usage_factory` 回传给运行记录。
"""

import importlib.util
import json
from pathlib import Path

from ticketdesk import (
    evidence_adapter,
    model_client,
    prompts,
    routing,
    tools,
)

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "fixtures" / "discovery" / "rules_v1.json"

# W3 之后工具能拿到的事实（比 W1 的可用集多：发货、退款、政策、历史处置）
AVAILABLE_FACTS = {
    "subject", "body", "status", "sla_due_at", "current_queue",
    "amount", "created_at", "paid_at", "shipment",
    "shipment_state", "refund_state", "policy_title", "history_resolution",
}

# 正文里出现这些"政策/商品"类关键词时，唯一候选也必须先做一致性校验：
# 这正是第一层 Gate 复核出的 D-36~D-40（唯一命中物流组，正文其实在问保修）
SEMANTIC_KEYWORDS = ("保修", "质保", "配件", "换新", "退货", "发票", "政策",
                     "条款", "赔付标准")

TOOL_NAMES = ("get_refund_records", "search_kb", "get_ticket_history")

# 基础取数工具 → 它能提供的事实类别（规则里写的是类别名，不是字段名）
FACT_CLASS = {
    "get_ticket": {"subject", "body", "status", "sla_due_at", "current_queue"},
    "get_order": {"amount", "created_at", "paid_at", "order_line"},
    "get_shipment": {"shipment"},
}

CHECK_SYSTEM = (
    "你在做一次轻量一致性校验：给定工单正文与一个候选队列，判断两者是否一致。\n"
    "只输出 json：{\"verdict\": \"CONSISTENT|INCONSISTENT|UNCERTAIN\", "
    "\"reason\": \"<一句话>\"}\n"
    "示例 json 输出：{\"verdict\": \"INCONSISTENT\", \"reason\": "
    "\"正文在问保修政策，与物流组候选不一致\"}\n"
    "你**不能**改队列、优先级，也不能提出新候选。"
)


def _rules_engine():
    """加载规则脚本模块并扩宽可用事实集（唯一规则实现，避免两套逻辑漂移）。"""
    spec = importlib.util.spec_from_file_location(
        "ac_rules_engine", ROOT / "scripts" / "discovery_pilot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.AVAILABLE_FACTS = set(AVAILABLE_FACTS)
    return module


def load_rules():
    """规则 v1 的全部规则（queue + priority 两组），顺序即文件顺序。"""
    payload = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or []) + list(
        payload.get("priority_rules") or [])


def base_evidence(registry, case, session):
    """基础取数：只用真实只读工具，返回 (facts, order_no, tool_results)。"""
    results = [tools.get_ticket(case["ticket_id"], session)]
    body = next((fact["value"] for fact in results[0]["facts"]
                 if fact["field"] == "body"), "")
    order_no = tools.extract_order_no(body) or case.get("order_no")
    if order_no:
        results.append(tools.get_order(order_no, session))
        results.append(tools.get_shipment(order_no, session))
    facts = []
    for result in results:
        facts.extend(registry.adapt(result)["facts"])
    return facts, order_no, results


def route_input_for(case, facts, order_no, available=None, tool_failed=False):
    """按规则 v1 确定性算候选与档位输入（模型不参与）。

    `facts` 是基础取数拿到的事实；"必要事实是否齐全"按**本次执行实际取到的
    事实类别**判断，而不是看工具理论上能不能取——所以这里要先算 `available`。
    """
    engine = _rules_engine()
    rules = [rule for rule in load_rules()
             if rule.get("decision_type", "queue") == case["decision_question"]]
    fact_map = {fact["field"]: fact["value"] for fact in facts}
    body = str(fact_map.get("body") or case.get("body") or "")
    available = set(fact_map) if available is None else set(available)
    evidence = {
        "order_no": order_no,
        "shipment_found": "shipment_state" in fact_map,
    }
    candidates, unexecutable, keyword_rules, incomplete = [], [], [], []
    for rule in rules:
        status, missing = engine.rule_status(rule)
        if status == "UNEXECUTABLE":
            unexecutable.append("%s(缺%s)" % (rule["rule_id"], ",".join(missing)))
            continue
        absent = [name for name in rule["required_facts"] if name not in available]
        if absent:
            incomplete.append("%s(缺%s)" % (rule["rule_id"], ",".join(absent)))
            continue
        if not engine.evaluate(rule["rule_id"], fact_map, evidence):
            continue
        candidates.append(rule["output"])
        if rule["rule_id"] in ("R-02", "R-03", "R-05", "P-02"):
            keyword_rules.append(rule["rule_id"])
    outputs = sorted(set(candidates))
    requires_semantics = bool(keyword_rules) or any(
        keyword in body for keyword in SEMANTIC_KEYWORDS)
    return routing.RoutingInput(
        candidates=outputs,
        required_facts_complete=not unexecutable and not incomplete,
        candidate_requires_semantics=requires_semantics,
        tool_failed=tool_failed,
    )


def prepare_case(case, session, registry):
    """为一条冻结案例准备运行输入（基础事实 + 路由输入）。"""
    facts, order_no, results = base_evidence(registry, case, session)
    # 规则里写的是事实名（status / shipment / amount…），这里按"哪一类取数做过了"对齐：
    # 取过发货工具就算拿到了 shipment 这一类事实——"没有发货"本身就是业务信号
    available = set()
    for result in results:
        available |= FACT_CLASS[result["tool"]]
    available |= {fact["field"] for fact in facts}
    view = {
        "case_id": case["case_id"],
        "ticket_id": case["ticket_id"],
        "decision_question": case["decision_question"],
        "body": case.get("body"),
        "business_state": case.get("business_state"),
        "order_no": order_no,
    }
    return {
        "case_id": case["case_id"],
        "ticket_id": case["ticket_id"],
        "decision_question": case["decision_question"],
        "body": view["body"],
        "order_no": order_no,
        "base_facts": facts,
        "base_fact_ids": [fact["fact_id"] for fact in facts],
        "route_input": route_input_for(view, facts, order_no, available),
        "view": view,
        "tool_results": results,
    }


def make_executor_factory(prepared, session):
    """工具执行器：只暴露三组只读补充工具，按案例绑定业务键。"""
    view = {case["case_id"]: case for case in prepared}

    def first(args, *names):
        """模型可能用不同参数名（query / keyword / q）：认下常见写法，缺了就报清楚。"""
        for name in names:
            value = args.get(name)
            if value:
                return value
        return None

    def factory(case_id):
        case = view[case_id]

        def call(tool=None, **args):
            if tool not in TOOL_NAMES:
                raise tools.ToolError("未知工具: %s" % tool)
            if tool == "get_refund_records":
                order_no = first(args, "order_no", "order", "order_id") \
                    or case["order_no"]
                if not order_no:
                    raise tools.ToolError("get_refund_records 缺少 order_no")
                return tools.get_refund_records(order_no, session)
            if tool == "search_kb":
                query = first(args, "query", "keyword", "q", "text", "policy")
                if not query:
                    raise tools.ToolError(
                        "search_kb 缺少 query（收到参数 %s）" % sorted(args))
                return tools.search_kb(query, session)
            return tools.get_ticket_history(session, case["ticket_id"])

        return call

    return factory


class UsageRecorder:
    """一次案例一臂的 token 采集（拿不到就是 None，不记 0）。"""

    def __init__(self):
        self.tokens = None

    def add(self, usage):
        value = model_client.usage_tokens(usage)
        if value is None:
            return
        self.tokens = (self.tokens or 0) + value

    def total(self):
        return self.tokens


def make_registry_factory(registries):
    """按案例建证据适配层，并把句柄留给模型工厂。

    为什么需要这个句柄：子图取回的新事实只存在于适配层里，模型要**读到它的内容**
    才谈得上使用它。没有这一步，模型只能看到 id 列表，等于取数取了但看不见。
    """
    def factory(case):
        registry = evidence_adapter.EvidenceRegistry()
        registries[case["case_id"]] = registry
        return registry

    return factory


def make_model_factories(client, prepared, recorders, registries=None,
                         max_tokens=1200):
    """返回 (workflow_factory, agent_factory, usage_factory)。

    workflow_factory：固定工作流判定节点（没有工具，一次给结论）；
    agent_factory：子图取证（可以用工具，也可以给 final）；
    usage_factory：把真实 token 用量交给运行记录。
    """
    view = {case["case_id"]: case for case in prepared}
    registries = registries if registries is not None else {}

    def visible_facts(case_id, allowed_fact_ids):
        """本次执行里模型能看到的事实：基础事实 + 已经取回的事实正文。"""
        known = {fact["fact_id"]: fact for fact in view[case_id]["base_facts"]}
        registry = registries.get(case_id)
        if registry is not None:
            known.update(registry.facts_by_id())
        return [known[fact_id] for fact_id in allowed_fact_ids
                if fact_id in known]

    def recorder_of(case_id):
        recorder = recorders.setdefault(case_id, UsageRecorder())
        return recorder

    def workflow_factory(case_id, allowed_fact_ids):
        case = view[case_id]
        recorder = recorder_of(case_id)

        def call(allowed_fact_ids, step):
            facts = visible_facts(case_id, allowed_fact_ids)
            messages = prompts.workflow_messages(case["view"], facts)
            reply = client.complete(messages, max_tokens=max_tokens)
            recorder.add(reply["usage"])
            return {"final": model_client.parse_json_object(reply["content"])}

        return call

    def agent_factory(case_id, allowed_fact_ids):
        case = view[case_id]
        recorder = recorder_of(case_id)
        history = []

        def call(allowed_fact_ids, step):
            facts = visible_facts(case_id, allowed_fact_ids)
            messages = prompts.agent_messages(case["view"], facts, step, history)
            reply = client.complete(messages, max_tokens=max_tokens)
            recorder.add(reply["usage"])
            action = model_client.parse_json_object(reply["content"])
            if "tool" in action:
                history.append("第 %d 步：调用 %s %s" % (
                    step + 1, action.get("tool"), action.get("args")))
            else:
                history.append("第 %d 步：给出结论" % (step + 1))
            return action

        return call

    def usage_factory(case_id):
        return recorder_of(case_id).total

    return workflow_factory, agent_factory, usage_factory


def make_checker_factory(client, prepared, recorders, max_tokens=256):
    """软事实档的一致性校验器：一次模型调用，失败一律按 UNCERTAIN 处理。"""
    view = {case["case_id"]: case for case in prepared}

    def factory(case_id):
        case = view[case_id]
        recorder = recorders.setdefault(case_id, UsageRecorder())

        def checker(statement, candidate):
            messages = [
                {"role": "system", "content": CHECK_SYSTEM},
                {"role": "user", "content": "工单正文：%s\n候选队列：%s\n请给 json。"
                 % (statement or case["body"], candidate)},
            ]
            try:
                reply = client.complete(messages, max_tokens=max_tokens)
            except model_client.ModelCallError:
                # 校验器失败不能放行：按 UNCERTAIN 处理，安全转入歧义档
                return "UNCERTAIN"
            recorder.add(reply["usage"])
            try:
                verdict_value = model_client.parse_json_object(
                    reply["content"]).get("verdict")
            except model_client.ModelCallError:
                return "UNCERTAIN"
            return verdict_value if verdict_value in routing.CHECK_RESULTS \
                else "UNCERTAIN"

        return checker

    return factory
