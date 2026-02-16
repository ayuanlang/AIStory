
from app.db.session import SessionLocal
from app.models.all_models import Project, Shot, Entity, Episode, Scene

db = SessionLocal()

projects = db.query(Project).all()
print(f"Found {len(projects)} projects.")

for p in projects:
    print(f"Project ID: {p.id}, Title: {p.title}")
    
    # Check Shots with direct project_id
    shots_direct = db.query(Shot).filter(Shot.project_id == p.id, Shot.image_url != None, Shot.image_url != "").all()
    print(f"  Shots (direct): {len(shots_direct)}")
    if shots_direct:
        print(f"    Sample Image: {shots_direct[0].image_url}")

    # Check Shots via join
    shots_join = db.query(Shot).join(Scene).join(Episode).filter(Episode.project_id == p.id, Shot.image_url != None, Shot.image_url != "").all()
    print(f"  Shots (join): {len(shots_join)}")
    if shots_join:
        print(f"    Sample Image: {shots_join[0].image_url}")

    # Check Entities
    entities = db.query(Entity).filter(Entity.project_id == p.id, Entity.image_url != None, Entity.image_url != "").all()
    print(f"  Entities: {len(entities)}")
    if entities:
        print(f"    Sample Image: {entities[0].image_url}")

db.close()
