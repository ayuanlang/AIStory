with open('backend/app/services/billing_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

def safe_replace(t, old, new):
    if old not in t:
        print('MISSING:', old[:80] + '...')
    else:
        print('FOUND')
        return t.replace(old, new, 1)
    return t

# 1. reserve: tx doesn't get project_id, but action DOES
old_reserve_tx = '''        tx = TransactionHistory(
            user_id=user_id,
            amount=-reserved_cost,
            balance_after=user.credits or 0,
            description=reserve_details.get("description", task_type),
            project_id=reserve_details.get("project_id"),
            episode_id=reserve_details.get("episode_id"),
            details=reserve_details
        )'''
new_reserve_tx = '''        tx = TransactionHistory(
            user_id=user_id,
            amount=-reserved_cost,
            balance_after=user.credits or 0,
            description=reserve_details.get("description", task_type),
            details=reserve_details
        )'''
text = safe_replace(text, old_reserve_tx, new_reserve_tx)

old_reserve_act = '''        action = TransactionAction(
            user_id=user_id,
            stage="RESERVED",
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            system_api_id=system_api_id,
            matched_rule_id=matched_rule_id,
            reserved_cost=reserved_cost,
            action_payload=reserve_details.get("metadata", {})
        )'''
new_reserve_act = '''        action = TransactionAction(
            user_id=user_id,
            project_id=reserve_details.get("project_id"),
            episode_id=reserve_details.get("episode_id"),
            stage="RESERVED",
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            system_api_id=system_api_id,
            matched_rule_id=matched_rule_id,
            reserved_cost=reserved_cost,
            action_payload=reserve_details.get("metadata", {})
        )'''
text = safe_replace(text, old_reserve_act, new_reserve_act)

# 2. cancel_reservation / refund. refund_tx removes project/ep. action gains it.
old_cancel_tx = '''        refund_tx = TransactionHistory(
            user_id=tx.user_id,
            amount=reserved_cost,
            balance_after=user.credits or 0,
            description=f"Refund for {tx.description or 'task'}",
            project_id=tx.project_id,
            episode_id=tx.episode_id,
            details=refund_details,
        )'''
new_cancel_tx = '''        refund_tx = TransactionHistory(
            user_id=tx.user_id,
            amount=reserved_cost,
            balance_after=user.credits or 0,
            description=f"Refund for {tx.description or 'task'}",
            details=refund_details,
        )'''
text = safe_replace(text, old_cancel_tx, new_cancel_tx)

old_cancel_act = '''        refund_action = TransactionAction(
            user_id=tx.user_id,
            stage="CANCELED",
            reservation_tx_id=reservation_id,
            task_type=task_type,
            provider=provider,
            model=model,
            reserved_cost=0,
            actual_cost=0,
            delta=reserved_cost,
            action_payload=refund_details
        )'''
new_cancel_act = '''        refund_action = TransactionAction(
            user_id=tx.user_id,
            project_id=res_action.project_id if res_action else None,
            episode_id=res_action.episode_id if res_action else None,
            stage="CANCELED",
            reservation_tx_id=reservation_id,
            task_type=task_type,
            provider=provider,
            model=model,
            reserved_cost=0,
            actual_cost=0,
            delta=reserved_cost,
            action_payload=refund_details
        )'''
text = safe_replace(text, old_cancel_act, new_cancel_act)

# 3. settlement inner refund
old_settle_ref = '''            settlement_tx = TransactionHistory(
                user_id=user.id,
                amount=refund,
                balance_after=user.credits or 0,
                description=f"Partial refund for {reservation_tx.description or 'task'}",
                project_id=reservation_tx.project_id,
                episode_id=reservation_tx.episode_id,
                details={
                    "status": "REFUND",
                    "reason": "RESERVATION_SETTLEMENT",
                    "reservation_tx_id": reservation_tx.id,
                }
            )'''
new_settle_ref = '''            settlement_tx = TransactionHistory(
                user_id=user.id,
                amount=refund,
                balance_after=user.credits or 0,
                description=f"Partial refund for {reservation_tx.description or 'task'}",
                details={
                    "status": "REFUND",
                    "reason": "RESERVATION_SETTLEMENT",
                    "reservation_tx_id": reservation_tx.id,
                }
            )'''
text = safe_replace(text, old_settle_ref, new_settle_ref)

old_settle_ref_act = '''            settle_action = TransactionAction(
                user_id=user.id,
                stage="SETTLED",
                reservation_tx_id=reservation_tx.id,
                task_type=settle_task_type,
                provider=settle_provider,
                model=settle_model,
                system_api_id=res_action.system_api_id if res_action else None,
                matched_rule_id=res_action.matched_rule_id if res_action else None,
                reserved_cost=reserved_cost,
                actual_cost=actual_cost,
                delta=refund, # positive back to user
                action_payload=settle_details
            )'''
new_settle_ref_act = '''            settle_action = TransactionAction(
                user_id=user.id,
                project_id=res_action.project_id if res_action else None,
                episode_id=res_action.episode_id if res_action else None,
                stage="SETTLED",
                reservation_tx_id=reservation_tx.id,
                task_type=settle_task_type,
                provider=settle_provider,
                model=settle_model,
                system_api_id=res_action.system_api_id if res_action else None,
                matched_rule_id=res_action.matched_rule_id if res_action else None,
                reserved_cost=reserved_cost,
                actual_cost=actual_cost,
                delta=refund, # positive back to user
                action_payload=settle_details
            )'''
text = safe_replace(text, old_settle_ref_act, new_settle_ref_act)


# 4. settlement inner charge
old_settle_chg = '''                settlement_tx = TransactionHistory(
                    user_id=user.id,
                    amount=-can_deduct,
                    balance_after=user.credits or 0,
                    description=f"Extra charge for {reservation_tx.description or 'task'}",
                    project_id=reservation_tx.project_id,
                    episode_id=reservation_tx.episode_id,
                    details={
                        "status": "CHARGE",
                        "reason": "RESERVATION_SETTLEMENT",
                        "reservation_tx_id": reservation_tx.id,
                    }
                )'''
new_settle_chg = '''                settlement_tx = TransactionHistory(
                    user_id=user.id,
                    amount=-can_deduct,
                    balance_after=user.credits or 0,
                    description=f"Extra charge for {reservation_tx.description or 'task'}",
                    details={
                        "status": "CHARGE",
                        "reason": "RESERVATION_SETTLEMENT",
                        "reservation_tx_id": reservation_tx.id,
                    }
                )'''
text = safe_replace(text, old_settle_chg, new_settle_chg)

old_settle_chg_act = '''                settle_action = TransactionAction(
                    user_id=user.id,
                    stage="CHARGE",
                    reservation_tx_id=reservation_tx.id,
                    task_type=settle_task_type,
                    provider=settle_provider,
                    model=settle_model,
                    system_api_id=res_action.system_api_id if res_action else None,
                    matched_rule_id=res_action.matched_rule_id if res_action else None,
                    reserved_cost=reserved_cost,
                    actual_cost=actual_cost,
                    delta=-can_deduct, # negative cost
                    action_payload=settle_details
                )'''
new_settle_chg_act = '''                settle_action = TransactionAction(
                    user_id=user.id,
                    project_id=res_action.project_id if res_action else None,
                    episode_id=res_action.episode_id if res_action else None,
                    stage="CHARGE",
                    reservation_tx_id=reservation_tx.id,
                    task_type=settle_task_type,
                    provider=settle_provider,
                    model=settle_model,
                    system_api_id=res_action.system_api_id if res_action else None,
                    matched_rule_id=res_action.matched_rule_id if res_action else None,
                    reserved_cost=reserved_cost,
                    actual_cost=actual_cost,
                    delta=-can_deduct, # negative cost
                    action_payload=settle_details
                )'''
text = safe_replace(text, old_settle_chg_act, new_settle_chg_act)

# 5. deduct (immediate deduct)
old_deduct = '''        transaction = TransactionHistory(
            user_id=user_id,
            amount=-final_cost,
            balance_after=user.credits,
            description=tx_details.get("description", task_type),
            project_id=tx_details.get("project_id"),
            episode_id=tx_details.get("episode_id"),
            details=tx_details
        )'''
new_deduct = '''        transaction = TransactionHistory(
            user_id=user_id,
            amount=-final_cost,
            balance_after=user.credits,
            description=tx_details.get("description", task_type),
            details=tx_details
        )'''
text = safe_replace(text, old_deduct, new_deduct)

old_deduct_act = '''        action = TransactionAction(
            user_id=user_id,
            stage="CHARGE", # immediate charge
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            system_api_id=system_api_id,
            matched_rule_id=matched_rule_id,
            reserved_cost=0,
            actual_cost=final_cost,
            delta=-final_cost,
            action_payload=tx_details.get("metadata", {})
        )'''
new_deduct_act = '''        action = TransactionAction(
            user_id=user_id,
            project_id=tx_details.get("project_id"),
            episode_id=tx_details.get("episode_id"),
            stage="CHARGE", # immediate charge
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            system_api_id=system_api_id,
            matched_rule_id=matched_rule_id,
            reserved_cost=0,
            actual_cost=final_cost,
            delta=-final_cost,
            action_payload=tx_details.get("metadata", {})
        )'''
text = safe_replace(text, old_deduct_act, new_deduct_act)

# 6. log_transaction_failure
old_fail = '''            transaction = TransactionHistory(
                user_id=user_id,
                amount=0,
                balance_after=user.credits or 0,
                description=fail_details.get("description", task_type),
                project_id=fail_details.get("project_id"),
                episode_id=fail_details.get("episode_id"),
                details=fail_details
            )'''
new_fail = '''            transaction = TransactionHistory(
                user_id=user_id,
                amount=0,
                balance_after=user.credits or 0,
                description=fail_details.get("description", task_type),
                details=fail_details
            )'''
text = safe_replace(text, old_fail, new_fail)

old_fail_act = '''            action = TransactionAction(
                user_id=user_id,
                stage="FAILED",
                task_type=task_type,
                provider=provider,
                model=model,
                reserved_cost=0,
                actual_cost=0,
                delta=0,
                action_payload=fail_details.get("metadata", fail_details)
            )'''
new_fail_act = '''            action = TransactionAction(
                user_id=user_id,
                project_id=fail_details.get("project_id"),
                episode_id=fail_details.get("episode_id"),
                stage="FAILED",
                task_type=task_type,
                provider=provider,
                model=model,
                reserved_cost=0,
                actual_cost=0,
                delta=0,
                action_payload=fail_details.get("metadata", fail_details)
            )'''
text = safe_replace(text, old_fail_act, new_fail_act)


with open('backend/app/services/billing_service.py', 'w', encoding='utf-8') as f:
    f.write(text)