
import sys
import os
from sqlalchemy import create_engine, text

# Correct path assuming running from backend root
sys.path.append(os.getcwd())

from app.core.config import settings
from app.models.all_models import Base

def add_columns():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        try:
           # Add name_en
           conn.execute(text("ALTER TABLE entities ADD COLUMN name_en VARCHAR"))
           print("Added name_en")
        except Exception as e:
           print(f"Skipped name_en: {e}")

        try:
           # Add gender
           conn.execute(text("ALTER TABLE entities ADD COLUMN gender VARCHAR"))
           print("Added gender")
        except Exception as e:
           print(f"Skipped gender: {e}")

        try:
           # Add role
           conn.execute(text("ALTER TABLE entities ADD COLUMN role VARCHAR"))
           print("Added role")
        except Exception as e:
           print(f"Skipped role: {e}")
        
        try:
           # Add archetype
           conn.execute(text("ALTER TABLE entities ADD COLUMN archetype VARCHAR"))
           print("Added archetype")
        except Exception as e:
           print(f"Skipped archetype: {e}")
        
        try:
           # Add appearance_cn
           conn.execute(text("ALTER TABLE entities ADD COLUMN appearance_cn TEXT"))
           print("Added appearance_cn")
        except Exception as e:
           print(f"Skipped appearance_cn: {e}")

        try:
           # Add clothing
           conn.execute(text("ALTER TABLE entities ADD COLUMN clothing TEXT"))
           print("Added clothing")
        except Exception as e:
           print(f"Skipped clothing: {e}")

        try:
           # Add action_characteristics
           conn.execute(text("ALTER TABLE entities ADD COLUMN action_characteristics TEXT"))
           print("Added action_characteristics")
        except Exception as e:
           print(f"Skipped action_characteristics: {e}")
           
        try:
           # Add visual_dependencies (JSON)
           conn.execute(text("ALTER TABLE entities ADD COLUMN visual_dependencies JSON"))
           print("Added visual_dependencies")
        except Exception as e:
           print(f"Skipped visual_dependencies: {e}")
           
        try:
           # Add dependency_strategy (JSON)
           conn.execute(text("ALTER TABLE entities ADD COLUMN dependency_strategy JSON"))
           print("Added dependency_strategy")
        except Exception as e:
           print(f"Skipped dependency_strategy: {e}")

if __name__ == "__main__":
    add_columns()
