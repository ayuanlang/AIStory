import re

with open('app/api/settings.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'# --- Function API Config Routes ---.*?def get_all_function_api_configs\('

replacement = '''# --- Function API Config Routes ---
from app.schemas.settings import FunctionAPIConfigUpdate, FunctionAPIConfigOut  
from app.models.all_models import APIRoutingConfig

@router.get("/settings/system/api_routing_mode")
def get_api_routing_mode(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not an admin")
    conf = db.query(APIRoutingConfig).first()
    if not conf:
        conf = APIRoutingConfig(use_function_based_routing=False)
        db.add(conf)
        db.commit()
        db.refresh(conf)
    return {"use_function_based_routing": conf.use_function_based_routing}

@router.post("/settings/system/api_routing_mode")
def update_api_routing_mode(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not an admin")
    conf = db.query(APIRoutingConfig).first()
    if not conf:
        conf = APIRoutingConfig(use_function_based_routing=False)
        db.add(conf)

    val = payload.get("use_function_based_routing", False)
    conf.use_function_based_routing = val
    db.commit()
    db.refresh(conf)
    return {"use_function_based_routing": conf.use_function_based_routing}

@router.get("/settings/system/function_api_configs", response_model=List[FunctionAPIConfigOut])
def get_all_function_api_configs('''

text, count = re.subn(pattern, replacement, text, flags=re.DOTALL)
print(count, 'replacements')

with open('app/api/settings.py', 'w', encoding='utf-8') as f:
    f.write(text)
