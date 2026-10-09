"""数据库连接：查询走视图，写入只在种子与迁移脚本里发生。"""

import threading
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from ticketdesk import config

_local = threading.local()
_USE_DEFAULT_DB = object()


def connect(database=_USE_DEFAULT_DB):
    """建连接。

    不传 `database` → 用配置里的库；显式传 `None` → 不连任何库（建库阶段用）。
    两者必须区分开：早期版本把 `None` 当成"用默认库"，建库时就会报
    `Unknown database`。
    """
    target = config.DB_NAME if database is _USE_DEFAULT_DB else database
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=target,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
    )


def _thread_conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = connect()
        _local.conn = conn
        return conn
    try:
        conn.ping(reconnect=True)
    except Exception:
        conn = connect()
        _local.conn = conn
    return conn


@contextmanager
def tx():
    conn = _thread_conn()
    conn.begin()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def query_one(sql, params=()):
    with _thread_conn().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def query_all(sql, params=()):
    with _thread_conn().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()
