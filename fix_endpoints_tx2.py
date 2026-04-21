import os
import re

path = r'backend\app\api\endpoints.py'

with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace any instance of `task_type="<val>"` inside `TransactionHistory(`
# This might be tricky because there are newlines.
# Let's find all `TransactionHistory(` to `)` blocks.

segments = []
idx = 0
while True:
    start = text.find('TransactionHistory(', idx)
    if start == -1:
        break
    end = text.find(')', start)
    block = text[start:end+1]
    
    if 'task_type=' in block:
        # replace `task_type="foo", provider="bar", model="baz", details={...}` with `description="foo", details={"task_type": "foo", ...}`
        # Actually it's easier:
        # First remove task_type, provider, model lines:
        
        # let's just do manual replacements for the remaining ones.
        
        pass
    idx = end

# For the remaining:
patch_1 = '''            trans = TransactionHistory(
                user_id=order.user_id,
                amount=order.credits,
                balance_after=user.credits if user else 0,
                task_type="recharge",
                provider="wechat",
                model="cny",
                details={"order_no": order_no, "amount_cny": order.amount, "method": "active_query"}
            )'''
new_patch_1 = '''            trans = TransactionHistory(
                user_id=order.user_id,
                amount=order.credits,
                balance_after=user.credits if user else 0,
                description="recharge",
                details={"task_type":"recharge", "provider":"wechat", "model":"cny", "order_no": order_no, "amount_cny": order.amount, "method": "active_query"}
            )'''
text = text.replace(patch_1, new_patch_1)


patch_2 = '''                    trans = TransactionHistory(
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
                    )'''
new_patch_2 = '''                    trans = TransactionHistory(
                        user_id=order.user_id,
                        amount=order.credits,
                        balance_after=user.credits if user else 0,
                        description="recharge",
                        details={
                            "task_type":"recharge", "provider":"wechat", "model":"cny",
                            "order_no": out_trade_no, 
                            "method": "notify", 
                            "wx_transaction_id": wx_transaction_id,
                            "amount_cny": order.amount
                        }
                    )'''
text = text.replace(patch_2, new_patch_2)


patch_3 = '''        trans = TransactionHistory(
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
        )'''
new_patch_3 = '''        trans = TransactionHistory(
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
        )'''
text = text.replace(patch_3, new_patch_3)

patch_4 = '''    trans = TransactionHistory(
        user_id=user.id,
        amount=order.credits,
        balance_after=user.credits,
        task_type="recharge",
        provider="wechat",
        model="cny",
        details={"order_no": order_no, "amount_cny": order.amount}
    )'''
new_patch_4 = '''    trans = TransactionHistory(
        user_id=user.id,
        amount=order.credits,
        balance_after=user.credits,
        description="recharge",
        details={"task_type":"recharge", "provider":"wechat", "model":"cny", "order_no": order_no, "amount_cny": order.amount}
    )'''
text = text.replace(patch_4, new_patch_4)


patch_5 = '''    trans = TransactionHistory(
        user_id=user_id,
        amount=user.credits - old_credits,
        balance_after=user.credits,
        task_type="admin_adjustment",
        details={"admin_id": current_user.id, "reason": "Manual Update"}
    )'''
new_patch_5 = '''    trans = TransactionHistory(
        user_id=user_id,
        amount=user.credits - old_credits,
        balance_after=user.credits,
        description="admin_adjustment",
        details={"task_type":"admin_adjustment", "admin_id": current_user.id, "reason": "Manual Update"}
    )'''
text = text.replace(patch_5, new_patch_5)


with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
    
print("Repatched endpoints.py.")
