import sys

with open('backend/app/services/billing_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

def safe_replace(t, old, new):
    if old not in t:
        print('MISSING:', old[:80] + '...')
        sys.exit(1)
    else:
        return t.replace(old, new, 1)

# Modify Signature of _log_transaction_action
old_sig = '''    def _log_transaction_action(
        db: Session,
        *,
        user_id: int,
        stage: str,
        task_type: str,
        provider: Optional[str],
        model: Optional[str],
        transaction_id: Optional[int] = None,'''
new_sig = '''    def _log_transaction_action(
        db: Session,
        *,
        user_id: int,
        stage: str,
        task_type: str,
        provider: Optional[str],
        model: Optional[str],
        project_id: Optional[int] = None,
        episode_id: Optional[int] = None,
        transaction_id: Optional[int] = None,'''
text = safe_replace(text, old_sig, new_sig)

# Modify the logic inside _log_transaction_action
old_inst = '''        action = TransactionAction(
            user_id=int(user_id),
            transaction_id=transaction_id,'''
new_inst = '''        action = TransactionAction(
            user_id=int(user_id),
            project_id=project_id,
            episode_id=episode_id,
            transaction_id=transaction_id,'''
text = safe_replace(text, old_inst, new_inst)

# 1. Update call in `reserve`
old_call_res = '''        BillingService._log_transaction_action(
            db,
            user_id=user_id,
            stage="RESERVED",
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,'''
new_call_res = '''        BillingService._log_transaction_action(
            db,
            user_id=user_id,
            stage="RESERVED",
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            project_id=reserve_details.get("project_id"),
            episode_id=reserve_details.get("episode_id"),'''
text = safe_replace(text, old_call_res, new_call_res)

# 2. Update call in `cancel_reservation`
old_call_cancel = '''        BillingService._log_transaction_action(
            db,
            user_id=tx.user_id,
            stage="CANCELED",
            task_type=tx_task_type,
            provider=tx_provider,
            model=tx_model,'''
new_call_cancel = '''        BillingService._log_transaction_action(
            db,
            user_id=tx.user_id,
            stage="CANCELED",
            task_type=tx_task_type,
            provider=tx_provider,
            model=tx_model,
            project_id=res_action.project_id if res_action else None,
            episode_id=res_action.episode_id if res_action else None,'''
text = safe_replace(text, old_call_cancel, new_call_cancel)

# 3. Update call in `settle_reservation`
old_call_settle = '''        BillingService._log_transaction_action(
            db,
            user_id=user.id,
            stage="SETTLED",
            task_type=res_task_type,
            provider=settle_provider,
            model=settle_model,'''
new_call_settle = '''        BillingService._log_transaction_action(
            db,
            user_id=user.id,
            stage="SETTLED",
            task_type=res_task_type,
            provider=settle_provider,
            model=settle_model,
            project_id=res_action.project_id if res_action else None,
            episode_id=res_action.episode_id if res_action else None,'''
text = safe_replace(text, old_call_settle, new_call_settle)

# 4. Update call in `deduct`
old_call_deduct = '''        BillingService._log_transaction_action(
            db,
            user_id=user_id,
            stage="DEDUCTED",
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,'''
new_call_deduct = '''        BillingService._log_transaction_action(
            db,
            user_id=user_id,
            stage="DEDUCTED",
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            project_id=tx_details.get("project_id"),
            episode_id=tx_details.get("episode_id"),'''
text = safe_replace(text, old_call_deduct, new_call_deduct)

with open('backend/app/services/billing_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated log_transaction calls correctly.")
