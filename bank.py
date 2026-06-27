"""
💰 DIGITAL BANK — UPI Payment System
Agent apna khud ka bank banata hai:
- UPI payment requests generate karta hai
- QR codes banata hai
- Transactions track karta hai
- Ledger maintain karta hai
- "Withdrawal" support — jab tu paise maange
"""

import json, time, uuid, base64, io, os, re
from pathlib import Path
from datetime import datetime
from typing import Optional

BASE = Path(__file__).parent
TRANSACTIONS_FILE = BASE / "transactions" / "ledger.json"
QR_DIR = BASE / "qr_codes"
PAYMENTS_DIR = BASE / "payments"

# Ensure dirs
for d in [QR_DIR, PAYMENTS_DIR, BASE / "transactions"]:
    d.mkdir(parents=True, exist_ok=True)


# ─────────── UPI LINK GENERATOR ───────────

def generate_upi_link(upi_id: str, amount: float, name: str = "Payment",
                      note: str = "") -> str:
    """Generate UPI deep link — opens GPay/PhonePe/Paytm directly"""
    from urllib.parse import quote
    note_encoded = quote(note or f"Payment of ₹{amount}")
    name_encoded = quote(name[:30])
    return (
        f"upi://pay?pa={upi_id}"
        f"&pn={name_encoded}"
        f"&am={amount:.2f}"
        f"&tn={note_encoded}"
        f"&cu=INR"
    )


def generate_qr_code(upi_link: str, filepath: Path) -> Optional[str]:
    """Generate QR code image for UPI link. Returns file path or None"""
    try:
        import qrcode
        import qrcode.image.svg
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(upi_link)
        qr.make(fit=True)
        # Use SVG to avoid PIL dependency issues
        img = qr.make_image(image_factory=qrcode.image.svg.SvgImage)
        filepath = filepath.with_suffix(".svg")
        img.save(filepath)
        return str(filepath)
    except Exception as e:
        # Fallback: write a text-based QR reference
        try:
            filepath.write_text(f"UPI Payment Link:\n{upi_link}\n\nOpen with any UPI app (GPay/PhonePe/Paytm)")
            return str(filepath)
        except Exception:
            return None


# ─────────── TRANSACTION LEDGER ───────────

class Transaction:
    def __init__(self, tx_id: str, client: str, amount: float,
                 note: str = "", upi_link: str = "",
                 qr_path: str = "", status: str = "pending"):
        self.tx_id = tx_id
        self.client = client
        self.amount = amount
        self.note = note
        self.upi_link = upi_link
        self.qr_path = qr_path
        self.status = status  # pending | paid | confirmed | cancelled
        self.utr = ""
        self.created_at = datetime.now().isoformat()
        self.paid_at = ""
        self.confirmed_at = ""

    def to_dict(self):
        return {
            "tx_id": self.tx_id,
            "client": self.client,
            "amount": self.amount,
            "note": self.note,
            "upi_link": self.upi_link,
            "qr_path": self.qr_path,
            "status": self.status,
            "utr": self.utr,
            "created_at": self.created_at,
            "paid_at": self.paid_at,
            "confirmed_at": self.confirmed_at,
        }

    @classmethod
    def from_dict(cls, d):
        t = cls(d["tx_id"], d["client"], d["amount"],
                d.get("note", ""), d.get("upi_link", ""),
                d.get("qr_path", ""), d.get("status", "pending"))
        t.utr = d.get("utr", "")
        t.created_at = d.get("created_at", t.created_at)
        t.paid_at = d.get("paid_at", "")
        t.confirmed_at = d.get("confirmed_at", "")
        return t

    def __repr__(self):
        status_icon = {"pending": "⏳", "paid": "✅", "confirmed": "🟢", "cancelled": "❌"}
        icon = status_icon.get(self.status, "❓")
        return f"{icon} ₹{self.amount:.0f} | {self.client:<20} | {self.status:<10} | {self.tx_id[:8]}"


