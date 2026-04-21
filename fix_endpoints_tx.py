import re

path = 'backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace:
# task_type="signup_bonus", -> description="signup_bonus",
# provider="system", -> details={... provider: 'system', model: ...} # not straight forward with regex

# Since there are only 5 occurrences:

patch_1 = """        trans = TransactionHistory(
            user_id=user.id,
            amount=granted_credits,
            balance_after=int(user.credits or 0),
            task_type="signup_bonus",
            provider="system",
            model="email_verification",
            details={
                "reason": "email_verification_trial_bonus",
                "target_credits": target_credits,
                "old_credits": old_credits,
                "method": "email_verify_sys"
            }
        )"""
        
new_patch_1 = """        trans = TransactionHistory(
            user_id=user.id,
            amount=granted_credits,
            balance_after=int(user.credits or 0),
            description="signup_bonus",
            details={
                "task_type": "signup_bonus",
                "provider": "system",
                "model": "email_verification",
                "reason": "email_verification_trial_bonus",
                "target_credits": target_credits,
                "old_credits": old_credits,
                "method": "email_verify_sys"
            }
        )"""
content = content.replace(patch_1, new_patch_1)


patch_2 = """            trans = TransactionHistory(
                user_id=order.user_id,
                amount=order.credits,
                balance_after=user.credits if user else 0,
                task_type="recharge",
                provider="wechat",
                model="cny",
                details={"order_no": order_no, "amount_cny": order.amount, "method": "active_query"}
            )"""
            
new_patch_2 = """            trans = TransactionHistory(
                user_id=order.user_id,
                amount=order.credits,
                balance_after=user.credits if user else 0,
                description="recharge",
                details={
                    "task_type": "recharge",
                    "provider": "wechat",
                    "model": "cny",
                    "order_no": order_no, 
                    "amount_cny": order.amount, 
                    "method": "active_query"
                }
            )"""
content = content.replace(patch_2, new_patch_2)


patch_3 = """                    trans = TransactionHistory(
                        user_id=order.user_id,
                        amount=order.credits,
                        balance_after=user.credits if user else 0,
                        task_type="recharge",
                        provider="wechat",
                        model="cny",
                        details={
                            "order_no": out_trade_no, 
                            "method": "notify", 
                            "wx_transaction_id": wx_transaction_id,
                            "amount_cny": order.amount
                        }
                    )"""

new_patch_3 = """                    trans = TransactionHistory(
                        user_id=order.user_id,
                        amount=order.credits,
                        balance_after=user.credits if user else 0,
                        description="recharge",
                        details={
                            "task_type": "recharge",
                            "provider": "wechat",
                            "model": "cny",
                            "order_no": out_trade_no, 
                            "method": "notify", 
                            "wx_transaction_id": wx_transaction_id,
                            "amount_cny": order.amount
                        }
                    )"""
content = content.replace(patch_3, new_patch_3)

patch_4 = """    trans = TransactionHistory(
        user_id=user.id,
        amount=order.credits,
        balance_after=user.credits,
        task_type="recharge",
        provider="wechat",
        model="cny",
        details={"order_no": order_no, "amount_cny": order.amount}
    )"""

new_patch_4 = """    trans = TransactionHistory(
        user_id=user.id,
        amount=order.credits,
        balance_after=user.credits,
        description="recharge",
        details={
            "task_type": "recharge", 
            "provider": "wechat", 
            "model": "cny", 
            "order_no": order_no, 
            "amount_cny": order.amount
        }
    )"""
content = content.replace(patch_4, new_patch_4)

patch_5 = """    trans = TransactionHistory(
        user_id=user_id,
        amount=user.credits - old_credits,
        balance_after=user.credits,
        task_type="admin_adjustment",
        details={"admin_id": current_user.id, "reason": "Manual Update"}
    )"""
    
new_patch_5 = """    trans = TransactionHistory(
        user_id=user_id,
        amount=user.credits - old_credits,
        balance_after=user.credits,
        description="admin_adjustment",
        details={
            "task_type": "admin_adjustment",
            "admin_id": current_user.id, 
            "reason": "Manual Update"
        }
    )"""
content = content.replace(patch_5, new_patch_5)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched")
