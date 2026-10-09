"""配置：数据库连接与取数契约的常量。

密钥只从环境变量/`.env` 读，不写死在代码里，也不打印取值。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DB_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "ticketdesk")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# 取数契约（P0）：模型与评测只看这个视图，它把 current_queue 固定成 unassigned
TICKET_VIEW = "pre_triage_view"
