-- W1 底座（冻结范围：2 张表 + 1 个取数视图）
-- 设计原则：底座如实保存真实字段（含 current_queue），但对外取数只走 pre_triage_view，
-- 让「防 label leakage」由 SQL 强制，而不是靠流程纪律。

CREATE TABLE IF NOT EXISTS ticket (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  ticket_id     VARCHAR(32) NOT NULL,
  customer_id   VARCHAR(32) NOT NULL,
  channel       ENUM('email','web','im') NOT NULL DEFAULT 'email',
  subject       VARCHAR(200) NOT NULL,
  body          TEXT NOT NULL,
  created_at    DATETIME NOT NULL,
  sla_due_at    DATETIME NOT NULL,
  status        ENUM('OPEN','CLOSED') NOT NULL DEFAULT 'OPEN',
  -- 底座真实字段：工单系统里确实存着「当前归属队列」；
  -- 但它是处置结果，模型与评测都不得看到（见下面的视图）
  current_queue VARCHAR(32) NULL,
  UNIQUE KEY uk_ticket_id (ticket_id),
  KEY idx_ticket_customer (customer_id, created_at),
  KEY idx_ticket_status (status, sla_due_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_no    VARCHAR(32) NOT NULL,
  customer_id VARCHAR(32) NOT NULL,
  status      ENUM('CREATED','PAID','SHIPPED','CANCELLED') NOT NULL,
  amount      DECIMAL(12,2) NOT NULL,
  created_at  DATETIME NOT NULL,
  paid_at     DATETIME NULL,
  UNIQUE KEY uk_order_no (order_no),
  KEY idx_order_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 取数契约：模型与评测的**唯一**入口。
-- current_queue 在这里被固定成 unassigned，既有处置结果不可能泄漏进模型输入。
CREATE OR REPLACE VIEW pre_triage_view AS
SELECT
  ticket_id,
  customer_id,
  channel,
  subject,
  body,
  created_at,
  sla_due_at,
  status,
  'unassigned' AS current_queue
FROM ticket;
