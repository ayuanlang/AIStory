import re
with open(r'C:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

find_blk = """                    user = db.query(User).filter(User.id == order.user_id).first()
                    if user:
                        user.credits = (user.credits or 0) + order.credits
                        
                    trans = TransactionHistory(
                        user_id=order.user_id,
                        amount=order.credits,
                        balance_after=user.credits if user else 0,
                        description="recharge", 
                        details={
                            "task_type": "recharge", "provider": "wechat", "model": "cny",
                            "order_no": out_trade_no, 
                            "method": "notify", 
                            "wx_transaction_id": wx_transaction_id,
                            "payer_openid": result.get("payer", {}).get("openid"),
                            # "raw": result # Store raw data if needed (careful with size)
                        }
                    )
                    db.add(trans)"""

repl_blk = """                    from app.models.all_models import Group
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
                                description="Group Recharge (WeChat)",
                                details={
                                    "task_type": "group_recharge", "provider": "wechat", "model": "cny",
                                    "order_no": out_trade_no, 
                                    "method": "notify", 
                                    "wx_transaction_id": wx_transaction_id,
                                    "payer_openid": result.get("payer", {}).get("openid")
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
                                "task_type": "recharge", "provider": "wechat", "model": "cny",
                                "order_no": out_trade_no, 
                                "method": "notify", 
                                "wx_transaction_id": wx_transaction_id,
                                "payer_openid": result.get("payer", {}).get("openid"),
                            }
                        )
                        db.add(trans)"""

if '"task_type": "group_recharge"' not in text:
    if find_blk in text:
        text = text.replace(find_blk, repl_blk)
        with open(r'C:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
            f.write(text)
        print("wechat_notify updated to support target_group_id successfully!")
    else:
        print("Could not find the exact block for wechat_notify.")
else:
    print("Already applied target_group_id logic to wechat_notify.")