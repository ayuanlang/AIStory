with open('backend/app/models/all_models.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_th = '''    description = Column(String, nullable=True) # 支出/充值描述
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=True) # 关联项目
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=True) # 关联分集

    details = Column(JSON, default={}) # Extra metadata (e.g. status)

    created_at = Column(String, default=now_bj_iso)

    user = relationship("User", back_populates="transactions")
    action_audit = relationship("TransactionAction", foreign_keys="[TransactionAction.transaction_id]", back_populates="ledger_entry", uselist=False)

    project = relationship("Project", foreign_keys=[project_id])
    episode = relationship("Episode", foreign_keys=[episode_id])'''

new_th = '''    description = Column(String, nullable=True) # 支出/充值描述

    details = Column(JSON, default={}) # Extra metadata (e.g. status)

    created_at = Column(String, default=now_bj_iso)

    user = relationship("User", back_populates="transactions")
    action_audit = relationship("TransactionAction", foreign_keys="[TransactionAction.transaction_id]", back_populates="ledger_entry", uselist=False)'''

if old_th in text:
    text = text.replace(old_th, new_th, 1)
    print('Replaced project_id/episode_id in TH')
else:
    print('Failed to replace TH')

old_ta = '''    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    transaction_id = Column(Integer, ForeignKey("transaction_history.id"), index=True, nullable=True)'''

new_ta = '''    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    transaction_id = Column(Integer, ForeignKey("transaction_history.id"), index=True, nullable=True)

    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=True)
    project = relationship("Project", foreign_keys=[project_id])
    episode = relationship("Episode", foreign_keys=[episode_id])'''

if old_ta in text:
    text = text.replace(old_ta, new_ta, 1)
    print('Added project_id/episode_id to TA')
else:
    print('Failed to replace TA')


with open('backend/app/models/all_models.py', 'w', encoding='utf-8') as f:
    f.write(text)
