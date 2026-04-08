import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))) 

from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting, SystemAPIBillingRule

def main():
    db = SessionLocal()
    existing = db.query(SystemAPISetting).filter(SystemAPISetting.provider == 'runninghub', SystemAPISetting.model == "sparkvideo-2.0-fast").first()
    if existing:
        print("RunningHub SparkVideo 2.0 Fast already exists in SystemAPISetting.")
    else:
        new_setting = SystemAPISetting(
            name="RunningHub SparkVideo 2.0 Fast (I2V)",
            category="Video",
            provider="runninghub",
            base_url="https://www.runninghub.cn",
            model="sparkvideo-2.0-fast",
            modality={"generation_modes": ["i2v"]},
            config={
                "endpoint": "/openapi/v2/rhart-video/sparkvideo-2.0-fast/image-to-video",
                "query_endpoint": "/openapi/v2/query"
            },
            deprecated=False,
            is_active=True,
            tags=["runninghub", "i2v", "fast"]
        )
        db.add(new_setting)
        db.commit()
        db.refresh(new_setting)
        
        billing_rule = SystemAPIBillingRule(
            system_api_setting_id=new_setting.id,
            rule_type="per_request",
            cost_amount=0.5,
            currency="USD",
            is_active=True,
            priority=100
        )
        db.add(billing_rule)
        db.commit()
        print(f"Added RunningHub SparkVideo 2.0 Fast to DB with ID: {new_setting.id}")

if __name__ == '__main__':
    main()
