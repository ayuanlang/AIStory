from app.db.session import SessionLocal
from app.services.media_service import media_service

db = SessionLocal()
config = media_service.get_api_config(
    provider=None,
    user_id=3,
    category="LLM",
    requested_model=None,
    user_credits=0,
    strict_provider=False,
    system_api_id=1062,
    function_name="script_analysis"
)

print("Result:")
print("Provider:", config.get("provider"))
print("Model:", config.get("model"))
if config.get("config"):
    print("Resolved Source:", config["config"].get("__resolved_source"))
else:
    print("No config nested. Result:", config)
