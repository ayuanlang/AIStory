import argparse
from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting
from app.services.modality_utils import migrate_legacy_modality_string


TARGET_PROVIDER = "kie"
TARGET_CATEGORY = "Video"
TARGET_MODEL = "gemini-omni-video"
TARGET_NAME = "Kie Gemini Omni Video"
TARGET_BASE_URL = "https://api.kie.ai"
TARGET_MODALITY = "text-to-video,image-to-video,video-to-video,audio-to-video"


def run(dry_run: bool = False) -> None:
    inserted = 0
    skipped = 0

    with SessionLocal() as session:
        existing = (
            session.query(SystemAPISetting)
            .filter(
                func.lower(SystemAPISetting.provider) == TARGET_PROVIDER.lower(),
                func.lower(SystemAPISetting.category) == TARGET_CATEGORY.lower(),
                func.lower(SystemAPISetting.model) == TARGET_MODEL.lower(),
            )
            .order_by(SystemAPISetting.id.asc())
            .all()
        )

        if existing:
            skipped = len(existing)
            print(
                f"[migrate] skip existing | provider={TARGET_PROVIDER} category={TARGET_CATEGORY} "
                f"model={TARGET_MODEL} ids={[row.id for row in existing]}"
            )
            return

        row = SystemAPISetting(
            name=TARGET_NAME,
            category=TARGET_CATEGORY,
            provider=TARGET_PROVIDER,
            base_url=TARGET_BASE_URL,
            model=TARGET_MODEL,
            modality=migrate_legacy_modality_string(TARGET_MODALITY),
            is_active=False,
            deprecated=False,
            config={},
            tags=[],
        )

        if dry_run:
            print(
                f"[migrate] dry-run insert | provider={TARGET_PROVIDER} category={TARGET_CATEGORY} model={TARGET_MODEL}"
            )
            return

        session.add(row)
        session.commit()
        session.refresh(row)
        inserted = 1
        print(
            f"[migrate] inserted | id={row.id} provider={TARGET_PROVIDER} category={TARGET_CATEGORY} model={TARGET_MODEL}"
        )

    print(f"[migrate] done | inserted={inserted} skipped={skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add KIE gemini-omni-video system API row if missing")
    parser.add_argument("--dry-run", action="store_true", help="Print intended action without writing")
    args = parser.parse_args()
    run(dry_run=bool(args.dry_run))
