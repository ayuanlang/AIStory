import io

with open(r'C:\AS\AIStory\backend\app\models\all_models.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add target_group_id to PaymentOrder
po_find = """class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))"""
po_repl = """class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    target_group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)"""
text = text.replace(po_find, po_repl)

th_find = """class TransactionHistory(Base):
    __tablename__ = "transaction_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)"""
th_repl = """class TransactionHistory(Base):
    __tablename__ = "transaction_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    target_group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)"""
text = text.replace(th_find, th_repl)

with open(r'C:\AS\AIStory\backend\app\models\all_models.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("all_models updated")