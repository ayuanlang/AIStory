
const fs = require("fs");
let p = "C:\\AIStory\\backend\\app\\api\\endpoints.py";
let code = fs.readFileSync(p, "utf8");

let re1 = /parsed_rows = parsed_rows\[\:safe_max_scenes\]\s+old_scene_no = str\(db_scene\.scene_no or db_scene\.id\)/;

let rep1 = `parsed_rows = parsed_rows[:safe_max_scenes]

    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found during DB update")
    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id).first()
    project = db.query(Project).filter(Project.id == episode.project_id).first()

    old_scene_no = str(db_scene.scene_no or db_scene.id)`;

code = code.replace(re1, rep1);
fs.writeFileSync(p, code, "utf8");
console.log("Regex replaced.");

