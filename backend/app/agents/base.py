"""Shared helpers for agents: ledger queries, fuzzy matching, dates."""
from __future__ import annotations

import difflib
import re
from datetime import date, datetime, timedelta
from typing import Any

from .. import db

FESTIVALS = [  # (name, date) - extend as needed
    ("Diwali", date(2026, 11, 8)),
    ("Bhai Dooj", date(2026, 11, 11)),
    ("Christmas", date(2026, 12, 25)),
    ("Makar Sankranti", date(2027, 1, 14)),
    ("Holi", date(2027, 3, 22)),
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def inr(v: float) -> str:
    v = round(v)
    s = str(abs(int(v)))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        s = head + "," + tail
    return ("-" if v < 0 else "") + "₹" + s


def merchant(mid: str) -> dict[str, Any]:
    m = db.one("SELECT * FROM merchants WHERE id=?", (mid,))
    if not m:
        raise KeyError(f"merchant {mid} not found")
    return m


def merchant_by_phone(phone: str) -> dict[str, Any] | None:
    return db.one("SELECT * FROM merchants WHERE phone=?", (phone,))


def customer_by_phone(phone: str) -> dict[str, Any] | None:
    return db.one("SELECT * FROM customers WHERE phone=?", (phone,))


def next_festival(today: date | None = None) -> tuple[str, int]:
    today = today or date.today()
    for name, d in FESTIVALS:
        if d >= today:
            return name, (d - today).days
    return FESTIVALS[0][0], 365


def sales_stats(mid: str) -> dict[str, Any]:
    def total(days_from: int, days_to: int = 0) -> float:
        r = db.one(
            "SELECT COALESCE(SUM(amount),0) s FROM transactions WHERE merchant_id=? AND status='success' "
            "AND method!='udhaar' AND ts >= ? AND ts < ?",
            (mid, (datetime.now() - timedelta(days=days_from)).isoformat(), (datetime.now() - timedelta(days=days_to)).isoformat()))
        return float(r["s"])

    last7, prev7, last30, last90 = total(7), total(14, 7), total(30), total(90)
    upi30 = float(db.one(
        "SELECT COALESCE(SUM(amount),0) s FROM transactions WHERE merchant_id=? AND method='upi' AND status='success' AND ts>=?",
        (mid, (datetime.now() - timedelta(days=30)).isoformat()))["s"])
    daily = db.q(
        "SELECT substr(ts,1,10) day, SUM(CASE WHEN status='success' AND method!='udhaar' THEN amount ELSE 0 END) total, "
        "SUM(CASE WHEN method='upi' AND status='success' THEN amount ELSE 0 END) upi, COUNT(*) txns "
        "FROM transactions WHERE merchant_id=? AND ts>=? AND ts<? GROUP BY day ORDER BY day",
        (mid, (datetime.now() - timedelta(days=90)).isoformat(), date.today().isoformat()))  # full days only
    vals = [d["total"] for d in daily] or [0]
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    return {
        "last7": last7, "prev7": prev7, "wow_pct": ((last7 - prev7) / prev7 * 100) if prev7 else 0,
        "last30": last30, "last90": last90, "avg_daily": last30 / 30, "upi_share": (upi30 / last30) if last30 else 0,
        "volatility": (var ** 0.5 / mean) if mean else 0, "daily": daily,
    }


def open_udhaar(mid: str) -> list[dict[str, Any]]:
    return db.q(
        "SELECT u.*, c.name, c.phone, c.segment, c.language, c.household_id FROM udhaar u JOIN customers c ON c.id=u.customer_id "
        "WHERE u.merchant_id=? AND u.status='open' ORDER BY u.amount DESC", (mid,))


def match_customer(mid: str, hint: str, pool: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    if not hint:
        return None
    pool = pool if pool is not None else db.q("SELECT * FROM customers WHERE merchant_id=?", (mid,))
    h = hint.lower().replace(" ji", "").replace("ji", "").strip()
    for c in pool:
        if h and h in c["name"].lower():
            return c
    names = {c["name"].lower(): c for c in pool}
    best = difflib.get_close_matches(h, list(names), n=1, cutoff=0.4)
    if best:
        return names[best[0]]
    for c in pool:
        for tok in c["name"].lower().replace("(", " ").replace(")", " ").split():
            if difflib.SequenceMatcher(None, h, tok).ratio() > 0.8:
                return c
    return None


PRODUCT_SYNONYMS = {
    "atta": "ATTA10", "aata": "ATTA10", "आटा": "ATTA10", "flour": "ATTA10", "gehu": "ATTA10",
    "chawal": "RICE5", "rice": "RICE5", "चावल": "RICE5", "basmati": "RICE5",
    "dal": "TOORDAL", "daal": "TOORDAL", "दाल": "TOORDAL", "toor": "TOORDAL",
    "cheeni": "SUGAR5", "chini": "SUGAR5", "sugar": "SUGAR5", "चीनी": "SUGAR5", "shakkar": "SUGAR5",
    "tel": "OIL1", "oil": "OIL1", "तेल": "OIL1",
    "ghee": "GHEE1", "ghi": "GHEE1", "घी": "GHEE1",
    "besan": "BESAN1", "बेसन": "BESAN1", "maida": "MAIDA1",
    "diya": "DIYA", "diye": "DIYA", "diyas": "DIYA", "दीये": "DIYA", "दिया": "DIYA",
    "rangoli": "RANGOLI", "kaju": "DRYFRT", "badam": "DRYFRT", "dry fruit": "DRYFRT", "dryfruit": "DRYFRT",
    "soan papdi": "SWEETS", "mithai": "SWEETS", "sweets": "SWEETS",
    "chai": "TEA500", "tea": "TEA500", "chai patti": "TEA500", "coffee": "COFFEE",
    "maggi": "MAGGI", "biscuit": "BISCUIT", "parle": "BISCUIT", "bhujia": "NAMKEEN", "namkeen": "NAMKEEN",
    "sabun": "SOAP", "soap": "SOAP", "shampoo": "SHAMPOO", "surf": "DETERGENT", "detergent": "DETERGENT",
    "namak": "SALT", "salt": "SALT", "gud": "JAGGERY", "jaggery": "JAGGERY", "agarbatti": "AGARBATTI",
    "candle": "CANDLES", "mombatti": "CANDLES", "doodh powder": "MILKPWD", "milk powder": "MILKPWD",
}


def match_products(mid: str, text: str) -> list[dict[str, Any]]:
    t = text.lower()
    skus = []
    for k, sku in sorted(PRODUCT_SYNONYMS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"(?<![\wऀ-ॿ]){re.escape(k)}(?![\wऀ-ॿ])", t) and sku not in skus:
            skus.append(sku)
    if not skus:
        return []
    marks = ",".join("?" * len(skus))
    return db.q(f"SELECT * FROM products WHERE merchant_id=? AND sku IN ({marks})", (mid, *skus))
