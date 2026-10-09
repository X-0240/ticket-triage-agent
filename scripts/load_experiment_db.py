"""把派生业务世界加载进**隔离的实验库**（不碰日常库）。

评审要求：JSON 是可审计的数据源，正式运行要让真实 `tools.py` 查库，而不是让实验
执行器直接读 JSON 绕过数据库工具。因此这里新建/重建一个独立的实验库
（默认 `ticketdesk_ac_v1`，可用环境变量 `DB_NAME_AC` 覆盖），按顺序执行
`migrations/*.sql`，再把 `experiments/ac_v1/derived/business_world_v1.json` 写入。

安全边界：

1. 目标库名与日常库（`DB_NAME`）相同就直接拒绝，绝不覆盖日常数据；
2. 只 DELETE/INSERT 世界文件里声明的那几张表，不碰其他表；
3. `*_offset_hours` 按**本次加载时刻**换算成绝对时间，加载时刻会打印出来，
   供正式 Manifest 记录。

用法：python scripts/load_experiment_db.py
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticketdesk import config, db, tools  # noqa: E402

WORLD = ROOT / "experiments" / "ac_v1" / "derived" / "business_world_v1.json"
MIGRATIONS = ROOT / "migrations"
DEFAULT_TARGET = "ticketdesk_ac_v1"

# 清库顺序：先删下游表，再删被引用的表
DELETE_ORDER = ("refund", "order_line", "shipment", "orders", "kb_article",
                "ticket")
INSERT_ORDER = ("ticket", "orders", "order_line", "shipment", "refund",
                "kb_article")
PROBE_KEYWORDS = ("退款", "取消", "保修", "物流", "超时", "订单号")


class LoadError(RuntimeError):
    """加载前置条件不成立：直接失败，不产生可疑状态。"""


def target_database():
    target = os.getenv("DB_NAME_AC", DEFAULT_TARGET)
    if target == config.DB_NAME:
        raise LoadError(
            "实验库名与日常库相同（%s）：拒绝加载，避免覆盖日常数据" % target)
    return target


def create_database(target):
    conn = db.connect(database=None)
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS `%s` "
                        "DEFAULT CHARACTER SET utf8mb4" % target)
    finally:
        conn.close()


def apply_migrations(target):
    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        raise LoadError("migrations 目录里没有 .sql 文件")
    for path in files:
        sql = path.read_text(encoding="utf-8")
        conn = db.connect(database=target)
        try:
            with conn.cursor() as cur:
                for statement in [s for s in sql.split(";") if s.strip()]:
                    cur.execute(statement)
        finally:
            conn.close()
    return [path.name for path in files]


def expand_row(row, base_time):
    """把 `*_offset_hours` 展开成绝对时间字段（`*_at`）。"""
    expanded = {}
    for key, value in row.items():
        if key.endswith("_offset_hours"):
            column = key[: -len("_offset_hours")] + "_at"
            expanded[column] = (None if value is None
                                else (base_time + timedelta(hours=value)
                                      ).strftime("%Y-%m-%d %H:%M:%S"))
        else:
            expanded[key] = value
    return expanded


def load_rows(target, world, base_time):
    conn = db.connect(database=target)
    loaded = {}
    try:
        with conn.cursor() as cur:
            for table in DELETE_ORDER:
                cur.execute("DELETE FROM %s" % table)
            for table in INSERT_ORDER:
                rows = [expand_row(row, base_time)
                        for row in world["tables"][table]]
                loaded[table] = len(rows)
                if not rows:
                    continue
                columns = list(rows[0])
                placeholders = ",".join(["%s"] * len(columns))
                sql = "INSERT INTO %s (%s) VALUES (%s)" % (
                    table, ",".join(columns), placeholders)
                cur.executemany(sql, [tuple(row[col] for col in columns)
                                      for row in rows])
    finally:
        conn.close()
    return loaded


def verify(target, world, base_time):
    """核对行数、主外键关系与"工具真的查得到"。"""
    conn = db.connect(database=target)
    problems, counts = [], {}
    try:
        with conn.cursor() as cur:
            for table in INSERT_ORDER:
                cur.execute("SELECT COUNT(*) AS n FROM %s" % table)
                counts[table] = cur.fetchone()["n"]
                if counts[table] != len(world["tables"][table]):
                    problems.append("%s 行数不符: %d != %d" % (
                        table, counts[table], len(world["tables"][table])))
            for table in ("order_line", "shipment", "refund"):
                cur.execute(
                    "SELECT COUNT(*) AS n FROM %s child "
                    "LEFT JOIN orders parent ON parent.order_no=child.order_no "
                    "WHERE parent.order_no IS NULL" % table)
                orphan = cur.fetchone()["n"]
                if orphan:
                    problems.append("%s 有 %d 行没有对应订单" % (table, orphan))
            cur.execute("SELECT COUNT(*) AS n FROM ticket WHERE resolution IS NULL")
            if cur.fetchone()["n"]:
                problems.append("有工单缺少处置备注（历史取数会拿不到结论）")
            cur.execute(
                "SELECT COUNT(*) AS n FROM ticket WHERE created_at > %s",
                (base_time.strftime("%Y-%m-%d %H:%M:%S"),))
            if cur.fetchone()["n"]:
                problems.append("有工单的创建时间晚于加载时刻")
    finally:
        conn.close()

    # 让本进程后续的真实工具查询都打到实验库（而不是日常库）
    db.use_database(target)
    session = tools.Session(customer_id=world["tables"]["ticket"][0]["customer_id"])
    kb_hits = {
        keyword: bool(tools.search_kb(keyword, session)["found"])
        for keyword in PROBE_KEYWORDS
    }
    missing = [keyword for keyword, found in kb_hits.items() if not found]
    if missing:
        problems.append("知识库缺少这些关键词命中: " + ",".join(missing))
    return counts, kb_hits, problems


def main():
    target = target_database()
    world = json.loads(WORLD.read_text(encoding="utf-8"))
    if world.get("kind") != "ac_v1_business_world":
        raise LoadError("世界文件类型不对: " + str(world.get("kind")))
    base_time = datetime.now().replace(microsecond=0)
    create_database(target)
    files = apply_migrations(target)
    loaded = load_rows(target, world, base_time)
    counts, kb_hits, problems = verify(target, world, base_time)
    print("实验库 %s ｜ 迁移 %s ｜ 加载时刻 %s"
          % (target, ",".join(files), base_time))
    print("写入行数 %s" % loaded)
    print("知识库关键词命中 %s" % kb_hits)
    if problems:
        raise LoadError("加载后校验失败：\n- " + "\n- ".join(problems))
    print("校验通过：行数 %s，主外键与工具可查性均正常" % counts)


if __name__ == "__main__":
    main()
