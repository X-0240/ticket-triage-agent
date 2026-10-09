# 工单分诊 benchmark·盲审包 v2（只读 inputs_50.json）

v1 已作废：它由独立 derive() 重建，与快照不是同一来源。
本包内容**逐条来自 inputs_50.json**，与规则执行所用输入同源。

三条判据（冻结口径）：
1. 固定取数 + 结构化规则后仍给不出唯一结论，**或唯一候选与正文语义冲突**；
2. **必须根据工单正文语义决定下一步查什么**；
3. 该形态在真实场景存在（见 provenance，可核查）。

提醒：0 候选也可能是 agent_needed（满足②③即可）；因事实缺失造成的零命中不算。

cases：50 条

### D-01（queue）

- provenance：synthetic_with_basis#frappe/helpdesk#2658 自动分配/SLA
- scenario_type：shipment
- 工单正文：已经付款好几天了，一直没发货，订单号 O-3001。
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['履约组']（命中规则 R-01）
- 当前分桶：unique
- 输入 sha256：8c97af2dbed1dcbd4e5d09b8281b2e590be13058266130f91d18d1363e5d5e82

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['履约组']（命中规则 R-01）
- 当前分桶：unique
- 输入 sha256：5612a78d22d3df9b80a9fea60bec8a759513130b6d7e281924a6e61cf01aeae7

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['履约组']（命中规则 R-01）
- 当前分桶：unique
- 输入 sha256：b470fee7c4533e8da619d4ef3d72c56f1c4359e790189935d6ec318737682a7a

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['履约组']（命中规则 R-01）
- 当前分桶：unique
- 输入 sha256：755c4418ce66a53e4a823d16a0388fe9109fd27526da3f07ae602804a0a08fde

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['履约组']（命中规则 R-01）
- 当前分桶：unique
- 输入 sha256：31a7d3acb70f3d740c9bf682b045485d723e258cd0ff6b0e7178ef504f5c6aa3

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=DELAYED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：970f344eb5a32b8002ba86f8b6e17c300cf8f1917deb778225745f2fab6709a6

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=DELAYED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：9beff3b5ff969faf43f0f00755c18ed1b412948369104f1c7b024027cd82d45c

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=DELAYED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：b00950879e6347532cb2ff3a47af1d4fd1ab7e63b777701d3542ddce594f32ad

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=DELAYED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：a557ce305bed829628951fc5754cbb184ded584a736121b6dc2f98aa71f6cbb2

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=DELAYED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：0ae60f31d34cae3670c2ca798090150017a3ad99666161a4da3d930e662b7a7c

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=SHIPPED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：0c4a4a637853b5815bab4c8f7de815103d0f587502a3e648c652f4bbaf835e76

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=SHIPPED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：28211855cd275f0f30b89d37c851869338ac72cab3b0b208c44f96b8e821e93c

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=SHIPPED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：78df0a6941864fce56425ce10f40083777ec6bfe668599201f4f0d5d1e23adaf

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=SHIPPED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：bbd7f1b3c65701b925d3537e2421c18a0f1d649593d418116afa63b3d87d6dae

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=SHIPPED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：d5124b6dc94697c2f1f874ee0a1ea9e775b74f39991ab1ad4aad0c33300123e2

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['售后组', '履约组']（命中规则 R-01,R-02）
- 当前分桶：multi_candidate
- 输入 sha256：17bc9882c4db9ef332ee1a6047b0a18db247d93c305c6090705bfb742d92fc9a

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['售后组', '履约组']（命中规则 R-01,R-02）
- 当前分桶：multi_candidate
- 输入 sha256：6a7fef3b1a4b54c47548c4eb5f4be1eb2d24a04c5636182406de286f2d7beb9f

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['售后组', '履约组']（命中规则 R-01,R-02）
- 当前分桶：multi_candidate
- 输入 sha256：a950268b9ed2cbb9b1dda2573a1c51acca14805e39aa9762a97101703129abc1

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['售后组', '履约组']（命中规则 R-01,R-02）
- 当前分桶：multi_candidate
- 输入 sha256：254d4c12e86ad1016945859c221ea5517f9e3497903665451c8fdf24db5f3b95

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['售后组', '履约组']（命中规则 R-01,R-02）
- 当前分桶：multi_candidate
- 输入 sha256：0a64166bdf8cf5c5afbae6acc978cfdc5a5881899bce1d7f6862a3961836d0ce

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
- baseline 事实：order_found=False；order_status=None；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：b7674afc36803ccd46ba2558074e931761e5f89979660acc6acef5e3663939dc

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
- baseline 事实：order_found=False；order_status=None；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：c0ae43e986d61c9c96d72e9eb1ee7481fa8e72d32e68d1719c28c965bb018ea1

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
- baseline 事实：order_found=False；order_status=None；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：05d0ecd092973d6cd5b7aac10a876d7ab8ad6ac5f110699dbb66c80ec8a155ef

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
- baseline 事实：order_found=False；order_status=None；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：bf93a9306d2fbf097354b5dc43c642726b916a1b8a513fdb1d3c14ae887dd5fe

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
- baseline 事实：order_found=False；order_status=None；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：55594a828567d4e442f2ce0511217c8e833b3ed481c31a020c7d5bddb1399b65

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=DELAYED
- 候选结果：['售后组', '物流组']（命中规则 R-02,R-04）
- 当前分桶：multi_candidate
- 输入 sha256：bb77b20a436c3f834d968842125634b7312ddd4204854f1617ff3ac5bbcf30f8

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=DELAYED
- 候选结果：['售后组', '物流组']（命中规则 R-02,R-04）
- 当前分桶：multi_candidate
- 输入 sha256：64720ca5d871e2243c244497304b6b3c2eeafd28236a2b895ba69662777ee1ec

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=DELAYED
- 候选结果：['售后组', '物流组']（命中规则 R-02,R-04）
- 当前分桶：multi_candidate
- 输入 sha256：6fae2d23733be7e5ef503d75cd88839a2ef13cd250c745c6f7f0f38fc4895886

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=DELAYED
- 候选结果：['售后组', '物流组']（命中规则 R-02,R-04）
- 当前分桶：multi_candidate
- 输入 sha256：c4b60a2ef5c68cc1868bebe80200027a813d2b10da863068cd08e92732736d37

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=DELAYED
- 候选结果：['售后组', '物流组']（命中规则 R-02,R-04）
- 当前分桶：multi_candidate
- 输入 sha256：8d11f746bb33e950cecd6e8ffcbfbb93eb5cc606b70e7c70905383e9eb381957

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
- baseline 事实：order_found=False；order_status=None；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：c3e4c55f426325db8057260f5f52c5a55ffb44e904edbd841e38c767bcc77b2f

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
- baseline 事实：order_found=False；order_status=None；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：8fe6d19c1f9ee465c9c90896d459dc75348a2a3d865a18795b52ac1c8809375b

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
- baseline 事实：order_found=False；order_status=None；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：47cf005bded3374ce6dc1187ab18335f116f7ec68759ca2ab198e38f03d2d149

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
- baseline 事实：order_found=False；order_status=None；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：d098b0195a586bd7fe250cb91fe80c1cb53d09bfbc43ec05d63ff4262d868bda

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
- baseline 事实：order_found=False；order_status=None；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：e05dc2162506a36bac49c6719989a9564bbe5e4f1547a345b59277219f890285

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=SHIPPED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：9c8a3da047be94b30bb90212d52b13dc867a7fe1453095a59fd8948876d5e084

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=SHIPPED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：78658114232873d6844e080be1c26bec5e2e302835f3cfbd59afad9fc88050a9

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=SHIPPED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：6b05fb64bcad3d0cc136952e8c0d64171cc8e950779d2f6f42a07f379af30a1c

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=SHIPPED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：a3aa5ac2343f9219333a35608f84489be858509fac3accd074d65620129abee8

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
- baseline 事实：order_found=True；order_status=SHIPPED；shipment_found=True；shipment_state=SHIPPED
- 候选结果：['物流组']（命中规则 R-04）
- 当前分桶：unique
- 输入 sha256：a1661fb7ef73f22050eb24637021f2f0cfa92a3885abd94652bc752354376010

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：ca69bf4b081e714c59e77270227f4dfcb72103480c4f5762b5cfae8d27b2c085

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：8ab75ce8eb060da375bd762cab93ecc9bad4b7494c80ed15501703cf1be71880

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：ddf81d6916a1429e66df5f901f21296d28bdd597b831ee7b4e7183d6fa2c8b0f

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：f79fe9f91562ad9650fdb412b98260c7fd59ed530bb1c560aee8263849cde5fe

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：无候选（命中规则 无）
- 当前分桶：zero_candidate
- 输入 sha256：4bcd2818fa48a416806dbcf7d75c8d742f51dae327555e8b39d4eac71e3deb70

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['P1']（命中规则 P-02）
- 当前分桶：unique
- 输入 sha256：88079f36bf335c54d399d2dfe5e3440f89cc8f5c2cfc258e1a78eb9c4269eb01

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['P1']（命中规则 P-02）
- 当前分桶：unique
- 输入 sha256：2e2ccf26f37b9d24116069a50aaef68edecdd27f6dac1c370ef05ec96e3ddcd7

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['P1']（命中规则 P-02）
- 当前分桶：unique
- 输入 sha256：32424d8fade22f800f5a65ff44deb3d3be318cd8b3366d6a029cea9641835694

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['P1']（命中规则 P-02）
- 当前分桶：unique
- 输入 sha256：7d2b837efa5048907d5501655eeb2bdaccd7bd6c723a5a59fe8ebfacd94b40b5

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
- baseline 事实：order_found=True；order_status=PAID；shipment_found=False；shipment_state=None
- 候选结果：['P1']（命中规则 P-02）
- 当前分桶：unique
- 输入 sha256：3cac4441a4cb550d5a9e9b2111187cd072f3d2089c9e316302f6d9f0d2d2102d

```
criterion_1_met: true/false
criterion_2_met: true/false
criterion_3_met: true/false
agent_needed: true/false
required_next_lookup: <还需查什么，或 none>
reason: <一句话>
```
