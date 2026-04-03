import re
from sqlalchemy import create_engine
from app.db.session import SessionLocal
from app.models.all_models import Entity, Shot, Project

def _is_dead_link(url: str) -> bool:
    url = str(url or "").strip().lower()
    if not url: return False
    
    # 清理 aitohumanize.com 等临时死链
    if 'aitohumanize.com' in url:
        return True
    
    # 也可以一并清理掉其他绝对写死 localhost 不可访问的外链
    if "http://localhost" in url or "http://127.0.0.1" in url:
        return True
        
    return False

def clean_database():
    db = SessionLocal()
    try:

        cnt_entities = 0
        entities = db.query(Entity).all()
        for e in entities:
            if _is_dead_link(e.image_url):
                e.image_url = ""
                cnt_entities += 1
                
        cnt_shots = 0
        shots = db.query(Shot).all()
        for s in shots:
            shot_changed = False
            if _is_dead_link(s.image_url):
                s.image_url = ""
                shot_changed = True
            
            if _is_dead_link(s.video_url):
                s.video_url = ""
                shot_changed = True
                
            notes = s.technical_notes or {}
            if isinstance(notes, dict) and _is_dead_link(notes.get("end_frame_url")):
                notes["end_frame_url"] = ""
                s.technical_notes = notes
                shot_changed = True
                
            if shot_changed:
                cnt_shots += 1
                
        db.commit()
        print(f"✅ 清理完成！")
        print(f" - 清理了 {cnt_entities} 个实体/角色图片")
        print(f" - 清理了 {cnt_shots} 个镜头的图片/结尾/视频链接")
    finally:
        db.close()

if __name__ == '__main__':
    clean_database()
