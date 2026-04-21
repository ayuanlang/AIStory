import re

def main():
    path_endpoints = 'backend/app/api/endpoints.py'
    with open(path_endpoints, 'r', encoding='utf-8') as f:
        text = f.read()

    # The loop over rows in `/billing/transactions`
    old_loop = """    rows = query.order_by(TransactionHistory.id.desc()).limit(limit).all()
    alias_map = _build_provider_alias_lookup(db)
    results: List[Dict[str, Any]] = []
    for row in rows:
        provider_text = str(getattr(row, "provider", "") or "").strip() or None
        provider_alias = _resolve_provider_alias(alias_map, provider_text)
        details_payload = _attach_provider_alias_deep(getattr(row, "details", None), alias_map)
        payload = {
            "id": row.id,
            "user_id": row.user_id,
            "amount": row.amount,
            "balance_after": row.balance_after,
            "task_type": row.task_type,
            "provider": row.provider,
            "model": row.model,
            "details": details_payload,
            "created_at": row.created_at,
        }
        if provider_alias:
            payload["provider_alias"] = provider_alias
        results.append(payload)

    return results"""

    new_loop = """    rows = query.order_by(TransactionHistory.id.desc()).limit(limit).all()
    alias_map = _build_provider_alias_lookup(db)
    results: List[Dict[str, Any]] = []
    for row in rows:
        # Action audit holds provider, model, task_type, etc.
        action = row.action_audit
        provider_text = str(getattr(action, "provider", "") or "").strip() or None if action else None
        model_text = action.model if action else None
        task_text = action.task_type if action else None
        project_id = action.project_id if action else None
        episode_id = action.episode_id if action else None
        
        provider_alias = _resolve_provider_alias(alias_map, provider_text)
        details_payload = _attach_provider_alias_deep(getattr(row, "details", None), alias_map)
        
        # Support fallback description
        display_description = row.description
        if not display_description and task_text:
            display_description = task_text
            
        payload = {
            "id": row.id,
            "user_id": row.user_id,
            "amount": row.amount,
            "balance_after": row.balance_after,
            "description": display_description,
            "task_type": task_text,
            "provider": provider_text,
            "model": model_text,
            "details": details_payload,
            "project_id": project_id,
            "episode_id": episode_id,
            "created_at": row.created_at,
        }
        if provider_alias:
            payload["provider_alias"] = provider_alias
        results.append(payload)

    return results"""

    text = text.replace(old_loop, new_loop, 1)

    with open(path_endpoints, 'w', encoding='utf-8') as f:
        f.write(text)

    path_schema = 'backend/app/schemas/billing.py'
    with open(path_schema, 'r', encoding='utf-8') as f:
        schema_text = f.read()

    old_schema = """class TransactionOut(BaseModel):
    id: int
    user_id: int
    amount: int
    balance_after: int
    task_type: Optional[str] = None
    provider: Optional[str] = None
    provider_alias: Optional[str] = None
    model: Optional[str] = None
    details: Optional[Any] = None
    created_at: str"""

    new_schema = """class TransactionOut(BaseModel):
    id: int
    user_id: int
    amount: int
    balance_after: int
    description: Optional[str] = None
    task_type: Optional[str] = None
    provider: Optional[str] = None
    provider_alias: Optional[str] = None
    model: Optional[str] = None
    details: Optional[Any] = None
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    created_at: str"""

    if old_schema in schema_text:
        schema_text = schema_text.replace(old_schema, new_schema, 1)
        with open(path_schema, 'w', encoding='utf-8') as f:
            f.write(schema_text)
        print("Schema patched.")
    else:
        print("Schema already patched or not found.")

if __name__ == '__main__':
    main()
