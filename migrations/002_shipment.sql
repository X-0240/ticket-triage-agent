-- 发货事实：baseline retrieval 的第三条腿
-- 语义约定（避免"两种表示法都能用却没定义区别"）：
--   未产生发货事实      → **没有 shipment 行**（域内缺席）
--   已建物流记录未发运  → 有行，state='CREATED'
--   已发运 / 延迟 / 丢失 → 有行，state 分别 'SHIPPED' / 'DELAYED' / 'LOST'
CREATE TABLE IF NOT EXISTS shipment (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_no       VARCHAR(32) NOT NULL,
  state          ENUM('CREATED','SHIPPED','DELAYED','LOST') NOT NULL,
  carrier        VARCHAR(32) NULL,
  tracking_no    VARCHAR(64) NULL,
  exception_flag TINYINT NOT NULL DEFAULT 0,
  shipped_at     DATETIME NULL,
  last_event_at  DATETIME NULL,
  UNIQUE KEY uk_shipment_order (order_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
