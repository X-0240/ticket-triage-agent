"""建库建表：按文件名顺序执行 migrations/*.sql（幂等）。

用法：python scripts/migrate.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticketdesk import config, db  # noqa: E402

MIGRATIONS = ROOT / "migrations"


def main():
    conn = db.connect(database=None)
    with conn.cursor() as cur:
        cur.execute(
            "CREATE DATABASE IF NOT EXISTS `%s` "
            "DEFAULT CHARACTER SET utf8mb4" % config.DB_NAME
        )
    conn.close()

    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        raise SystemExit("migrations 目录里没有 .sql 文件")
    for path in files:
        sql = path.read_text(encoding="utf-8")
        conn = db.connect()
        with conn.cursor() as cur:
            for statement in [s for s in sql.split(";") if s.strip()]:
                cur.execute(statement)
        conn.close()
        print("[ok] %s" % path.name)
    print("迁移完成：%d 个文件，库 %s" % (len(files), config.DB_NAME))


if __name__ == "__main__":
    main()
