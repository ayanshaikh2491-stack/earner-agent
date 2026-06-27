#!/usr/bin/env python
"""
🏦 AGENT BANK — CLI REPL for the Digital Bank
Tu apna khud ka digital bank chala sakta hai:
- Payment requests bhejo (UPI link + QR code)
- Payments track karo
- Balance dekho
- Withdraw karo
"""

import sys, os, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bank import DigitalBank

bank = DigitalBank()
bank.load_config()

# ── Config ──
bank_name = bank.bank_name or "AgentBank"
default_upi = bank.upi_id or ""

# ── Help Text ──
HELP = f"""
{'═'*55}
  🏦 {bank_name.upper()} — CLI DIGITAL BANK
{'═'*55}

  📋 COMMANDS:
  request <client> <amount> [note]
        → Payment request bhejo (UPI link + QR generate karega)

  list [pending|paid|confirmed|cancelled]
        → Saare transactions dekho

  paid <tx_id> [utr]
        → Payment mil gaya! Mark as paid (UTR number optional)

  confirm <tx_id>
        → Confirm payment — bank mein paisa aa gaya

  cancel <tx_id>
        → Transaction cancel karo

  balance
        → Bank balance dekho

  withdraw [amount]
        → Bank se paise nikalo (tuze bhejne ke liye ready)

  config <upi_id> [bank_name]
        → Bank set karo: apna UPI ID daalo (e.g. name@upi)

  txn <tx_id>
        → Transaction details dekho

  export
        → Saare transactions export karo (console pe)

  help
        → Yeh help message

  exit / quit
        → Band karo

{'═'*55}
"""

# ── Display Functions ──

def show_transaction(tx):
    """Display single transaction details"""
    status_icon = {"pending": "⏳", "paid": "✅", "cancelled": "❌", "confirmed": "🟢"}
    icon = status_icon.get(tx.status, "❓")
    print(f"\n{'─'*45}")
    print(f"  {icon} TXN: {tx.tx_id}")
    print(f"  Client:   {tx.client}")
    print(f"  Amount:   ₹{tx.amount:.0f}")
    print(f"  Note:     {tx.note or '—'}")
    print(f"  Status:   {tx.status.upper()}")
    if tx.utr:
        print(f"  UTR:      {tx.utr}")
    if tx.created_at:
        print(f"  Created:  {tx.created_at[:19]}")
    if tx.paid_at:
        print(f"  Paid at:  {tx.paid_at[:19]}")
    if tx.confirmed_at:
        print(f"  Confirmed: {tx.confirmed_at[:19]}")
    if tx.upi_link:
        print(f"  UPI Link: {tx.upi_link}")
    if tx.qr_path and os.path.exists(tx.qr_path):
        print(f"  QR Code:  {tx.qr_path}")
    print(f"{'─'*45}")


# ── Main REPL Loop ──

