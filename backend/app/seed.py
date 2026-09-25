"""Synthetic seed data: one hero merchant (Ramesh), a small portfolio, leads, onboarding cases, activations.

Run standalone:  uv run python -m app.seed
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta

from . import db
from .config import settings
from .services import memory

RNG = random.Random(42)
TODAY = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
HERO = "M001"


def d(days_ago: float) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat(timespec="seconds")


HOUSEHOLDS = [
    ("H01", "Sharma parivar", [("C01", "Rajesh Sharma (Sharma ji)", "regular"), ("C02", "Sunita Sharma", "regular"), ("C03", "Rohit Sharma", "occasional")]),
    ("H02", "Patil family", [("C04", "Ganesh Patil", "loyal"), ("C05", "Meena Patil", "loyal")]),
    ("H03", "Khan household", [("C06", "Imran Khan", "regular"), ("C07", "Ayesha Khan", "regular"), ("C08", "Zoya Khan", "occasional")]),
    ("H04", "Iyer family", [("C09", "Lakshmi Iyer", "loyal"), ("C10", "Venkat Iyer", "lapsing")]),
    ("H05", "Deshmukh family", [("C11", "Sachin Deshmukh", "lapsing"), ("C12", "Pooja Deshmukh", "regular")]),
    ("H06", "Gupta family", [("C13", "Anil Gupta", "regular"), ("C14", "Kavita Gupta", "loyal"), ("C15", "Aarav Gupta", "occasional")]),
    ("H07", "Fernandes family", [("C16", "Joseph Fernandes", "lapsing"), ("C17", "Maria Fernandes", "regular")]),
    ("H08", "Yadav family", [("C18", "Mukesh Yadav", "regular"), ("C19", "Sita Yadav", "regular")]),
    ("H09", "Shaikh household", [("C20", "Salim Shaikh", "occasional"), ("C21", "Nasreen Shaikh", "regular")]),
    ("H10", "Joshi family", [("C22", "Prakash Joshi", "loyal"), ("C23", "Asha Joshi", "loyal"), ("C24", "Neha Joshi", "occasional")]),
    ("H11", "Singles", [("C25", "Vikram Rao", "occasional"), ("C26", "Arjun Mehta", "lapsing"), ("C27", "Priya Nair", "regular"),
                         ("C28", "Kunal Shah", "occasional"), ("C29", "Deepa Kulkarni", "regular"), ("C30", "Farhan Qureshi", "lapsing")]),
]

PRODUCTS = [
    ("ATTA10", "Aashirvaad Atta 10kg", "आटा 10 किलो", "staples", 6, 10, 520, 1.6, 1.8),
    ("RICE5", "Basmati Rice 5kg", "बासमती चावल 5 किलो", "staples", 14, 8, 610, 0.9, 1.6),
    ("TOORDAL", "Toor Dal 1kg", "तूर दाल 1 किलो", "staples", 22, 15, 165, 2.1, 1.4),
    ("SUGAR5", "Sugar 5kg", "चीनी 5 किलो", "staples", 9, 10, 245, 1.2, 2.2),
    ("OIL1", "Fortune Sunflower Oil 1L", "सूरजमुखी तेल 1 लीटर", "staples", 30, 20, 155, 3.0, 1.9),
    ("GHEE1", "Amul Ghee 1L", "अमूल घी 1 लीटर", "staples", 5, 8, 640, 0.6, 2.8),
    ("BESAN1", "Besan 1kg", "बेसन 1 किलो", "staples", 7, 10, 110, 0.8, 3.0),
    ("MAIDA1", "Maida 1kg", "मैदा 1 किलो", "staples", 12, 10, 55, 0.7, 2.6),
    ("DRYFRT", "Kaju Badam Gift Pack", "ड्राई फ्रूट गिफ्ट पैक", "festive", 3, 6, 899, 0.2, 6.0),
    ("SWEETS", "Haldiram Soan Papdi 500g", "सोन पापड़ी", "festive", 10, 12, 160, 0.5, 5.0),
    ("DIYA", "Clay Diya Pack (12)", "मिट्टी के दीये", "festive", 0, 10, 90, 0.1, 12.0),
    ("AGARBATTI", "Cycle Agarbatti", "अगरबत्ती", "pooja", 40, 20, 60, 1.5, 2.0),
    ("TEA500", "Tata Tea Gold 500g", "चाय पत्ती", "beverages", 18, 12, 290, 1.1, 1.3),
    ("COFFEE", "Nescafe Classic 100g", "कॉफी", "beverages", 9, 6, 330, 0.3, 1.2),
    ("MILKPWD", "Amul Milk Powder 500g", "मिल्क पाउडर", "dairy", 8, 6, 270, 0.4, 1.4),
    ("BISCUIT", "Parle-G Family Pack", "पारले-जी", "snacks", 60, 30, 50, 4.5, 1.3),
    ("NAMKEEN", "Haldiram Bhujia 400g", "भुजिया", "snacks", 16, 12, 110, 1.4, 2.4),
    ("SOAP", "Lux Soap (4 pack)", "साबुन", "personal", 25, 12, 180, 0.9, 1.2),
    ("SHAMPOO", "Clinic Plus 340ml", "शैम्पू", "personal", 11, 8, 190, 0.5, 1.1),
    ("DETERGENT", "Surf Excel 1kg", "सर्फ एक्सेल", "home", 13, 10, 145, 0.8, 1.3),
    ("MAGGI", "Maggi 12 pack", "मैगी", "snacks", 20, 15, 168, 1.3, 1.2),
    ("SALT", "Tata Salt 1kg", "नमक", "staples", 35, 15, 28, 1.6, 1.1),
    ("JAGGERY", "Jaggery 1kg", "गुड़", "staples", 6, 8, 80, 0.4, 2.2),
    ("CANDLES", "Decorative Candles", "मोमबत्ती", "festive", 4, 10, 120, 0.1, 8.0),
    ("RANGOLI", "Rangoli Colour Set", "रंगोली रंग", "festive", 0, 8, 75, 0.05, 15.0),
]

SUPPLIERS = [
    ("S01", "Mahalaxmi Wholesale (Dadar)", "919800000101", 4.5, 15, 1, 1.00, "whatsapp"),
    ("S02", "Metro Cash & Carry (mock)", "919800000102", 4.2, 0, 2, 0.94, "api"),
    ("S03", "ONDC Seller: Shree Traders", "919800000103", 4.0, 30, 3, 0.97, "ondc"),
]

PORTFOLIO = [
    ("M002", "Sunil Jadhav", "Jadhav Medicals", "pharmacy", "Thane", "mr-IN", "growing", 310000, 0),
    ("M003", "Fatima Sayyed", "Sayyed Tailors", "services", "Kurla", "hi-IN", "growing", 95000, 0),
    ("M004", "Karthik R", "Karthik Tiffin Centre", "food", "Matunga", "ta-IN", "active", 180000, 0),
    ("M005", "Harpreet Kaur", "Punjab Sweets", "food", "Chembur", "pa-IN", "growing", 420000, 0),
    ("M006", "Mahesh Patel", "Patel Hardware", "hardware", "Ghatkopar", "gu-IN", "at_risk", 60000, 1),
    ("M007", "Anita Das", "Das Mobile Repair", "services", "Andheri", "bn-IN", "active", 140000, 0),
    ("M008", "Rakesh Tiwari", "Tiwari Pan Shop", "retail", "Dadar", "hi-IN", "activating", 0, 0),
    ("M009", "Sneha More", "More Flowers", "retail", "Parel", "mr-IN", "onboarding", 0, 0),
    ("M010", "Joseph D'Souza", "D'Souza Bakery", "food", "Bandra", "en-IN", "growing", 260000, 0),
]

LEADS = [
    ("L01", "Vinod Chauhan", "Chauhan General Store", "kirana", "Sion", "field-survey", 180, 0.62, "hi-IN"),
    ("L02", "Rekha Pawar", "Pawar Vegetables", "fruits-veg", "Dadar", "referral", 260, 0.48, "mr-IN"),
    ("L03", "Abdul Rehman", "Rehman Chicken Centre", "meat", "Kurla", "soundbox-lookalike", 150, 0.55, "hi-IN"),
    ("L04", "Geeta Nair", "Nair Stores", "kirana", "Chembur", "ondc-seller-list", 120, 0.71, "ml-IN"),
    ("L05", "Pradeep Shetty", "Udupi Snacks", "food", "Matunga", "referral", 320, 0.66, "kn-IN"),
    ("L06", "Kiran Bhosale", "Bhosale Xerox", "services", "Parel", "field-survey", 90, 0.4, "mr-IN"),
    ("L07", "Mohan Lal", "Lal Sweets", "food", "Ghatkopar", "gmaps-scrape", 210, 0.58, "hi-IN"),
    ("L08", "Shabana Ansari", "Ansari Bangles", "retail", "Mohammed Ali Rd", "field-survey", 140, 0.35, "hi-IN"),
    ("L09", "Ravi Kumar", "Kumar Medical", "pharmacy", "Wadala", "referral", 190, 0.74, "hi-IN"),
    ("L10", "Nikhil Sawant", "Sawant Dairy", "dairy", "Lalbaug", "soundbox-lookalike", 280, 0.69, "mr-IN"),
    ("L11", "Farida Merchant", "Merchant Dry Fruits", "retail", "Crawford Mkt", "gmaps-scrape", 230, 0.61, "gu-IN"),
    ("L12", "Tukaram Gaikwad", "Gaikwad Chai", "food", "Worli", "field-survey", 400, 0.3, "mr-IN"),
]


def seed(reset: bool = True) -> dict:
    if reset:
        db.reset()
    now = TODAY.isoformat(timespec="seconds")

    db.x("INSERT INTO merchants VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
         (HERO, "Ramesh Gupta", "Ramesh Kirana Stores", "kirana", "Mumbai", "Dadar West", "hi-IN",
          settings.demo_merchant_phone, "growing", 0, 40000, 0, d(120)))
    for m in PORTFOLIO:
        db.x("INSERT INTO merchants VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
             (m[0], m[1], m[2], m[3], "Mumbai", m[4], m[5], f"91980000{m[0][-3:]}0", m[6], m[7], m[7] * 0.15, m[8], d(RNG.randint(10, 200))))

    # Customers + households
    cust_rows = []
    for hid, hname, members in HOUSEHOLDS:
        db.x("INSERT INTO households VALUES (?,?,?)", (hid, HERO, hname))
        for cid, name, seg in members:
            phone = settings.demo_customer_phone if cid == "C01" else f"91980000{cid[-2:]}99"
            cust_rows.append((cid, name, seg, hid, phone))

    tx_rows = []
    cust_stats = {}
    for cid, name, seg, hid, phone in cust_rows:
        visits_per_week = {"loyal": 4, "regular": 2.5, "occasional": 0.8, "lapsing": 1.8}[seg]
        basket = RNG.uniform(120, 650)
        last_day = 1 if seg != "lapsing" else RNG.randint(24, 40)
        visits = 0
        spend = 0.0
        for day in range(90, last_day - 1, -1):
            if RNG.random() < visits_per_week / 7:
                amt = round(basket * RNG.uniform(0.5, 1.6), 0)
                method = RNG.choices(["upi", "cash", "udhaar"], [0.62, 0.3, 0.08])[0]
                status = "failed" if method == "upi" and RNG.random() < 0.03 else "success"
                tx_rows.append((HERO, cid, amt, d(day - RNG.random() * 0.5), method, status))
                visits += 1
                spend += amt
        cust_stats[cid] = (visits, spend, last_day)
        churn = 0.82 if seg == "lapsing" else (0.15 if seg == "loyal" else 0.3)
        db.x("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
             (cid, HERO, name, phone, hid, "hi-IN" if cid not in ("C09", "C10") else "ta-IN", seg,
              d(last_day), visits, round(spend), round(spend * 4.2), churn))
    # walk-in (anonymous) sales so GMV looks realistic
    for day in range(90, 0, -1):
        festive = 1.25 if day < 12 else 1.0
        for _ in range(RNG.randint(18, 30)):
            tx_rows.append((HERO, None, round(RNG.uniform(20, 380) * festive), d(day - RNG.random() * 0.6),
                            RNG.choices(["upi", "cash"], [0.58, 0.42])[0], "success"))
    db.xmany("INSERT INTO transactions(merchant_id, customer_id, amount, ts, method, status) VALUES (?,?,?,?,?,?)", tx_rows)

    udhaar = [("C01", 1200, 21, "open"), ("C06", 850, 12, "open"), ("C11", 2300, 38, "open"), ("C16", 640, 30, "open"),
              ("C13", 480, 6, "open"), ("C26", 1500, 45, "open"), ("C19", 300, 4, "open"), ("C21", 960, 17, "open"),
              ("C04", 700, 50, "paid"), ("C22", 1100, 60, "paid")]
    for cid, amt, age, st in udhaar:
        db.x("INSERT INTO udhaar(merchant_id, customer_id, amount, created, due, status, recovered) VALUES (?,?,?,?,?,?,?)",
             (HERO, cid, amt, d(age), d(age - 7), st, amt if st == "paid" else 0))

    for p in PRODUCTS:
        db.x("INSERT INTO products(merchant_id, sku, name, name_local, category, stock, reorder_level, price, daily_velocity, festival_multiplier) "
             "VALUES (?,?,?,?,?,?,?,?,?,?)", (HERO, *p))
    for s in SUPPLIERS:
        db.x("INSERT INTO suppliers VALUES (?,?,?,?,?,?,?,?)", s)

    for l in LEADS:
        db.x("INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
             (l[0], l[1], l[2], l[3], l[4], l[5], l[6], l[7], None, "new", None, l[8], d(RNG.randint(0, 6))))

    ok = {"docs": "done", "compliance": "done", "banking": "done", "hardware": "done", "legal": "done"}
    cases = [
        ("OB01", "L90", "Sneha More", "More Flowers", {**ok, "compliance": "exception"},
         {"track": "compliance", "type": "name_mismatch", "detail": "PAN name 'SNEHA R MORE' vs bank account name 'SNEHA RAJESH MORE'"}, "exception"),
        ("OB02", "L91", "Deepak Verma", "Verma Electricals", {**ok, "docs": "exception", "legal": "in_progress"},
         {"track": "docs", "type": "unreadable_document", "detail": "Shop establishment certificate photo is blurred (OCR confidence 0.41)"}, "exception"),
        ("OB03", "L92", "Asif Mulla", "Mulla Meat Shop", {**ok, "banking": "exception"},
         {"track": "banking", "type": "penny_drop_failed", "detail": "Penny-drop failed: account frozen per bank response code 'ACCT_DORMANT'"}, "exception"),
        ("OB04", "L93", "Lata Kamble", "Kamble Provision", {"docs": "done", "compliance": "in_progress", "banking": "done", "hardware": "in_progress", "legal": "done"}, None, "in_progress"),
        ("OB05", "L94", "Rahul Pandey", "Pandey Stationery", ok, None, "complete"),
    ]
    for c in cases:
        db.x("INSERT INTO onboarding_cases VALUES (?,?,?,?,?,?,?,?,?)",
             (c[0], c[1], c[2], c[3], db.dumps(c[4]), db.dumps(c[5]) if c[5] else None, c[6], None, d(RNG.randint(1, 4))))

    acts = [
        ("AC01", "Rakesh Tiwari", "Tiwari Pan Shop", "Dadar", "Soundbox 5.0", "delivered", None, "device_offline", 30, None),
        ("AC02", "Rahul Pandey", "Pandey Stationery", "Sion", "Soundbox 5.0", "dispatched", None, None, 0, None),
        ("AC03", "Pinky Shah", "Shah Cosmetics", "Ghatkopar", "Card Soundbox", "delivered", "FA-Amit", "qr_not_displayed", 52, None),
        ("AC04", "Sameer Khan", "Khan Auto Parts", "Kurla", "Soundbox 5.0", "first_txn", "FA-Priya", None, 6, d(1)),
        ("AC05", "Leela Menon", "Menon Tea Stall", "Matunga", "Soundbox Mini", "allocated", None, None, 0, None),
    ]
    for a in acts:
        db.x("INSERT INTO activations VALUES (?,?,?,?,?,?,?,?,?,?)", a)

    db.x("INSERT INTO offers(merchant_id, amount, tenure_days, daily_repay_pct, fee, status, reason, score, created, decided) VALUES (?,?,?,?,?,?,?,?,?,?)",
         ("M005", 60000, 120, 8, 2400, "repaying", "Festive sweets demand", 0.81, d(40), d(40)))

    return {"merchant": HERO, "customers": len(cust_rows), "transactions": len(tx_rows)}


async def seed_memory() -> None:
    """Load a compact natural-language + graph picture of the hero merchant into the memory graph."""
    ds = memory.dataset_for(HERO)
    await memory.remember(ds, "Ramesh Gupta runs Ramesh Kirana Stores in Dadar West, Mumbai. Prefers Hindi. Activated on Paytm Soundbox 120 days ago.",
                          agent="activator", edges=[("Ramesh Kirana Stores", "Merchant", "OWNED_BY", "Ramesh Gupta", "Person"),
                                                    ("Ramesh Kirana Stores", "Merchant", "LOCATED_IN", "Dadar West", "Area")], quiet=True)
    for hid, hname, members in HOUSEHOLDS:
        for cid, name, seg in members:
            c = db.one("SELECT * FROM customers WHERE id=?", (cid,))
            edges = [(name, "Customer", "SHOPS_AT", "Ramesh Kirana Stores", "Merchant")]
            if hid != "H11":
                edges.append((name, "Customer", "BELONGS_TO", hname, "Household"))
            await memory.remember(ds, f"{name} is a {seg} customer of Ramesh Kirana Stores ({c['visits_90d']} visits, ₹{c['spend_90d']:.0f} in 90 days)"
                                  + (f", member of the {hname} household." if hid != "H11" else "."), agent="pulse", edges=edges, quiet=True)
    await memory.remember(ds, "Sharma ji (Rajesh Sharma) usually pays udhaar late but always pays within ~2 weeks of a polite reminder; prefers WhatsApp in Hindi; responded best to evening reminders.",
                          agent="grower", edges=[("Rajesh Sharma (Sharma ji)", "Customer", "OWES", "Ramesh Kirana Stores", "Merchant"),
                                                 ("Rajesh Sharma (Sharma ji)", "Customer", "PREFERS", "Evening WhatsApp reminder", "Preference")], quiet=True)
    await memory.remember(ds, "Last Diwali Ramesh ran out of diyas, rangoli colours and dry-fruit gift packs 5 days before the festival; festive sales were 1.8x normal.",
                          agent="grower", edges=[("Ramesh Kirana Stores", "Merchant", "STOCKED_OUT", "Diwali festive items", "Event")], quiet=True)
    await memory.remember(ds, "Sachin Deshmukh and Venkat Iyer have not visited in over 3 weeks; both used to buy staples weekly.",
                          agent="pulse", edges=[("Sachin Deshmukh", "Customer", "AT_RISK_OF", "Churn", "Signal"),
                                                ("Venkat Iyer", "Customer", "AT_RISK_OF", "Churn", "Signal")], quiet=True)
    for s in SUPPLIERS:
        await memory.remember(ds, f"Supplier {s[1]} offers {s[4]} days credit and {s[5]}-day delivery via {s[7]}.",
                              agent="bazaar", edges=[("Ramesh Kirana Stores", "Merchant", "BUYS_FROM", s[1], "Supplier")], quiet=True)
    await memory.remember("portfolio", "Portfolio: 10 merchants in Mumbai; Patel Hardware is flagged at-risk after a 40% GMV drop; Tiwari Pan Shop device offline 30h after delivery.",
                          agent="commander", edges=[("Patel Hardware", "Merchant", "FLAGGED", "GMV drop", "Risk"),
                                                    ("Tiwari Pan Shop", "Merchant", "BLOCKED_BY", "Device offline", "Issue")], quiet=True)
    await memory.cognify()


if __name__ == "__main__":
    print(seed())
    asyncio.run(seed_memory())
    print("memory seeded")
