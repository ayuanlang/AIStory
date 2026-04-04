import os
import sys

# Ensure backend root is in PYTHON_PATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting, SystemAPIBillingRule

# Define provider name
PROVIDER_NAME = "aiclub"
BASE_URL = "https://aiclub.zimaocloud.com/model/openApi/v1"

# Models extract based on the docs list provided
MODELS = [
    {"name": "Doubao Chat", "category": "LLM", "model": "doubao-seed-1-6-lite-251015", "modality": {}, "billing_type": "tokens", "price_in": 0.01, "price_out": 0.02},
    {"name": "Doubao Image Gen", "category": "Image", "model": "doubao-image", "modality": {"generation_modes": ["t2i"]}, "billing_type": "per_request", "price_req": 0.5},
    {"name": "Doubao Video Gen", "category": "Video", "model": "doubao-video", "modality": {"generation_modes": ["t2v", "i2v"]}, "billing_type": "per_request", "price_req": 2.0},
    {"name": "Kimi Chat", "category": "LLM", "model": "moonshot-v1-8k", "modality": {}, "billing_type": "tokens", "price_in": 0.05, "price_out": 0.08},
    {"name": "GLM Chat", "category": "LLM", "model": "glm-4", "modality": {}, "billing_type": "tokens", "price_in": 0.03, "price_out": 0.03},
    {"name": "Kling T2V", "category": "Video", "model": "kling-v1-txt2video", "modality": {"generation_modes": ["t2v"]}, "billing_type": "per_request", "price_req": 5.0},
    {"name": "Kling I2V", "category": "Video", "model": "kling-v1-img2video", "modality": {"generation_modes": ["i2v"]}, "billing_type": "per_request", "price_req": 5.0},
    {"name": "VEO Video Gen", "category": "Video", "model": "veo-video", "modality": {"generation_modes": ["t2v"]}, "billing_type": "per_request", "price_req": 6.0},
    {"name": "Hailuo T2V", "category": "Video", "model": "hailuo-t2v", "modality": {"generation_modes": ["t2v"]}, "billing_type": "per_request", "price_req": 4.0},
    {"name": "Hailuo I2V", "category": "Video", "model": "hailuo-i2v", "modality": {"generation_modes": ["i2v"]}, "billing_type": "per_request", "price_req": 4.0},
    {"name": "Tongyi Wanxiang T2V", "category": "Video", "model": "wanx-t2v", "modality": {"generation_modes": ["t2v"]}, "billing_type": "per_request", "price_req": 3.0},
    {"name": "Tongyi Wanxiang I2V", "category": "Video", "model": "wanx-i2v", "modality": {"generation_modes": ["i2v"]}, "billing_type": "per_request", "price_req": 3.0},
    {"name": "Vidu T2V", "category": "Video", "model": "vidu-t2v", "modality": {"generation_modes": ["t2v"]}, "billing_type": "per_request", "price_req": 3.5},
    {"name": "Vidu I2V", "category": "Video", "model": "vidu-i2v", "modality": {"generation_modes": ["i2v"]}, "billing_type": "per_request", "price_req": 3.5},
    {"name": "Jimeng Video", "category": "Video", "model": "jimeng-video", "modality": {"generation_modes": ["t2v", "i2v"]}, "billing_type": "per_request", "price_req": 4.0},
    {"name": "Sora Video Gen", "category": "Video", "model": "sora", "modality": {"generation_modes": ["t2v"]}, "billing_type": "per_request", "price_req": 20.0},
    {"name": "Deepseek Chat", "category": "LLM", "model": "deepseek-chat", "modality": {}, "billing_type": "tokens", "price_in": 0.01, "price_out": 0.02},
    {"name": "Gemini Nano Image", "category": "Image", "model": "gemini-2.5-flash-image", "modality": {"generation_modes": ["t2i"]}, "billing_type": "per_request", "price_req": 1.0},
    {"name": "ChatGPT Chat", "category": "LLM", "model": "gpt-4o", "modality": {}, "billing_type": "tokens", "price_in": 0.1, "price_out": 0.15},
]

def main():
    db: Session = SessionLocal()
    try:
        inserted = 0
        for m in MODELS:
            # Check if exists
            existing = db.query(SystemAPISetting).filter(
                SystemAPISetting.provider == PROVIDER_NAME,
                SystemAPISetting.model == m["model"]
            ).first()
            
            if not existing:
                setting = SystemAPISetting(
                    name=m["name"],
                    category=m["category"],
                    provider=PROVIDER_NAME,
                    base_url=BASE_URL,
                    model=m["model"],
                    modality=m["modality"],
                    is_active=False,      # Preset to inactive
                    deprecated=True,      # Preset to deprecated
                    config={"sync_source": "aiclub"}
                )
                db.add(setting)
                db.flush()
                
                # Add billing rule
                if m["billing_type"] == "tokens":
                    # cost is typically integer representing some smallest unit for db storage (like 1/1000th of token)
                    # using the extracted value directly; if need *1000 or similar adjust accordingly 
                    rule = SystemAPIBillingRule(
                        system_api_id=setting.id,
                        name=f"{m['name']} Rule",
                        applies_to_text=True,
                        billing_unit_type="tokens",
                        billing_cost_input=int(m["price_in"] * 1000), # example: microcents or scaled
                        billing_cost_output=int(m["price_out"] * 1000),
                        is_active=True
                    )
                else:
                    rule = SystemAPIBillingRule(
                        system_api_id=setting.id,
                        name=f"{m['name']} Rule",
                        applies_to_image=m["category"] == "Image",
                        applies_to_video=m["category"] == "Video",
                        billing_unit_type="per_call",
                        billing_cost=int(m["price_req"] * 1000), 
                        is_active=True
                    )
                db.add(rule)
                inserted += 1
                print(f"Inserted: {m['name']} ({m['model']})")
            else:
                # Update existing deprecated status
                existing.is_active = False
                existing.deprecated = True
                print(f"Skipped existing (deprecated updated): {m['name']} ({m['model']})")

        db.commit()
        print(f"\nDone. Successfully added {inserted} aiclub models as deprecated.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