def main():
    if not bank.upi_id:
        print(f"\n{'!'*50}")
        print(f"  ⚠  PEHLE APNA UPI ID SET KARO!")
        print(f"  Command: config <tumhara_upi_id>")
        print(f"  Example: config merchant@upi")
        print(f"{'!'*50}\n")
        print(HELP)

    print(f"\n{'═'*55}")
    print(f"  🏦 {bank_name.upper()} — Digital Bank CLI")
    print(f"{'═'*55}")
    if bank.upi_id:
        print(f"  UPI: {bank.upi_id}  |  Balance: ₹{bank.balance:.0f}")
    print(f"  Type 'help' for commands, 'exit' to quit\n")

    while True:
        try:
            cmd = input("🏦 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Bye!")
            break

        if not cmd:
            continue

        parts = cmd.split()
        action = parts[0].lower()

        # ── EXIT ──
        if action in ("exit", "quit", "bye"):
            print("👋 Bye! Bank safe hai.")
            break

        # ── HELP ──
        elif action == "help":
            print(HELP)

        # ── CONFIG ──
        elif action == "config":
            if len(parts) < 2:
                print("⚠ Use: config <upi_id> [bank_name]")
                print("  Example: config merchant@upi")
                continue
            upi = parts[1]
            name = " ".join(parts[2:]) if len(parts) > 2 else ""
            result = bank.configure(upi, name)
            print(f"\n✅ Bank configured!")
            print(f"   UPI: {bank.upi_id}")
            if name:
                print(f"   Name: {bank.bank_name}")

        # ── REQUEST ──
        elif action == "request":
            if not bank.upi_id:
                print("⚠ Pehle UPI ID set karo: config <upi_id>")
                continue
            if len(parts) < 3:
                print("⚠ Use: request <client_name> <amount> [note]")
                print("  Example: request Rahul 500 Website design")
                continue
            client = parts[1]
            try:
                amount = float(parts[2])
            except ValueError:
                print("⚠ Invalid amount")
                continue
            note = " ".join(parts[3:]) if len(parts) > 3 else ""

            tx = bank.create_invoice(client, amount, note)
            print(f"\n{'!'*45}")
            print(f"  ✅ INVOICE CREATED!")
            print(f"  TXN ID:   {tx.tx_id}")
            print(f"  Client:   {tx.client}")
            print(f"  Amount:   ₹{tx.amount:.0f}")
            print(f"  Status:   {tx.status}")
            print(f"{'─'*45}")
            print(f"  📱 UPI LINK:")
            print(f"  {tx.upi_link}")
            if tx.qr_path:
                print(f"\n  🖼 QR Code saved: {tx.qr_path}")
            print(f"{'!'*45}")

        # ── LIST ──
        elif action == "list":
            status = parts[1] if len(parts) > 1 else ""
            txns = bank.list_transactions(status) if status else bank.transactions
            if not txns:
                print(f"\n📭 No transactions{' with status: ' + status if status else ''}")
                continue
            print(f"\n{'─'*50}")
            print(f"  Transactions ({status or 'all'}): {len(txns)}")
            print(f"{'─'*50}")
            for t in txns:
                print(f"  {t}")
            print(f"{'─'*50}")

        # ── PAID ──
        elif action == "paid":
            if len(parts) < 2:
                print("⚠ Use: paid <tx_id> [utr_number]")
                continue
            tx_id = parts[1].upper()
            utr = parts[2] if len(parts) > 2 else ""
            tx = bank.mark_paid(tx_id, utr)
            if not tx:
                print(f"❌ Transaction '{tx_id}' nahi mila!")
                continue
            print(f"\n✅ Payment marked as PAID!")
            print(f"   TXN: {tx.tx_id} | ₹{tx.amount:.0f} | {tx.client}")
            if utr:
                print(f"   UTR: {utr}")

        # ── CONFIRM ──
        elif action == "confirm":
            if len(parts) < 2:
                print("⚠ Use: confirm <tx_id>")
                continue
            tx_id = parts[1].upper()
            tx = bank.confirm_payment(tx_id)
            if not tx:
                print(f"❌ Transaction '{tx_id}' confirm nahi ho sakti (pehle 'paid' mark karo)")
                continue
            print(f"\n🟢 Payment CONFIRMED! Paisa bank mein aa gaya!")
            print(f"   TXN: {tx.tx_id} | ₹{tx.amount:.0f} | {tx.client}")

        # ── CANCEL ──
        elif action == "cancel":
            if len(parts) < 2:
                print("⚠ Use: cancel <tx_id>")
                continue
            tx_id = parts[1].upper()
            tx = bank.cancel(tx_id)
            if not tx:
                print(f"❌ Transaction '{tx_id}' nahi mila!")
                continue
            print(f"❌ Transaction CANCELLED: {tx_id}")

        # ── BALANCE ──
        elif action == "balance":
            print(bank.summary_text())

        # ── WITHDRAW ──
        elif action == "withdraw":
            amt = float(parts[1]) if len(parts) > 1 else None
            result = bank.withdraw(amt)
            print(f"\n{result['msg']}")

        # ── TXN DETAIL ──
        elif action == "txn":
            if len(parts) < 2:
                print("⚠ Use: txn <tx_id>")
                continue
            tx_id = parts[1].upper()
            tx = bank.get(tx_id)
            if not tx:
                print(f"❌ Transaction '{tx_id}' nahi mila!")
                continue
            show_transaction(tx)

        # ── EXPORT ──
        elif action == "export":
            if not bank.transactions:
                print("📭 No transactions to export.")
                continue
            print(f"\n{'═'*70}")
            print(f"  TRANSACTION EXPORT — {bank.bank_name}")
            print(f"{'═'*70}")
            print(f"{'TXN ID':<14} {'Client':<20} {'Amount':>8} {'Status':<12} {'UTR':<16} {'Date':<20}")
            print(f"{'─'*70}")
            for t in bank.transactions:
                date = t.created_at[:10] if t.created_at else "—"
                print(f"{t.tx_id:<14} {t.client:<20} ₹{t.amount:>5.0f} {t.status:<12} {t.utr or '—':<16} {date:<20}")
            print(f"{'═'*70}")
            print(f"  TOTAL CONFIRMED: ₹{bank.balance:.0f}")
            print(f"  TOTAL PENDING:   ₹{bank.pending_amount:.0f}")
            print(f"{'═'*70}")

        else:
            print(f"❓ Unknown: {action}. Type 'help'")


if __name__ == "__main__":
    main()
