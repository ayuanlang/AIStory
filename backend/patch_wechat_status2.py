import re
with open(r'C:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# PATCH 1: check_order_status
find_blk1 = """            # Add Credits
            user = db.query(User).filter(User.id == order.user_id).first()
            if user:
                user.credits = (user.credits or 0) + order.credits
                
            # Transaction History
            trans = TransactionHistory(
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
            )
            db.add(trans)"""

repl_blk1 = """            # Add Credits & Transaction
            from app.models.all_models import Group
            if order.target_group_id:
                target_group = db.query(Group).filter(Group.id == order.target_group_id).first()
                if target_group:
                    old_credits = target_group.credits or 0
                    target_group.credits = old_credits + order.credits
                    trans = TransactionHistory(
                        user_id=order.user_id,
                        target_group_id=order.target_group_id,
                        amount=order.credits,
                        balance_after=target_group.credits,
                        type="group_recharge",
                        description="Group Recharge (Active Query)",
                        details={
                            "task_type": "group_recharge",
                            "provider": "wechat",
                            "model": "cny",
                            "order_no": order_no, 
                            "amount_cny": order.amount, 
                            "method": "active_query"
                        }
                    )
                    db.add(trans)
            else:
                user = db.query(User).filter(User.id == order.user_id).first()
                if user:
                    user.credits = (user.credits or 0) + order.credits
                    
                trans = TransactionHistory(
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
                )
                db.add(trans)"""

if find_blk1 in text:
    text = text.replace(find_blk1, repl_blk1)
    print("Patched 1")

# PATCH 2: mock_pay_order (it turned out it had details dictionary)
find_blk2 = """    # Add Credits
    user = db.query(User).filter(User.id == order.user_id).first()
    old_credits = user.credits or 0
    user.credits = old_credits + order.credits
    
    # Log Transaction
    trans = TransactionHistory(
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
    )
    db.add(trans)
    
    db.commit()
    
    return {"status": "success", "new_balance": user.credits}"""

repl_blk2 = """    # Add Credits
    from app.models.all_models import Group
    if order.target_group_id:
        target_group = db.query(Group).filter(Group.id == order.target_group_id).first()
        if target_group:
            old_credits = target_group.credits or 0
            target_group.credits = old_credits + order.credits
            trans = TransactionHistory(
                user_id=order.user_id,
                target_group_id=order.target_group_id,
                amount=order.credits,
                balance_after=target_group.credits,
                type="group_recharge",
                description="Group Recharge (Mock)",
                details={
                    "task_type": "group_recharge", 
                    "provider": "wechat", 
                    "model": "cny", 
                    "order_no": order_no, 
                    "amount_cny": order.amount
                }
            )
            db.add(trans)
            db.commit()
            return {"status": "success", "new_balance": target_group.credits}
    
    user = db.query(User).filter(User.id == order.user_id).first()
    old_credits = user.credits or 0
    user.credits = old_credits + order.credits
    
    # Log Transaction
    trans = TransactionHistory(
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
    )
    db.add(trans)
    
    db.commit()
    
    return {"status": "success", "new_balance": user.credits}"""

if find_blk2 in text:
    text = text.replace(find_blk2, repl_blk2)
    print("Patched 2")

with open(r'C:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Complete")