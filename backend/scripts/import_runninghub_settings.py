import os
import sys

# Ensure backend root is in PYTHON_PATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting, SystemAPIBillingRule        

def main():
    db = SessionLocal()
    try:
        # Define provider
        PROVIDER = "runninghub"
        BASE_URL = "https://www.runninghub.cn"
        
        # Check if exists
        existing = db.query(SystemAPISetting).filter(SystemAPISetting.provider == PROVIDER, SystemAPISetting.model == "sparkvideo-2.0").first()
        if existing:
            print("RunningHub SparkVideo 2.0 already exists in SystemAPISetting.")
        else:
            new_setting = SystemAPISetting(
                name="RunningHub SparkVideo 2.0 (I2V)",
                category="Video",
                provider=PROVIDER,
                base_url=BASE_URL,
                model="sparkvideo-2.0",
                modality={"generation_modes": ["i2v"]},
                config={
                    "endpoint": "/openapi/v2/rhart-video/sparkvideo-2.0/image-to-video",
                    "query_endpoint": "/openapi/v2/query"
                },
                deprecated=False,
                is_active=True,
                tags=["runninghub", "i2v"]
            )
            db.add(new_setting)
            db.commit()
            db.refresh(new_setting)
            print(f"Added RunningHub SparkVideo 2.0 to SystemAPISetting with ID: {new_setting.id}")
            
            # Setup simple billing rule
            billing_rule = SystemAPIBillingRule(
                system_api_setting_id=new_setting.id,
                rule_type="per_request",
                cost_amount=0.5, # adjust later
                currency="USD",
                is_active=True,
                priority=100
            )
            db.add(billing_rule)
            db.commit()
            print("Added SystemAPIBillingRule for RunningHub.")
            
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    main()
