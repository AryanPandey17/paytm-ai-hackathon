"""SQLite ledger = system of record for exact numbers (money, stock). Cognee holds context/relationships."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .config import settings

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS merchants (
  id TEXT PRIMARY KEY, name TEXT, shop TEXT, category TEXT, city TEXT, area TEXT, language TEXT,
  phone TEXT, stage TEXT, monthly_gmv REAL DEFAULT 0, credit_limit REAL DEFAULT 0, risk_flag INTEGER DEFAULT 0,
  created TEXT
);
CREATE TABLE IF NOT EXISTS households (id TEXT PRIMARY KEY, merchant_id TEXT, name TEXT);
CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY, merchant_id TEXT, name TEXT, phone TEXT, household_id TEXT, language TEXT,
  segment TEXT, last_visit TEXT, visits_90d INTEGER, spend_90d REAL, ltv REAL, churn_risk REAL
);
CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT, customer_id TEXT, amount REAL, ts TEXT,
  method TEXT, status TEXT
);
CREATE TABLE IF NOT EXISTS udhaar (
  id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT, customer_id TEXT, amount REAL, created TEXT,
  due TEXT, status TEXT, last_nudged TEXT, nudges INTEGER DEFAULT 0, recovered REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT, sku TEXT, name TEXT, name_local TEXT,
  category TEXT, stock INTEGER, reorder_level INTEGER, price REAL, daily_velocity REAL, festival_multiplier REAL
);
CREATE TABLE IF NOT EXISTS suppliers (
  id TEXT PRIMARY KEY, name TEXT, phone TEXT, rating REAL, credit_days INTEGER, delivery_days INTEGER,
  price_index REAL, channel TEXT
);
CREATE TABLE IF NOT EXISTS leads (
  id TEXT PRIMARY KEY, name TEXT, shop TEXT, category TEXT, area TEXT, source TEXT, footfall INTEGER,
  digital_readiness REAL, fit_score REAL, status TEXT, channel TEXT, language TEXT, created TEXT
);
CREATE TABLE IF NOT EXISTS onboarding_cases (
  id TEXT PRIMARY KEY, lead_id TEXT, merchant_name TEXT, shop TEXT, tracks TEXT, exception TEXT,
  status TEXT, resolution TEXT, created TEXT
);
CREATE TABLE IF NOT EXISTS activations (
  id TEXT PRIMARY KEY, merchant_name TEXT, shop TEXT, area TEXT, device TEXT, stage TEXT,
  field_agent TEXT, issue TEXT, hours_since_delivery REAL, first_txn_at TEXT
);
CREATE TABLE IF NOT EXISTS offers (
  id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT, amount REAL, tenure_days INTEGER,
  daily_repay_pct REAL, fee REAL, status TEXT, reason TEXT, score REAL, created TEXT, decided TEXT
);
CREATE TABLE IF NOT EXISTS approvals (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, ref_id TEXT, agent TEXT, title TEXT, detail TEXT,
  amount REAL, status TEXT, channel TEXT, created TEXT, decided TEXT, decided_by TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, thread TEXT, phone TEXT, direction TEXT, sender TEXT, text TEXT,
  kind TEXT, meta TEXT, ts TEXT, via TEXT
);
CREATE TABLE IF NOT EXISTS purchase_orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT, supplier_id TEXT, items TEXT, total REAL,
  status TEXT, created TEXT, quotes TEXT
);
CREATE TABLE IF NOT EXISTS mem_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dataset TEXT, agent TEXT, text TEXT, entities TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS mem_edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dataset TEXT, src TEXT, src_type TEXT, rel TEXT, dst TEXT, dst_type TEXT,
  weight REAL DEFAULT 1, ts TEXT
);
CREATE TABLE IF NOT EXISTS plans (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT, plan TEXT, provider TEXT, ts TEXT);
"""


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(settings.db_path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.executescript(SCHEMA)
        return _conn


def q(sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    with _lock:
        cur = conn().execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def one(sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
    rows = q(sql, params)
    return rows[0] if rows else None


def x(sql: str, params: tuple | list = ()) -> int:
    with _lock:
        cur = conn().execute(sql, params)
        conn().commit()
        return cur.lastrowid


def xmany(sql: str, rows: list[tuple]) -> None:
    with _lock:
        conn().executemany(sql, rows)
        conn().commit()


def reset() -> None:
    with _lock:
        c = conn()
        tables = [r["name"] for r in q("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for t in tables:
            c.execute(f"DROP TABLE IF EXISTS {t}")
        c.executescript(SCHEMA)
        c.commit()


def dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def loads(v: str | None, default: Any = None) -> Any:
    if not v:
        return default
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return default
