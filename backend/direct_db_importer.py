
import os
import sys
import json
from sqlalchemy.orm import Session

# Adjust path to allow imports from the app directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting, SystemAPIBillingRule

# --- Combined Model Data ---
N1N_MODELS_DATA = [
    # Batch 1
    {"name": "gemini-3.1-flash-lite-preview", "category": "LLM", "description": "...", "pricing": {"input": 0.3750, "output": 2.2500, "unit": "M_tokens"}},
    {"name": "gemini-3.1-pro-preview", "category": "LLM", "description": "...", "pricing": {"input": 3.0000, "output": 18.0000, "unit": "M_tokens"}},
    {"name": "gemini-3.1-flash-image-preview", "category": "Image", "description": "...", "pricing": {"unit_price": 0.166, "unit": "image"}},
    {"name": "gemini-3-pro-image-preview", "category": "Image", "description": "...", "pricing": {"unit_price": 0.330, "unit": "image"}},
    {"name": "gemini-3-pro-preview", "category": "LLM", "description": "...", "pricing": {"input": 1.6000, "output": 9.6000, "unit": "M_tokens"}},
    {"name": "gemini-3-flash-preview", "category": "LLM", "description": "...", "pricing": {"input": 0.4000, "output": 2.4000, "unit": "M_tokens"}},
    {"name": "gemini-2.5-flash-preview-tts", "category": "Voice", "description": "...", "pricing": {"input": 0.7500, "output": 15.0000, "unit": "M_tokens"}},
    {"name": "gemini-2.5-pro-preview-tts", "category": "Voice", "description": "...", "pricing": {"input": 1.5000, "output": 30.0000, "unit": "M_tokens"}},
    {"name": "veo_3_1-components-4K", "category": "Video", "description": "...", "pricing": {"unit_price": 0.850, "unit": "video"}},
    {"name": "gemini-3-pro-preview-11-2025", "category": "LLM", "description": "...", "pricing": {"input": 1.6000, "output": 9.6000, "unit": "M_tokens"}},
    {"name": "gemini-3-pro-preview-thinking", "category": "LLM", "description": "...", "pricing": {"input": 3.0000, "output": 18.0000, "unit": "M_tokens"}},
    {"name": "veo_3_1-4K", "category": "Video", "description": "...", "pricing": {"unit_price": 0.850, "unit": "video"}},
    {"name": "veo_3_1-fast-4K", "category": "Video", "description": "...", "pricing": {"unit_price": 0.430, "unit": "video"}},
    {"name": "veo_3_1-fast-components-4K", "category": "Video", "description": "...", "pricing": {"unit_price": 0.860, "unit": "video"}},
    {"name": "veo3.1-4k", "category": "Video", "description": "...", "pricing": {"unit_price": 1.000, "unit": "video"}},
    {"name": "veo3.1-components-4k", "category": "Video", "description": "...", "pricing": {"unit_price": 1.000, "unit": "video"}},
    {"name": "gemini-2.5-flash-image", "category": "Image", "description": "...", "pricing": {"unit_price": 0.090, "unit": "image"}},
    {"name": "gemini-2.5-flash-image-preview", "category": "Image", "description": "...", "pricing": {"unit_price": 0.090, "unit": "image"}},
    {"name": "gemini-2.5-pro", "category": "LLM", "description": "...", "pricing": {"input": 1.0000, "output": 8.0000, "unit": "M_tokens"}},
    {"name": "gemini-2.5-pro-thinking", "category": "LLM", "description": "...", "pricing": {"input": 1.8750, "output": 15.0000, "unit": "M_tokens"}},
    # Batch 2
    {"name": "gpt-5.3-codex-medium", "category": "LLM", "description": "...", "pricing": {"input": 1.4000, "output": 11.2000, "unit": "M_tokens"}},
    {"name": "gpt-5.3-codex-xhigh", "category": "LLM", "description": "...", "pricing": {"input": 1.4000, "output": 11.2000, "unit": "M_tokens"}},
    {"name": "gpt-5.2-codex", "category": "LLM", "description": "...", "pricing": {"input": 1.4000, "output": 11.2000, "unit": "M_tokens"}},
    {"name": "gpt-image-1.5-all", "category": "Image", "description": "...", "pricing": {"unit_price": 0.078, "unit": "image"}},
    {"name": "gpt-5.1-all", "category": "LLM", "description": "...", "pricing": {"input": 1.2500, "output": 10.0000, "unit": "M_tokens"}},
    {"name": "gpt-5.1-codex-max", "category": "LLM", "description": "...", "pricing": {"input": 0.7500, "output": 6.0000, "unit": "M_tokens"}},
    {"name": "gpt-5.1-thinking-all", "category": "LLM", "description": "...", "pricing": {"input": 1.2500, "output": 10.0000, "unit": "M_tokens"}},
    {"name": "gpt-5.2-all", "category": "LLM", "description": "...", "pricing": {"input": 1.7500, "output": 14.0000, "unit": "M_tokens"}},
    {"name": "sora-2-all", "category": "Video", "description": "...", "pricing": {"unit_price": 0.200, "unit": "video"}},
    {"name": "sora-2-pro-all", "category": "Video", "description": "...", "pricing": {"unit_price": 3.600, "unit": "video"}},
    {"name": "sora-2-vip-all", "category": "Video", "description": "...", "pricing": {"unit_price": 2.500, "unit": "video"}},
    {"name": "gpt-5.1-codex", "category": "LLM", "description": "...", "pricing": {"input": 0.7500, "output": 6.0000, "unit": "M_tokens"}},
    {"name": "sora-2-characters", "category": "Video", "description": "...", "pricing": {"unit_price": 0.010, "unit": "video"}},
    {"name": "gpt-4o-image-vip", "category": "Image", "description": "...", "pricing": {"unit_price": 0.120, "unit": "image"}},
    {"name": "gpt-5-all", "category": "LLM", "description": "...", "pricing": {"input": 1.2500, "output": 10.0000, "unit": "M_tokens"}},
    {"name": "gpt-5-pro-all", "category": "LLM", "description": "...", "pricing": {"unit_price": 1.610, "unit": "invocation"}},
]

