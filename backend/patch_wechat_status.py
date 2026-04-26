import re
with open(r'C:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

find_blk = """              # Add Credits
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

repl_blk = """              # Add Credits & Transaction
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

if find_blk in text:
    text = text.replace(find_blk, repl_blk)
    with open(r'C:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("check_order_status updated to support target_group_id successfully!")
else:
    print("Could not find the exact block for check_order_status.")