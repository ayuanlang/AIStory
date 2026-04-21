with open('backend/app/services/billing_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

def safe_replace(t, old, new):
    if old not in t:
        print('MISSING:', old[:50] + '...')
    else:
        return t.replace(old, new, 1)

# 1. settle_reservation refund block
old_ref = '''                amount=refund,
                balance_after=user.credits or 0,
                description=f"Partial refund for {reservation_tx.description or 'task'}",
                project_id=reservation_tx.project_id,
                episode_id=reservation_tx.episode_id,
                details={
                    "status": "REFUND",'''
new_ref = '''                amount=refund,
                balance_after=user.credits or 0,
                description=f"Partial refund for {reservation_tx.description or 'task'}",
                details={
                    "status": "REFUND",'''
text = safe_replace(text, old_ref, new_ref)

# 2. settle_reservation charge block
old_chg = '''                    amount=-can_deduct,
                    balance_after=user.credits or 0,
                    description=f"Extra charge for {reservation_tx.description or 'task'}",
                    project_id=reservation_tx.project_id,
                    episode_id=reservation_tx.episode_id,
                    details={
                        "status": "CHARGE",'''
new_chg = '''                    amount=-can_deduct,
                    balance_after=user.credits or 0,
                    description=f"Extra charge for {reservation_tx.description or 'task'}",
                    details={
                        "status": "CHARGE",'''
text = safe_replace(text, old_chg, new_chg)


with open('backend/app/services/billing_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Cleaned up remaining project/episode from TransactionHistory")
