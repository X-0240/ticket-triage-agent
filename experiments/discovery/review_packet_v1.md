# 工单分诊 benchmark·盲审包（v1，全 50 条）

请对每条 case 独立判断，**不要参考任何人的先前判断**；你看到的是原始材料。
每条按末尾模板回答六项：criterion_1_met / criterion_2_met / criterion_3_met / agent_needed / required_next_lookup / reason。

三条判据（冻结口径）：
1. 固定取数 + 结构化规则之后仍给不出唯一结论，**或规则给出唯一候选但与正文语义冲突**；
2. **必须根据工单正文语义决定下一步查什么**；
3. 该形态在真实场景存在（见每条附的 provenance，可核查）。

两条提醒：
- **0 候选（zero_candidate）也可能是 agent_needed**，只要同时满足 ②③；
- 但**因工具/事实缺失造成的**零命中不算——本包已把这类（UNEXECUTABLE）排除。

cases：50 条（含 unique / zero_candidate / multi_candidate，随机顺序即按 id）

### D-01（queue）

- provenance：synthetic_with_basis#frappe/helpdesk#2658 自动分配/SLA
- scenario_type：shipment
- 工单正文：已经付款好几天了，一直没发货，订单号 O-3001。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：['履约组']（命中规则 R-01）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['shipment', 'status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-02（queue）

- provenance：synthetic_with_basis#frappe/helpdesk#2658 自动分配/SLA
- scenario_type：shipment
- 工单正文：已经付款好几天了，一直没发货，这已经是第二次了，实在受不了，订单号 O-3002。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：['履约组']（命中规则 R-01）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['shipment', 'status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-03（queue）

- provenance：synthetic_with_basis#frappe/helpdesk#2658 自动分配/SLA
- scenario_type：shipment
- 工单正文：5 天前下的单，中间一直没消息，现在已经付款好几天了，一直没发货，订单号 O-3003。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：['履约组']（命中规则 R-01）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['shipment', 'status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-04（queue）

- provenance：synthetic_with_basis#frappe/helpdesk#2658 自动分配/SLA
- scenario_type：shipment
- 工单正文：订单 O-3004 到底要拖多久？已经付款好几天了，一直没发货，你们到底管不管？
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：['履约组']（命中规则 R-01）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['shipment', 'status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-05（queue）

- provenance：synthetic_with_basis#frappe/helpdesk#2658 自动分配/SLA
- scenario_type：shipment
- 工单正文：已经付款好几天了，一直没发货，具体订单号我一时找不到了。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-06（queue）

- provenance：synthetic_with_basis#物流异常形态
- scenario_type：shipment
- 工单正文：物流卡在中转站好几天没动静，订单号 O-3006。
- baseline 事实：order.status=SHIPPED；shipment.state=DELAYED；shipment.exception_flag=1
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-07（queue）

- provenance：synthetic_with_basis#物流异常形态
- scenario_type：shipment
- 工单正文：物流卡在中转站好几天没动静，这已经是第二次了，实在受不了，订单号 O-3007。
- baseline 事实：order.status=SHIPPED；shipment.state=DELAYED；shipment.exception_flag=1
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-08（queue）

- provenance：synthetic_with_basis#物流异常形态
- scenario_type：shipment
- 工单正文：5 天前下的单，中间一直没消息，现在物流卡在中转站好几天没动静，订单号 O-3008。
- baseline 事实：order.status=SHIPPED；shipment.state=DELAYED；shipment.exception_flag=1
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-09（queue）

- provenance：synthetic_with_basis#物流异常形态
- scenario_type：shipment
- 工单正文：订单 O-3009 到底要拖多久？物流卡在中转站好几天没动静，你们到底管不管？
- baseline 事实：order.status=SHIPPED；shipment.state=DELAYED；shipment.exception_flag=1
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-10（queue）

- provenance：synthetic_with_basis#物流异常形态
- scenario_type：shipment
- 工单正文：物流卡在中转站好几天没动静，具体订单号我一时找不到了。
- baseline 事实：order.status=SHIPPED；shipment.state=DELAYED；shipment.exception_flag=1
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-11（queue）

- provenance：synthetic_with_basis#正常在途
- scenario_type：shipment
- 工单正文：想确认一下包裹走到哪了，订单号 O-3011。
- baseline 事实：order.status=SHIPPED；shipment.state=SHIPPED；shipment.exception_flag=0
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-12（queue）

- provenance：synthetic_with_basis#正常在途
- scenario_type：shipment
- 工单正文：想确认一下包裹走到哪了，这已经是第二次了，实在受不了，订单号 O-3012。
- baseline 事实：order.status=SHIPPED；shipment.state=SHIPPED；shipment.exception_flag=0
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-13（queue）

- provenance：synthetic_with_basis#正常在途
- scenario_type：shipment
- 工单正文：5 天前下的单，中间一直没消息，现在想确认一下包裹走到哪了，订单号 O-3013。
- baseline 事实：order.status=SHIPPED；shipment.state=SHIPPED；shipment.exception_flag=0
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-14（queue）

- provenance：synthetic_with_basis#正常在途
- scenario_type：shipment
- 工单正文：订单 O-3014 到底要拖多久？想确认一下包裹走到哪了，你们到底管不管？
- baseline 事实：order.status=SHIPPED；shipment.state=SHIPPED；shipment.exception_flag=0
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-15（queue）

- provenance：synthetic_with_basis#正常在途
- scenario_type：shipment
- 工单正文：想确认一下包裹走到哪了，具体订单号我一时找不到了。
- baseline 事实：order.status=SHIPPED；shipment.state=SHIPPED；shipment.exception_flag=0
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-16（queue）

- provenance：synthetic_with_basis#chatwoot#13543 退款诉求
- scenario_type：refund
- 工单正文：不想要了，希望退款，订单号 O-3016。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：['售后组', '履约组']（命中规则 R-01,R-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body', 'shipment', 'status']
- 当前分桶：multi_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-17（queue）

- provenance：synthetic_with_basis#chatwoot#13543 退款诉求
- scenario_type：refund
- 工单正文：不想要了，希望退款，这已经是第二次了，实在受不了，订单号 O-3017。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：['售后组', '履约组']（命中规则 R-01,R-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body', 'shipment', 'status']
- 当前分桶：multi_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-18（queue）

- provenance：synthetic_with_basis#chatwoot#13543 退款诉求
- scenario_type：refund
- 工单正文：5 天前下的单，中间一直没消息，现在不想要了，希望退款，订单号 O-3018。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：['售后组', '履约组']（命中规则 R-01,R-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body', 'shipment', 'status']
- 当前分桶：multi_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-19（queue）

- provenance：synthetic_with_basis#chatwoot#13543 退款诉求
- scenario_type：refund
- 工单正文：订单 O-3019 到底要拖多久？不想要了，希望退款，你们到底管不管？
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：['售后组', '履约组']（命中规则 R-01,R-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body', 'shipment', 'status']
- 当前分桶：multi_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-20（queue）

- provenance：synthetic_with_basis#chatwoot#13543 退款诉求
- scenario_type：refund
- 工单正文：不想要了，希望退款，具体订单号我一时找不到了。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：['售后组']（命中规则 R-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-21（queue）

- provenance：issue_derived#frappe/helpdesk#2658
- scenario_type：none
- 工单正文：我这个情况该怎么办，订单号 O-3021。
- baseline 事实：order=（查不到该订单）；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-22（queue）

- provenance：issue_derived#frappe/helpdesk#2658
- scenario_type：none
- 工单正文：我这个情况该怎么办，这已经是第二次了，实在受不了，订单号 O-3022。
- baseline 事实：order=（查不到该订单）；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-23（queue）

- provenance：issue_derived#frappe/helpdesk#2658
- scenario_type：none
- 工单正文：5 天前下的单，中间一直没消息，现在我这个情况该怎么办，订单号 O-3023。
- baseline 事实：order=（查不到该订单）；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-24（queue）

- provenance：issue_derived#frappe/helpdesk#2658
- scenario_type：none
- 工单正文：订单 O-3024 到底要拖多久？我这个情况该怎么办，你们到底管不管？
- baseline 事实：order=（查不到该订单）；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-25（queue）

- provenance：issue_derived#frappe/helpdesk#2658
- scenario_type：none
- 工单正文：我这个情况该怎么办，具体订单号我一时找不到了。
- baseline 事实：order=（查不到该订单）；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-26（queue）

- provenance：issue_derived#frappe/helpdesk#3465 重开单与指标失真
- scenario_type：mixed
- 工单正文：货没到还要退款，上次也没人处理，订单号 O-3026。
- baseline 事实：order.status=SHIPPED；shipment.state=DELAYED；shipment.exception_flag=1
- 判定问题：queue
- 候选结果：['售后组', '物流组']（命中规则 R-02,R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body', 'status']
- 当前分桶：multi_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-27（queue）

- provenance：issue_derived#frappe/helpdesk#3465 重开单与指标失真
- scenario_type：mixed
- 工单正文：货没到还要退款，上次也没人处理，这已经是第二次了，实在受不了，订单号 O-3027。
- baseline 事实：order.status=SHIPPED；shipment.state=DELAYED；shipment.exception_flag=1
- 判定问题：queue
- 候选结果：['售后组', '物流组']（命中规则 R-02,R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body', 'status']
- 当前分桶：multi_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-28（queue）

- provenance：issue_derived#frappe/helpdesk#3465 重开单与指标失真
- scenario_type：mixed
- 工单正文：5 天前下的单，中间一直没消息，现在货没到还要退款，上次也没人处理，订单号 O-3028。
- baseline 事实：order.status=SHIPPED；shipment.state=DELAYED；shipment.exception_flag=1
- 判定问题：queue
- 候选结果：['售后组', '物流组']（命中规则 R-02,R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body', 'status']
- 当前分桶：multi_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-29（queue）

- provenance：issue_derived#frappe/helpdesk#3465 重开单与指标失真
- scenario_type：mixed
- 工单正文：订单 O-3029 到底要拖多久？货没到还要退款，上次也没人处理，你们到底管不管？
- baseline 事实：order.status=SHIPPED；shipment.state=DELAYED；shipment.exception_flag=1
- 判定问题：queue
- 候选结果：['售后组', '物流组']（命中规则 R-02,R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body', 'status']
- 当前分桶：multi_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-30（queue）

- provenance：issue_derived#frappe/helpdesk#3465 重开单与指标失真
- scenario_type：mixed
- 工单正文：货没到还要退款，上次也没人处理，具体订单号我一时找不到了。
- baseline 事实：order.status=SHIPPED；shipment.state=DELAYED；shipment.exception_flag=1
- 判定问题：queue
- 候选结果：['售后组']（命中规则 R-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-31（queue）

- provenance：synthetic_with_basis#数据不存在形态
- scenario_type：missing_data
- 工单正文：帮我查一下那个订单，订单号 O-9999。
- baseline 事实：order=（查不到该订单）；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-32（queue）

- provenance：synthetic_with_basis#数据不存在形态
- scenario_type：missing_data
- 工单正文：帮我查一下那个订单，这已经是第二次了，实在受不了，订单号 O-9999。
- baseline 事实：order=（查不到该订单）；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-33（queue）

- provenance：synthetic_with_basis#数据不存在形态
- scenario_type：missing_data
- 工单正文：5 天前下的单，中间一直没消息，现在帮我查一下那个订单，订单号 O-9999。
- baseline 事实：order=（查不到该订单）；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-34（queue）

- provenance：synthetic_with_basis#数据不存在形态
- scenario_type：missing_data
- 工单正文：订单 O-9999 到底要拖多久？帮我查一下那个订单，你们到底管不管？
- baseline 事实：order=（查不到该订单）；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-35（queue）

- provenance：synthetic_with_basis#数据不存在形态
- scenario_type：missing_data
- 工单正文：帮我查一下那个订单，具体订单号我一时找不到了。
- baseline 事实：order=（查不到该订单）；shipment=（无发货记录）
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-36（queue）

- provenance：synthetic_with_basis#咨询形态
- scenario_type：policy
- 工单正文：收到货了，想问下保修政策，订单号 O-3036。
- baseline 事实：order.status=SHIPPED；shipment.state=SHIPPED；shipment.exception_flag=0
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-37（queue）

- provenance：synthetic_with_basis#咨询形态
- scenario_type：policy
- 工单正文：收到货了，想问下保修政策，这已经是第二次了，实在受不了，订单号 O-3037。
- baseline 事实：order.status=SHIPPED；shipment.state=SHIPPED；shipment.exception_flag=0
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-38（queue）

- provenance：synthetic_with_basis#咨询形态
- scenario_type：policy
- 工单正文：5 天前下的单，中间一直没消息，现在收到货了，想问下保修政策，订单号 O-3038。
- baseline 事实：order.status=SHIPPED；shipment.state=SHIPPED；shipment.exception_flag=0
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-39（queue）

- provenance：synthetic_with_basis#咨询形态
- scenario_type：policy
- 工单正文：订单 O-3039 到底要拖多久？收到货了，想问下保修政策，你们到底管不管？
- baseline 事实：order.status=SHIPPED；shipment.state=SHIPPED；shipment.exception_flag=0
- 判定问题：queue
- 候选结果：['物流组']（命中规则 R-04）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['status']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-40（queue）

- provenance：synthetic_with_basis#咨询形态
- scenario_type：policy
- 工单正文：收到货了，想问下保修政策，具体订单号我一时找不到了。
- baseline 事实：order.status=SHIPPED；shipment.state=SHIPPED；shipment.exception_flag=0
- 判定问题：queue
- 候选结果：无候选（命中规则 无）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：无
- 当前分桶：zero_candidate

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-41（priority）

- provenance：synthetic_with_basis#SLA 临近（benchmark policy）
- scenario_type：sla
- 工单正文：有点着急，麻烦尽快处理，订单号 O-3041。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：priority
- 候选结果：['P0']（命中规则 P-01）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['sla_due_at']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-42（priority）

- provenance：synthetic_with_basis#SLA 临近（benchmark policy）
- scenario_type：sla
- 工单正文：有点着急，麻烦尽快处理，这已经是第二次了，实在受不了，订单号 O-3042。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：priority
- 候选结果：['P0']（命中规则 P-01）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['sla_due_at']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-43（priority）

- provenance：synthetic_with_basis#SLA 临近（benchmark policy）
- scenario_type：sla
- 工单正文：5 天前下的单，中间一直没消息，现在有点着急，麻烦尽快处理，订单号 O-3043。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：priority
- 候选结果：['P0']（命中规则 P-01）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['sla_due_at']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-44（priority）

- provenance：synthetic_with_basis#SLA 临近（benchmark policy）
- scenario_type：sla
- 工单正文：订单 O-3044 到底要拖多久？有点着急，麻烦尽快处理，你们到底管不管？
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：priority
- 候选结果：['P0']（命中规则 P-01）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['sla_due_at']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-45（priority）

- provenance：synthetic_with_basis#SLA 临近（benchmark policy）
- scenario_type：sla
- 工单正文：有点着急，麻烦尽快处理，具体订单号我一时找不到了。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：priority
- 候选结果：['P0']（命中规则 P-01）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['sla_due_at']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-46（priority）

- provenance：issue_derived#frappe/helpdesk#3465
- scenario_type：refund
- 工单正文：希望尽快退款，订单号 O-3046。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：priority
- 候选结果：['P1']（命中规则 P-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-47（priority）

- provenance：issue_derived#frappe/helpdesk#3465
- scenario_type：refund
- 工单正文：希望尽快退款，这已经是第二次了，实在受不了，订单号 O-3047。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：priority
- 候选结果：['P1']（命中规则 P-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-48（priority）

- provenance：issue_derived#frappe/helpdesk#3465
- scenario_type：refund
- 工单正文：5 天前下的单，中间一直没消息，现在希望尽快退款，订单号 O-3048。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：priority
- 候选结果：['P1']（命中规则 P-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-49（priority）

- provenance：issue_derived#frappe/helpdesk#3465
- scenario_type：refund
- 工单正文：订单 O-3049 到底要拖多久？希望尽快退款，你们到底管不管？
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：priority
- 候选结果：['P1']（命中规则 P-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```

### D-50（priority）

- provenance：issue_derived#frappe/helpdesk#3465
- scenario_type：refund
- 工单正文：希望尽快退款，具体订单号我一时找不到了。
- baseline 事实：order.status=PAID；shipment=（无发货记录）
- 判定问题：priority
- 候选结果：['P1']（命中规则 P-02）
- 可用事实：order.status/amount、shipment.state/exception_flag、ticket.body/sla_due_at
- 命中规则所需事实：['body']
- 当前分桶：unique

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```
