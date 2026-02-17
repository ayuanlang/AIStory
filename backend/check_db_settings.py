
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.all_models import APISetting, User # Assuming these are available 
from app.core.config import settings

# Setup DB connection
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def check_settings():
    print(f"Checking database: {settings.DATABASE_URL}")
    
    # 1. Check Users
    users = db.query(User).all()
    print(f"\nTotal Users: {len(users)}")
    for u in users:
        print(f"User ID: {u.id}, Username: {u.username}")

    # 2. Check Settings
    api_settings = db.query(APISetting).all()
    print(f"\nTotal API Settings: {len(api_settings)}")
    
    for s in api_settings:
        print(f"ID: {s.id}, UserID: {s.user_id}, Provider: {s.provider}, Category: {s.category}, Active: {s.is_active}")
        print(f"  --> API Key: {s.api_key[:5]}... if exists")
        print(f"  --> Config: {s.config}")

    # 3. Check specific user settings (assuming usually user_id=1 is the main one)
    if users:
        target_user_id = users[0].id
        print(f"\nSettings for User ID {target_user_id}:")
        user_settings = db.query(APISetting).filter(APISetting.user_id == target_user_id).all()
        for s in user_settings:
            print(f"  - {s.provider} ({s.category})")


    # 2. Check System Payments
    print("\nSystem Payments:")
    payments = db.query(APISetting).filter(APISetting.category == "System_Payment").all()
    if not payments:
        print(" > No System Payment settings found!")
    else:
        for p in payments:
            print(f" > Provider: '{p.provider}' | Config: {p.config} | API Key len: {len(p.api_key) if p.api_key else 0}")
            if p.provider == 'wechat_pay':
                # Show keys in config
                if p.config:
                    print(f"   Config Keys: {list(p.config.keys())}")
                    # Show partial values
                    for k,v in p.config.items():
                        v_str = str(v)
                        print(f"   - {k}: {v_str[:5]}...{v_str[-5:] if len(v_str)>10 else ''}")

if __name__ == "__main__":
    check_settings()
