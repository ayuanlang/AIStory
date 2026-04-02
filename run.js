
const fs = require("fs");
let p = "C:\\AIStory\\backend\\app\\api\\endpoints.py";
let code = fs.readFileSync(p, "utf8");

let target = `        if "completion_tokens" in details and "output_tokens" not in details:
            details["output_tokens"] = details.get("completion_tokens", 0)
    billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, details)`;

let rep = `        if "completion_tokens" in details and "output_tokens" not in details:
            details["output_tokens"] = details.get("completion_tokens", 0)
    
    current_user_id = getattr(current_user, "id", None)
    if not current_user_id:
        current_user_id = db.query(User).filter(User.username == current_user.username).first().id if hasattr(current_user, "username") else getattr(current_user, "_sa_instance_state").dict.get("id")

    billing_service.deduct_credits(db, current_user_id, "llm_chat", provider, model, details)`;

if (code.includes(`billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, details)`)) {
    code = code.replace(/billing_service\.deduct_credits\(db, current_user\.id, "llm_chat", provider, model, details\)/g, `billing_service.deduct_credits(db, current_user_id_cached, "llm_chat", provider, model, details)`);
    // Need to define current_user_id_cached early
    let findDef = /db_scene = db\.query\(Scene\)\.filter\(Scene\.id == scene_id\)\.first\(\)/;
    code = code.replace(findDef, "current_user_id_cached = current_user.id\n    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()");
    fs.writeFileSync(p, code, "utf8");
    console.log("Fixed!");
}

