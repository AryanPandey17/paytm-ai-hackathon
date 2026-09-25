"""Mocked Paytm rails (Collect, disbursal, Soundbox, settlements). Swap for real APIs in production."""
import random
import string
from datetime import datetime


def _ref(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def collect_link(merchant_id: str, customer_id: str, amount: float, note: str = "") -> dict:
    ref = _ref()
    return {
        "link": f"https://paytm.me/demo/{ref}",
        "upi_intent": f"upi://pay?pa=merchant{merchant_id.lower()}@paytm&am={amount:.0f}&tn={note or 'Udhaar'}&tr={ref}",
        "ref": ref,
        "amount": amount,
        "created": datetime.now().isoformat(timespec="seconds"),
        "mock": True,
    }


def disburse(merchant_id: str, amount: float) -> dict:
    return {"txn_id": f"DSB{_ref(10)}", "amount": amount, "merchant_id": merchant_id, "status": "SUCCESS", "mock": True}


def soundbox_status(device_id: str) -> dict:
    return {"device_id": device_id, "online": random.random() > 0.2, "battery": random.randint(20, 100), "mock": True}
