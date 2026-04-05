import os
import sys
from sqlalchemy import text
from sqlalchemy.orm import Session

# Ensure we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
from app.db.session import SessionLocal
from app.models.all_models import SystemAPIBillingRule, SystemAPISetting

def add_n1n_functional_routing_and_mappings():
    db = SessionLocal()
    try:
        # --- 1. FUNCTIONAL ROUTING via Billing Rules ---
        print("Configuring functional routing (duration and resolution boundaries)...")
        
        # We define rules for Sora models to support specific lengths and sizes
        # 10s: 9.0 ~ 11.0
        # 15s: 14.0 ~ 16.0
        # 25s: 24.0 ~ 26.0
        # 720p: height 700 ~ 800
        # 1080p: height 1000 ~ 1100

        sora_configs = {
            "sora-2-all": [
                # 10s 720p
                {"min_d": 9.0, "max_d": 11.0, "min_h": 700, "max_h": 800, "cost": 0.200},
                # 15s 720p
                {"min_d": 14.0, "max_d": 16.0, "min_h": 700, "max_h": 800, "cost": 0.200},
            ],
            "sora-2-pro-all": [
                # 15s 1080p
                {"min_d": 14.0, "max_d": 16.0, "min_h": 1000, "max_h": 1150, "cost": 3.600},
                # 15s 720p
                {"min_d": 14.0, "max_d": 16.0, "min_h": 700, "max_h": 800, "cost": 3.600},
                # 25s 720p
                {"min_d": 24.0, "max_d": 26.0, "min_h": 700, "max_h": 800, "cost": 3.600},
            ],
            "sora-2-vip-all": [
                # 10s (any resolution implied, but we can set open height)
                {"min_d": 9.0, "max_d": 11.0, "min_h": None, "max_h": None, "cost": 2.500},
            ]
        }
        
        USD_TO_CREDITS = 7 * 100

        for model_name, rules in sora_configs.items():
            setting = db.query(SystemAPISetting).filter_by(provider="n1n", model=model_name).first()
            if not setting: continue
            
            # Clear old generic rules for this video model
            db.query(SystemAPIBillingRule).filter_by(system_api_id=setting.id).delete()
            
            # Add specific bounded rules
            for rule in rules:
                db.add(SystemAPIBillingRule(
                    system_api_id=setting.id,
                    name=f"Per Call ({rule['min_d']}s)",
                    applies_to_video=True,
                    billing_unit_type="per_call",
                    billing_cost=rule["cost"] * USD_TO_CREDITS,
                    duration_seconds_min=rule["min_d"],
                    duration_seconds_max=rule["max_d"],
                    height_min=rule["min_h"],
                    height_max=rule["max_h"]
                ))
            print(f"  - Updated functional routing bounds for {model_name}")

        
        # --- 2. DATA MAPPINGS ---
        print("Configuring KIE Standard Data Mappings for n1n...")
        # Since n1n is OpenAI-compatible (gpt-series, sora wrappers probably adopt OAI structure or standard structures)
        # We will insert some essential mappings if the schema exists
        
        mapping_table_exists = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='kie_system_data_standard_mappings'")).fetchone()
        
        if mapping_table_exists:
            # We map standard "t2v" (Text-to-Video), "t2i" (Text-to-Image) modes for these
            mappings_to_insert = [
                # GPT Image models
                ("n1n", "gpt-image-1.5-all", "payload.mode", "t2i", "GENERATION_MODE", "t2i", "std_to_api:exact"),
                ("n1n", "gpt-4o-image-vip", "payload.mode", "t2i", "GENERATION_MODE", "t2i", "std_to_api:exact"),
                # Sora Video models
                ("n1n", "sora-2-all", "payload.mode", "t2v", "GENERATION_MODE", "t2v", "std_to_api:exact"),
                ("n1n", "sora-2-pro-all", "payload.mode", "t2v", "GENERATION_MODE", "t2v", "std_to_api:exact"),
                ("n1n", "sora-2-vip-all", "payload.mode", "t2v", "GENERATION_MODE", "t2v", "std_to_api:exact"),
                # Veo Video models
                ("n1n", "veo_3_1-4K", "payload.mode", "t2v", "GENERATION_MODE", "t2v", "std_to_api:exact"),
                ("n1n", "veo_3_1-components-4K", "payload.mode", "t2v", "GENERATION_MODE", "t2v", "std_to_api:exact"),
                # Gemini Image models
                ("n1n", "gemini-3.1-flash-image-preview", "payload.mode", "t2i", "GENERATION_MODE", "t2i", "std_to_api:exact"),
                ("n1n", "gemini-3-pro-image-preview", "payload.mode", "t2i", "GENERATION_MODE", "t2i", "std_to_api:exact"),
            ]
            
            for provider, model_id, field, source_val, dim, std_val, conf in mappings_to_insert:
                # Upsert logic to avoid unique constraint violation
                db.execute(text("""
                    INSERT OR IGNORE INTO kie_system_data_standard_mappings 
                    (provider, model_key_inferred, source_field, source_enum_value, standard_dimension, standard_value, confidence, is_active)
                    VALUES (:p, :m, :f, :sv, :dim, :std, :c, 1)
                """), {
                    "p": provider, "m": model_id, "f": field, "sv": source_val, "dim": dim, "std": std_val, "c": conf
                })
            
            print("  - Inserted mappings for t2i/t2v generation modes.")
        else:
            print("  - Mapping table not found, skipping mappings.")

        db.commit()
        print("\n✅ Functional routing and Data mappings applied successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Operation failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    add_n1n_functional_routing_and_mappings()
