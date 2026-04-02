import re

with open("backend/app/services/media_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update signature to include system_api_id
content = re.sub(
    r"""    def get_api_config\(
        self,
        provider: str,
        user_id: int = 1,
        category: str = None,
        requested_model: Optional\[str\] = None,
        user_credits: int = 0,
        strict_provider: bool = False,
    \) -> Dict\[str, Any\]:""",
    """    def get_api_config(
        self,
        provider: str,
        user_id: int = 1,
        category: str = None,
        requested_model: Optional[str] = None,
        user_credits: int = 0,
        strict_provider: bool = False,
        system_api_id: Optional[int] = None,
    ) -> Dict[str, Any]:""",
    content
)

# 2. Inside the try block, right after `self._repair_invalid_system_config_rows(...)`:
injection = """
                self._repair_invalid_system_config_rows(session, category=category, provider=provider)

                use_function_based_routing = False
                try:
                    from app.models.all_models import APIRoutingConfig
                    routing_conf = session.query(APIRoutingConfig).first()
                    if routing_conf:
                        use_function_based_routing = routing_conf.use_function_based_routing
                except Exception:
                    pass

"""
content = re.sub(r"                self\._repair_invalid_system_config_rows\(session, category=category, provider=provider\)\n", injection, content)

# 3. Override user_setting_id/user_system_api_id if use_function_based_routing is True and system_api_id is passed
override = """
                user_binding_status = "no_user_setting" if not user_setting else ("no_system_api_id" if user_system_api_id <= 0 else "pending")

                if use_function_based_routing and system_api_id is not None:
                    user_system_api_id = int(system_api_id)
                    selected_user_strategy = "unified_function_api"
                    user_setting_id = "func_based_" + getattr(category, "name", str(category))
                    user_binding_status = "function_api_direct_route"
                    
                    # We need to spoof a dummy user_setting so the logic below triggers
                    class DummyUserSetting:
                        system_api_id = user_system_api_id
                        api_strategy = "unified_function_api"
                        id = user_setting_id
                    user_setting = DummyUserSetting()
"""

content = re.sub(
    r"                user_binding_status = \"no_user_setting\" if not user_setting else \(\"no_system_api_id\" if user_system_api_id <= 0 else \"pending\"\)\n",
    override,
    content
)

with open("backend/app/services/media_service.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Backend routing fixed!")