def main():
    db: Session = SessionLocal()
    
    # Assuming 1 USD = 7 CNY and 1 CNY = 100 credits
    USD_TO_CREDITS = 7 * 100
    provider_name = "n1n"
    
    created_count = 0
    updated_count = 0

    try:
        for model_data in N1N_MODELS_DATA:
            model_name = model_data["name"]
            
            # Check if setting exists
            setting = db.query(SystemAPISetting).filter(
                SystemAPISetting.provider == provider_name,
                SystemAPISetting.model == model_name
            ).first()

            config_payload = {
                "supplier_info": {
                    "description": model_data["description"]
                }
            }

            if setting:
                # Update existing setting
                setting.name = model_data["name"]
                setting.category = model_data["category"]
                setting.base_url = "https://api.n1n.ai/v1"
                setting.config = config_payload
                setting.deprecated = False
                updated_count += 1
                print(f"Updating model: {model_name}")
            else:
                # Create new setting
                setting = SystemAPISetting(
                    name=model_data["name"],
                    category=model_data["category"],
                    provider=provider_name,
                    model=model_name,
                    base_url="https://api.n1n.ai/v1",
                    api_key="YOUR_N1N_API_KEY", # Placeholder
                    is_active=True,
                    deprecated=False,
                    config=config_payload
                )
                db.add(setting)
                created_count += 1
                print(f"Creating model: {model_name}")

            # Flush to get the setting ID for new records
            db.flush()

            # Delete old billing rules for this setting
            db.query(SystemAPIBillingRule).filter(SystemAPIBillingRule.system_api_id == setting.id).delete(synchronize_session=False)
            
            # Create new billing rules
            pricing = model_data["pricing"]
            if pricing["unit"] == "M_tokens":
                # Assuming USD_TO_CREDITS transforms cost correctly
                cost_input = (pricing["input"] / 1_000_000) * USD_TO_CREDITS
                cost_output = (pricing["output"] / 1_000_000) * USD_TO_CREDITS
                db.add(SystemAPIBillingRule(
                    system_api_id=setting.id, 
                    name="Per Token Pricing", 
                    applies_to_text=True,
                    billing_unit_type="per_token",
                    billing_cost_input=cost_input,
                    billing_cost_output=cost_output
                ))
            elif pricing["unit"] in ["image", "video", "invocation"]:
                cost = pricing["unit_price"] * USD_TO_CREDITS
                is_image = pricing["unit"] == "image"
                is_video = pricing["unit"] == "video"
                db.add(SystemAPIBillingRule(
                    system_api_id=setting.id, 
                    name="Per Call Pricing", 
                    applies_to_image=is_image, 
                    applies_to_video=is_video,
                    billing_unit_type="per_call",
                    billing_cost=cost
                ))
            
            print(f"  - Billing rules processed for {model_name}")

        db.commit()
        print("\n✅ Database import successful!")
        print(f"   - Created: {created_count} models")
        print(f"   - Updated: {updated_count} models")

    except Exception as e:
        db.rollback()
        print(f"❌ Database import failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Simplified description for brevity in the log
    for model in N1N_MODELS_DATA:
        model['description'] = model['description'][:20] + '...'
    main()
