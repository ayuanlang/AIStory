
path = 'c:/AIStory/backend/app/api/settings.py'
code = \\\
class APIRoutingConfigOut(BaseModel):
    use_function_based_routing: bool

class APIRoutingConfigUpdate(BaseModel):
    use_function_based_routing: bool

@router.get('/settings/system/api-routing-config', response_model=APIRoutingConfigOut)
def get_api_routing_config(db: Session = Depends(get_db)):
    from app.models.all_models import APIRoutingConfig
    config = db.query(APIRoutingConfig).first()
    return {'use_function_based_routing': config.use_function_based_routing if config else False}

@router.put('/settings/system/api-routing-config', response_model=APIRoutingConfigOut)
def update_api_routing_config(
    payload: APIRoutingConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.all_models import APIRoutingConfig
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail='Only system/admin users can manage routing config')
    config = db.query(APIRoutingConfig).first()
    if not config:
        config = APIRoutingConfig(use_function_based_routing=payload.use_function_based_routing)
        db.add(config)
    else:
        config.use_function_based_routing = payload.use_function_based_routing
    db.commit()
    return {'use_function_based_routing': config.use_function_based_routing}
\\\
with open(path, 'a', encoding='utf-8') as f:
    f.write('\\n' + code + '\\n')

