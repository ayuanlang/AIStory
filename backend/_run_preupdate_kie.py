import asyncio
from types import SimpleNamespace

from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting
from app.schemas.settings import SupplierApiFeatureAnalyzeRequest
from app.api.settings import ai_assistant_analyze_supplier_features


def main() -> None:
    db = SessionLocal()
    try:
        rows = (
            db.query(SystemAPISetting)
            .filter(SystemAPISetting.provider == "kie")
            .filter(~SystemAPISetting.category.like("System_%"))
            .all()
        )
        selected_ids = [int(r.id) for r in rows if getattr(r, "id", None) is not None]

        payload = SupplierApiFeatureAnalyzeRequest(
            provider="kie",
            source_urls=["https://docs.kie.ai/llms.txt"],
            selected_system_api_ids=[],
            include_provider_intro_url=False,
            search_keywords=[
                "llm",
                "chat",
                "completion",
                "context window",
                "input tokens",
                "output tokens",
                "voice",
                "music",
            ],
            user_supplement=(
                "请优先覆盖 settings 中已存在的 kie 模型，按当前提示词要求提取 Text/Voice/Music 与计费相关信息；"
                "无可靠信息时保持空字段并标注 warnings。"
            ),
            max_length=12000,
            max_pages=1,
            save_to_db=True,
            create_missing_models=True,
        )

        user = SimpleNamespace(is_superuser=True)
        resp = asyncio.run(
            ai_assistant_analyze_supplier_features(
                payload=payload,
                db=db,
                current_user=user,
            )
        )

        print("=== PREUPDATE_RESULT ===")
        print(f"provider={resp.provider}")
        print(f"db_existing_kie_count={len(selected_ids)}")
        print(f"selected_system_api_count={resp.selected_system_api_count}")
        print(f"analyzed_url_count={resp.analyzed_url_count}")
        print(f"models={len(resp.models)}")
        print(f"saved_created={resp.saved_created}")
        print(f"saved_updated={resp.saved_updated}")
        print("warnings=")
        for w in (resp.warnings or [])[:50]:
            print(f"- {w}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
