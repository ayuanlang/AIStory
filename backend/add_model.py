import os
with open('app/models/all_models.py', 'r', encoding='utf-8-sig') as f:
    text = f.read()

if 'DeletedMedia' not in text:
    new_model = '''
class DeletedMedia(Base):
    __tablename__ = "deleted_media"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)
    deleted_at = Column(DateTime(timezone=True), default=func.now())
'''
    if 'func' not in text:
        text = text.replace('from sqlalchemy import ', 'from sqlalchemy import func, ')
    text += new_model
    with open('app/models/all_models.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Added DeletedMedia model.')
else:
    print('DeletedMedia already exists.')