class DigitalBank:
    """The Digital Bank — manages all transactions"""

    def __init__(self, upi_id: str = "", bank_name: str = "AgentBank"):
        self.bank_name = bank_name
        self.upi_id = upi_id or ""
        self.transactions: list[Transaction] = []
        self.load()

    # ── Config ──
    def configure(self, upi_id: str, bank_name: str = ""):
        """Set your UPI ID (e.g. name@upi)"""
        self.upi_id = upi_id
        if bank_name:
            self.bank_name = bank_name
        self._save_config()
        return f"✅ Bank configured: {self.upi_id}"

    def _config_path(self):
        return BASE / "transactions" / "bank_config.json"

    def _save_config(self):
        import json
        cfg = {"upi_id": self.upi_id, "bank_name": self.bank_name}
        self._config_path().write_text(json.dumps(cfg, indent=2))

    def load_config(self):
        p = self._config_path()
        if p.exists():
            cfg = json.loads(p.read_text())
            self.upi_id = cfg.get("upi_id", self.upi_id)
            self.bank_name = cfg.get("bank_name", self.bank_name)

    # ── Transactions ──
    def create_invoice(self, client: str, amount: float, note: str = "") -> Transaction:
        """Create a new payment request (invoice)"""
        tx_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        upi_link = ""
        qr_path = ""

        if self.upi_id:
            upi_link = generate_upi_link(
                self.upi_id, amount,
                name=self.bank_name,
                note=note or f"Payment from {client}"
            )
            # Generate QR
            qr_filename = f"qr_{tx_id}.png"
            qr_file = QR_DIR / qr_filename
            qr_result = generate_qr_code(upi_link, qr_file)
            if qr_result:
                qr_path = qr_result

        tx = Transaction(tx_id, client, amount, note, upi_link, qr_path)
        self.transactions.append(tx)
        self.save()
        return tx

    def mark_paid(self, tx_id: str, utr: str = "") -> Optional[Transaction]:
        """Mark a transaction as paid (user confirms payment received)"""
        tx = self.get(tx_id)
        if not tx:
            return None
        tx.status = "paid"
        tx.utr = utr
        tx.paid_at = datetime.now().isoformat()
        self.save()
        return tx

    def confirm_payment(self, tx_id: str) -> Optional[Transaction]:
        """Confirm payment — money is in the bank"""
        tx = self.get(tx_id)
        if not tx:
            return None
        if tx.status != "paid":
            return None
        tx.status = "confirmed"
        tx.confirmed_at = datetime.now().isoformat()
        self.save()
        return tx

    def cancel(self, tx_id: str) -> Optional[Transaction]:
        tx = self.get(tx_id)
        if not tx:
            return None
        tx.status = "cancelled"
        self.save()
        return tx

    def get(self, tx_id: str) -> Optional[Transaction]:
        for tx in self.transactions:
            if tx.tx_id == tx_id:
                return tx
        return None

    # ── Ledger ──
    @property
    def balance(self) -> float:
        """Total confirmed payments (money in bank)"""
        return sum(tx.amount for tx in self.transactions
                   if tx.status in ("paid", "confirmed"))

    @property
    def pending_amount(self) -> float:
        return sum(tx.amount for tx in self.transactions
                   if tx.status == "pending")

    @property
    def total_collected(self) -> float:
        return self.balance

    def list_transactions(self, status: str = "") -> list[Transaction]:
        if not status:
            return list(self.transactions)
        return [tx for tx in self.transactions if tx.status == status]

    def recent(self, n: int = 10) -> list[Transaction]:
        return list(reversed(self.transactions))[:n]

    # ── Withdrawal ──
    def withdraw(self, amount: Optional[float] = None) -> dict:
        """'Withdraw' money from the digital bank"""
        available = self.balance
        if available <= 0:
            return {"success": False, "msg": "❌ Bank mein paisa nahi hai!"}
        amt = amount if amount and amount <= available else available
        return {
            "success": True,
            "amount": amt,
            "msg": (
                f"💰 ₹{amt:.0f} withdraw ready!"
                f"\n   UPI ID: {self.upi_id}"
                f"\n   Baad mein yeh amount tuje bhej dunga."
                f"\n   Abhi bank mein total: ₹{available:.0f}"
            )
        }

    # ── Persistence ──
    def save(self):
        data = {
            "bank_name": self.bank_name,
            "upi_id": self.upi_id,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "updated_at": datetime.now().isoformat(),
        }
        TRANSACTIONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def load(self):
        self.load_config()
        if not TRANSACTIONS_FILE.exists():
            return
        try:
            data = json.loads(TRANSACTIONS_FILE.read_text())
            self.transactions = [Transaction.from_dict(d) for d in data.get("transactions", [])]
        except (json.JSONDecodeError, KeyError):
            self.transactions = []

    def summary_text(self) -> str:
        """Returns a formatted bank summary"""
        pending_tx = self.list_transactions("pending")
        paid_tx = self.list_transactions("paid")
        confirmed_tx = self.list_transactions("confirmed")

        lines = [
            f"\n{'═'*50}",
            f"  🏦 {self.bank_name.upper()}",
            f"  UPI: {self.upi_id or '❌ NOT SET'}",
            f"{'═'*50}",
            f"  💰 Balance:     ₹{self.balance:.0f}",
            f"  ⏳ Pending:     ₹{self.pending_amount:.0f}",
            f"  📊 Total Txns:  {len(self.transactions)}",
            f"{'─'*50}",
        ]
        if confirmed_tx:
            lines.append(f"  🟢 Confirmed: {len(confirmed_tx)}")
            for t in confirmed_tx[-5:]:
                lines.append(f"     {t}")
        if paid_tx:
            lines.append(f"  ✅ Paid (unconfirmed): {len(paid_tx)}")
            for t in paid_tx[-3:]:
                lines.append(f"     {t}")
        if pending_tx:
            lines.append(f"  ⏳ Pending: {len(pending_tx)}")
            for t in pending_tx[-5:]:
                lines.append(f"     {t}")
        lines.append(f"{'═'*50}")
        return "\n".join(lines)
