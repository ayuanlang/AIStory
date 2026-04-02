const fs = require('fs');
let code = fs.readFileSync('backend/app/services/media_service.py', 'utf8');

code = code.replace(
/    def get_api_config\(\n        self,\n        provider: str,\n        user_id: int = 1,\n        category: str = None,\n        requested_model: Optional\[str\] = None,\n        user_credits: int = 0,\n        strict_provider: bool = False,\n    \) -> Dict\[str, Any\]:/g,
`    def get_api_config(
        self,
        provider: str,
        user_id: int = 1,
        category: str = None,
        requested_model: Optional[str] = None,
        user_credits: int = 0,
        strict_provider: bool = False,
        system_api_id: Optional[int] = None,
    ) -> Dict[str, Any]:`
);

code = code.replace(
`            with SessionLocal() as session:\n                resolved_category = str(category or "").strip()`,
`            with SessionLocal() as session:
                resolved_category = str(category or "").strip()
                use_function_based_routing = False
                try:
                    from app.models.all_models import APIRoutingConfig
                    routing_conf = session.query(APIRoutingConfig).first()
                    if routing_conf:
                        use_function_based_routing = routing_conf.use_function_based_routing
                except Exception as e:
                    pass`
);

let findString = `                    user_setting = session.query(APISetting).filter(
                        APISetting.user_id == user_id, APISetting.category == resolved_category
                    ).order_by(APISetting.id.desc()).first()`;

let replaceString = `                    selected_system_setting_id = None
                    selected_user_strategy = "smart_default"

                    if use_function_based_routing and system_api_id is not None:
                        selected_system_setting_id = int(system_api_id)
                        selected_user_strategy = "unified_function_api"
                    else:
                        user_setting = session.query(APISetting).filter(
                            APISetting.user_id == user_id, 
                            APISetting.category == resolved_category
                        ).order_by(APISetting.id.desc()).first()
                        selected_system_setting_id = int(getattr(user_setting, "system_api_id", 0) or 0)`;

code = code.replace(findString, replaceString);

// Remove the old `selected_system_setting_id = int(getattr(user_setting, "system_api_id", 0) or 0)`
// Which is directly under user_setting query.
code = code.replace(/                    selected_user_strategy = "smart_default"\n                    selected_system_setting_id = int\(getattr\(user_setting, "system_api_id", 0\) or 0\)\n/, '');
code = code.replace(/                    selected_system_setting_id = int\(getattr\(user_setting, "system_api_id", 0\) or 0\)\n                    selected_user_strategy = "smart_default"\n/, '');
code = code.replace(/                    selected_system_setting_id = getattr\(user_setting, "system_api_id", None\)\n                    if selected_system_setting_id:\n                        selected_system_setting_id = int\(selected_system_setting_id\)\n                    else:\n                        selected_system_setting_id = 0\n                    selected_user_strategy = "smart_default"/, '');

fs.writeFileSync('backend/app/services/media_service.py', code, 'utf8');
console.log('Updated get_api_config inside media_service.py!');