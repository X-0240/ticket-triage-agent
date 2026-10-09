-- W3 最小范围：只补第一层 Gate 复核出的三种取证需求，不加别的
--   退款：refund + get_refund_records
--   政策知识：kb_article + search_kb（只返回 PUBLISHED，带来源字段）
--   商品关联：order_line（扩展现有 get_order 返回商品行）
--   历史处理：ticket.resolution 字段（历史结论），由 get_ticket_history 使用

CREATE TABLE IF NOT EXISTS order_line (
  id         BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_no   VARCHAR(32) NOT NULL,
  sku_code   VARCHAR(32) NOT NULL,
  sku_name   VARCHAR(100) NULL,
  qty        INT NOT NULL,
  unit_price DECIMAL(10,2) NOT NULL,
  KEY idx_line_order (order_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS refund (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  refund_no   VARCHAR(40) NOT NULL,
  order_no    VARCHAR(32) NOT NULL,
  amount      DECIMAL(12,2) NOT NULL,
  state       ENUM('APPLIED','APPROVED','REJECTED','REFUNDED') NOT NULL,
  reason      VARCHAR(200) NULL,
  created_at  DATETIME NOT NULL,
  UNIQUE KEY uk_refund_no (refund_no),
  KEY idx_refund_order (order_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 知识库：只查已发布且仍有效的政策；来源信息（id/版本/状态/更新时间）必须回传
CREATE TABLE IF NOT EXISTS kb_article (
  id         BIGINT PRIMARY KEY AUTO_INCREMENT,
  kb_id      VARCHAR(40) NOT NULL,
  title      VARCHAR(200) NOT NULL,
  body       TEXT NOT NULL,
  policy_type VARCHAR(40) NULL,
  version    VARCHAR(20) NOT NULL DEFAULT 'v1',
  status     ENUM('PUBLISHED','RETIRED') NOT NULL DEFAULT 'PUBLISHED',
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uk_kb_id (kb_id),
  KEY idx_kb_status (status, policy_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 历史处理结论：只给历史工单用；当前工单的 resolution 不得进入分诊输入
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'ticket'
    AND COLUMN_NAME = 'resolution'
);
SET @ddl := IF(
  @col_exists = 0,
  'ALTER TABLE ticket ADD COLUMN resolution VARCHAR(200) NULL',
  'SELECT 1'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
