import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(settings.BASE_DIR) / "app" / "core" / "prompts" / "supplier_feature_analysis_system_prompt.txt"
_PROMPT_FALLBACK = (
    "You are a senior API product + billing analyst. Return ONE valid JSON object only. "
    "Extract model-level capabilities and billing clues from supplier docs."
)


def get_supplier_feature_analysis_system_prompt() -> str:
    try:
        content = _PROMPT_PATH.read_text(encoding="utf-8").strip()
        if content:
            return content
    except Exception as exc:
        logger.error("failed to read supplier feature analysis prompt file %s: %s", _PROMPT_PATH, exc)
    return _PROMPT_FALLBACK


SUPPLIER_FEATURE_ANALYSIS_SYSTEM_PROMPT = get_supplier_feature_analysis_system_prompt()
