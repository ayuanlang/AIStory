const fs = require('fs');
let code = fs.readFileSync('backend/app/api/endpoints.py', 'utf8');

// For line 21651
code = code.replace(
/    runtime_target = _resolve_media_runtime_target\(\n        provider=req\.provider,\n        model=req\.model,\n        media_type="image",\n        category="Image",\n        user_id=current_user\.id,\n        user_credits=\(current_user\.credits or 0\),\n    \)/g,
`    runtime_target = _resolve_media_runtime_target(
        provider=req.provider,
        model=req.model,
        media_type="image",
        category="Image",
        user_id=current_user.id,
        user_credits=(current_user.credits or 0),
        system_api_id=getattr(req, "system_api_id", None),
    )`
);

// For 23540 generating video
code = code.replace(
/    runtime_target = _resolve_media_runtime_target\(\n        provider=req\.provider,\n        model=req\.model,\n        media_type="video",\n        category="Video",\n        user_id=current_user\.id,\n        user_credits=\(current_user\.credits or 0\),\n    \)/g,
`    runtime_target = _resolve_media_runtime_target(
        provider=req.provider,
        model=req.model,
        media_type="video",
        category="Video",
        user_id=current_user.id,
        user_credits=(current_user.credits or 0),
        system_api_id=getattr(req, "system_api_id", None),
    )`
);

// For 24024 generating voice
code = code.replace(
/    runtime_target = _resolve_media_runtime_target\(\n        provider=req\.provider,\n        model=req\.model,\n        media_type="audio",\n        category="Voice",\n        user_id=current_user\.id,\n        user_credits=\(current_user\.credits or 0\),\n    \)/g,
`    runtime_target = _resolve_media_runtime_target(
        provider=req.provider,
        model=req.model,
        media_type="audio",
        category="Voice",
        user_id=current_user.id,
        user_credits=(current_user.credits or 0),
        system_api_id=getattr(req, "system_api_id", None),
    )`
);

fs.writeFileSync('backend/app/api/endpoints.py', code, 'utf8');
console.log('Updated endpoint calls');