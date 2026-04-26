import re
with open(r'C:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

req_find = """class RechargeRequest(BaseModel):
    amount: int"""
req_repl = """class RechargeRequest(BaseModel):
    amount: int
    group_id: Optional[int] = None"""
if "group_id: Optional[int] = None" not in text:
    text = text.replace(req_find, req_repl)

po_find = """    order = PaymentOrder(
        order_no=order_no,
        user_id=current_user.id,
        amount=req.amount,
        credits=total_credits,
        status="PENDING",
        pay_url=pay_url,
        provider="wechat",
        created_at=now_bj_iso()
    )"""

po_repl = """    order = PaymentOrder(
        order_no=order_no,
        user_id=current_user.id,
        amount=req.amount,
        credits=total_credits,
        status="PENDING",
        pay_url=pay_url,
        provider="wechat",
        created_at=now_bj_iso(),
        target_group_id=req.group_id
    )"""
if "target_group_id=req.group_id" not in text:
    text = text.replace(po_find, po_repl)


mock_find = """    # Add Credits
    user = db.query(User).filter(User.id == order.user_id).first()
    old_credits = user.credits or 0
    user.credits = old_credits + order.credits
    
    # Log Transaction
    trans = TransactionHistory(
        user_id=user.id,
        amount=order.credits,
        balance_after=user.credits,
        type="recharge",
        description="Recharge (Mock)",
        created_at=now_bj_iso()
    )
    db.add(trans)"""

mock_repl = """    # Add Credits
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
                created_at=now_bj_iso()
            )
            db.add(trans)
    else:
        user = db.query(User).filter(User.id == order.user_id).first()
        old_credits = user.credits or 0
        user.credits = old_credits + order.credits
        trans = TransactionHistory(
            user_id=user.id,
            amount=order.credits,
            balance_after=user.credits,
            type="recharge",
            description="Recharge (Mock)",
            created_at=now_bj_iso()
        )
        db.add(trans)"""

if "type=\"group_recharge\"" not in text:
    text = text.replace(mock_find, mock_repl)

with open(r'C:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Endpoints logic patched! Done.")