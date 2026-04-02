const fs = require('fs');
let code = fs.readFileSync('backend/app/api/endpoints.py', 'utf8');

code = code.replace(
/def _resolve_media_runtime_target\(\n    \*,\n    provider: Optional\[str\],\n    model: Optional\[str\],\n    media_type: str,\n    category: str,\n    user_id: int,\n    user_credits: int,\n\) -> Dict\[str, Any\]:/,
`def _resolve_media_runtime_target(
    *,
    provider: Optional[str],
    model: Optional[str],
    media_type: str,
    category: str,
    user_id: int,
    user_credits: int,
    system_api_id: Optional[int] = None,
) -> Dict[str, Any]:`
);

code = code.replace(
/        pre_api_cfg = media_service\.get_api_config\(\n            provider=provider,\n            user_id=user_id,\n            category=category,\n            requested_model=model,\n            user_credits=user_credits,\n            strict_provider=strict_provider,\n        \) or \{\}/,
`        pre_api_cfg = media_service.get_api_config(
            provider=provider,
            user_id=user_id,
            category=category,
            requested_model=model,
            user_credits=user_credits,
            strict_provider=strict_provider,
            system_api_id=system_api_id,
        ) or {}`
);

fs.writeFileSync('backend/app/api/endpoints.py', code, 'utf8');
console.log('Updated _resolve_media_runtime_target args.');