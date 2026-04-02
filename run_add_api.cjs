const fs = require('fs');
let code = fs.readFileSync('backend/app/api/settings.py', 'utf8');

const target = "def get_all_function_api_configs(";

const newCode = `
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

def get_all_function_api_configs(`;

code = code.replace(target, newCode);
fs.writeFileSync('backend/app/api/settings.py', code, 'utf8');
console.log('Added api endpoint');