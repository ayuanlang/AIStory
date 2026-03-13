import csv
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "backend" / "aistory.db"
INPUT_CSV = ROOT / "_kie_billing_rule_candidates_detailed.csv"
OUT_CSV = ROOT / "_kie_billing_rule_candidates_system_api_integrated.csv"
OUT_MD = ROOT / "_kie_billing_rule_candidates_system_api_integrated.md"


ALIAS_MODEL_BY_URL_PATH = {
    "/4o-image-api/generate-4-o-image.md": "gpt4o-image",
    "/flux-kontext-api/generate-or-edit-image.md": "flux/kontext",
}


def _norm(value: str) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    s = s.replace("_", "-")
    s = re.sub(r"\s+", "", s)
    return s


def _norm_slug(value: str) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower().replace("_", "-")
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def normalize_generation_mode(value: str) -> str:
    gm = _norm_slug(value)
    aliases = {
        "": "",
        "i2i": "image-edit",
        "image-to-image": "image-edit",
        "image2image": "image-edit",
        "img2img": "image-edit",
        "t2i": "text-to-image",
        "t2v": "text-to-video",
        "i2v": "image-to-video",
        "v2v": "video-to-video",
    }
    return aliases.get(gm, gm)


def gm_for_db_lookup(gm_split: str) -> str:
    if gm_split == "image-edit":
        return "image-to-image"
    return gm_split


def parse_bool_or_blank(value: str):
    s = _norm(value)
    if s in {"", "none", "null"}:
        return ""
    if s in {"1", "true", "yes", "y"}:
        return "true"
    if s in {"0", "false", "no", "n"}:
        return "false"
    return ""


def extract_model_from_url(url: str) -> str:
    if not url:
        return ""

    parsed = urlparse(url)
    path = parsed.path
    if path in ALIAS_MODEL_BY_URL_PATH:
        return ALIAS_MODEL_BY_URL_PATH[path]

    market_prefix = "/market/"
    if path.startswith(market_prefix) and path.endswith(".md"):
        key = path[len(market_prefix) : -3]
        key = key.replace("flux2/", "flux-2/")
        # Normalize common doc-vs-DB naming differences.
        key = key.replace("kling/v25-", "kling/v2-5-")
        key = key.replace("gemini/", "")
        key = key.replace("seedream/4-5-", "seedream/4.5-")
        if key == "kling/image-to-video":
            key = "kling-2.6/image-to-video"
        elif key == "kling/text-to-video":
            key = "kling-2.6/text-to-video"
        elif key == "kling/motion-control":
            key = "kling-2.6/motion-control"
        return key

    return ""


def split_modes(raw: str) -> set[str]:
    if not raw:
        return set()
    text = str(raw)
    parts = re.split(r"[\[\]\",]+", text)
    out = set()
    for p in parts:
        n = _norm_slug(p)
        if n:
            out.add(n)
    return out


def split_formats(raw: str) -> set[str]:
    if not raw:
        return set()
    text = str(raw)
    parts = re.split(r"[\[\]\",]+", text)
    out = set()
    for p in parts:
        n = _norm_slug(p)
        if n:
            out.add(n)
    return out


def load_settings(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, category, provider, model, name, is_active,
               generation_modes, input_formats, output_format, has_audio
        FROM system_api_settings
        WHERE provider = 'kie'
        """
    )
    rows = []
    for r in cur.fetchall():
        model = (r["model"] or "").strip()
        rows.append(
            {
                "id": r["id"],
                "category": (r["category"] or "").strip(),
                "provider": (r["provider"] or "").strip(),
                "model": model,
                "model_norm": _norm(model),
                "name": (r["name"] or "").strip(),
                "is_active": int(r["is_active"] or 0),
                "generation_modes": split_modes(r["generation_modes"]),
                "input_formats": split_formats(r["input_formats"]),
                "output_format": _norm_slug(r["output_format"]),
                "has_audio": parse_bool_or_blank(r["has_audio"]),
            }
        )
    return rows


def load_rule_stats(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT system_api_id,
               SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_rule_count,
               COUNT(1) AS total_rule_count
        FROM system_api_billing_rules
        GROUP BY system_api_id
        """
    )
    counts = {
        int(r["system_api_id"]): {
            "active_rule_count": int(r["active_rule_count"] or 0),
            "total_rule_count": int(r["total_rule_count"] or 0),
        }
        for r in cur.fetchall()
    }

    cur.execute(
        """
        SELECT system_api_id, generation_mode
        FROM system_api_billing_rules
        WHERE is_active = 1
        """
    )
    active_modes = defaultdict(set)
    for r in cur.fetchall():
        api_id = int(r["system_api_id"])
        gm = _norm_slug(r["generation_mode"])
        active_modes[api_id].add(gm)

    return counts, active_modes


def score_match(candidate: dict, setting: dict) -> tuple[int, str]:
    score = 0
    reasons = []

    c_model = _norm(candidate["model_guess"])
    s_model = setting["model_norm"]

    if c_model and c_model == s_model:
        score += 100
        reasons.append("model_exact")
    elif c_model and (c_model in s_model or s_model in c_model):
        score += 60
        reasons.append("model_partial")

    c_category = _norm_slug(candidate["category"])
    s_category = _norm_slug(setting["category"])
    if c_category and s_category and c_category == s_category:
        score += 20
        reasons.append("category")

    c_out = _norm_slug(candidate["output_format"])
    if c_out and c_out == setting["output_format"]:
        score += 12
        reasons.append("output")

    c_in = _norm_slug(candidate["input_format"])
    if c_in and c_in in setting["input_formats"]:
        score += 8
        reasons.append("input")

    c_audio = parse_bool_or_blank(candidate["has_audio"])
    if c_audio and c_audio == setting["has_audio"]:
        score += 6
        reasons.append("audio")

    gm = gm_for_db_lookup(candidate["generation_mode_split"])
    gm_norm = _norm_slug(gm)
    if gm_norm and gm_norm in setting["generation_modes"]:
        score += 10
        reasons.append("gm")

    if setting["is_active"] == 1:
        score += 3
        reasons.append("active")

    return score, "+".join(reasons)


def choose_setting(candidate: dict, settings: list[dict]):
    best = None
    best_score = -1
    best_reason = ""
    for s in settings:
        score, reason = score_match(candidate, s)
        if score > best_score:
            best = s
            best_score = score
            best_reason = reason
        elif score == best_score and best is not None:
            # Tie-break: prefer active and then smaller id as canonical older entry.
            if s["is_active"] > best["is_active"]:
                best = s
                best_reason = reason
            elif s["is_active"] == best["is_active"] and s["id"] < best["id"]:
                best = s
                best_reason = reason

    if best_score < 40:
        return None, best_score, "no_confident_match"
    return best, best_score, best_reason


def gm_covered(gm_split: str, active_modes: set[str], active_count: int) -> bool:
    if active_count <= 0:
        return False
    if "" in active_modes:
        return True
    gm = _norm_slug(gm_for_db_lookup(gm_split))
    if not gm:
        return True
    return gm in active_modes


def to_markdown_table(rows: list[dict], headers: list[str]) -> str:
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        vals = []
        for h in headers:
            v = str(r.get(h, ""))
            v = v.replace("|", "\\|")
            vals.append(v)
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main():
    conn = sqlite3.connect(DB_PATH)
    settings = load_settings(conn)
    rule_counts, rule_active_modes = load_rule_stats(conn)

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        input_rows = list(reader)

    out_rows = []
    unmatched = []

    for row in input_rows:
        candidate = {
            "category": (row.get("category") or "").strip(),
            "title": (row.get("title") or "").strip(),
            "url": (row.get("url") or "").strip(),
            "generation_mode_original": (row.get("generation_mode") or "").strip(),
            "generation_mode_split": normalize_generation_mode(row.get("generation_mode") or ""),
            "input_format": (row.get("input_format") or "").strip(),
            "output_format": (row.get("output_format") or "").strip(),
            "has_audio": (row.get("has_audio") or "").strip(),
            "model_guess": extract_model_from_url(row.get("url") or ""),
            "resolution": (row.get("resolution") or "").strip(),
            "aspect_ratio": (row.get("aspect_ratio") or "").strip(),
            "mode": (row.get("mode") or "").strip(),
            "quality": (row.get("quality") or "").strip(),
            "source_sound": (row.get("source_sound") or "").strip(),
            "source_multi_shots": (row.get("source_multi_shots") or "").strip(),
        }

        matched, match_score, match_method = choose_setting(candidate, settings)

        if matched is None:
            api_id = ""
            api_model = ""
            api_name = ""
            api_active = ""
            active_rule_count = 0
            total_rule_count = 0
            active_rule_modes = ""
            gm_coverage = False
            unmatched.append(candidate)
        else:
            api_id = matched["id"]
            api_model = matched["model"]
            api_name = matched["name"]
            api_active = matched["is_active"]
            count = rule_counts.get(api_id, {"active_rule_count": 0, "total_rule_count": 0})
            active_rule_count = count["active_rule_count"]
            total_rule_count = count["total_rule_count"]
            mode_set = rule_active_modes.get(api_id, set())
            active_rule_modes = ",".join(sorted(m for m in mode_set if m))
            gm_coverage = gm_covered(candidate["generation_mode_split"], mode_set, active_rule_count)

        out_rows.append(
            {
                "category": candidate["category"],
                "title": candidate["title"],
                "url": candidate["url"],
                "generation_mode_original": candidate["generation_mode_original"],
                "generation_mode_split": candidate["generation_mode_split"],
                "input_format": candidate["input_format"],
                "output_format": candidate["output_format"],
                "has_audio": candidate["has_audio"],
                "model_guess": candidate["model_guess"],
                "matched_system_api_id": api_id,
                "matched_system_api_model": api_model,
                "matched_system_api_name": api_name,
                "matched_system_api_active": api_active,
                "match_score": match_score,
                "match_method": match_method,
                "active_rule_count": active_rule_count,
                "total_rule_count": total_rule_count,
                "active_rule_modes": active_rule_modes,
                "gm_covered_by_active_rules": "true" if gm_coverage else "false",
                "resolution": candidate["resolution"],
                "aspect_ratio": candidate["aspect_ratio"],
                "mode": candidate["mode"],
                "quality": candidate["quality"],
                "source_sound": candidate["source_sound"],
                "source_multi_shots": candidate["source_multi_shots"],
            }
        )

    headers = list(out_rows[0].keys()) if out_rows else []
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(out_rows)

    total = len(out_rows)
    matched_count = sum(1 for r in out_rows if r["matched_system_api_id"] != "")
    active_matched = sum(1 for r in out_rows if str(r["matched_system_api_active"]) == "1")
    with_active_rules = sum(1 for r in out_rows if int(r["active_rule_count"]) > 0)
    gm_covered_count = sum(1 for r in out_rows if r["gm_covered_by_active_rules"] == "true")

    split_counter = Counter(r["generation_mode_split"] for r in out_rows)
    unmatched_counter = Counter(r["category"] for r in unmatched)

    top_unmatched = sorted(unmatched, key=lambda r: (r["category"], r["title"]))[:25]

    summary_lines = []
    summary_lines.append("# KIE Billing Candidates x System API Integration")
    summary_lines.append("")
    summary_lines.append(f"- Source candidates: **{total}**")
    summary_lines.append(f"- Matched to `system_api_settings` (provider=kie): **{matched_count}**")
    summary_lines.append(f"- Matched and active settings: **{active_matched}**")
    summary_lines.append(f"- Matched with active billing rules: **{with_active_rules}**")
    summary_lines.append(f"- Generation mode covered by active rules: **{gm_covered_count}**")
    summary_lines.append("")
    summary_lines.append("## Generation Mode Split")
    summary_lines.append("")
    for gm, cnt in sorted(split_counter.items()):
        summary_lines.append(f"- `{gm or '(blank)'}`: {cnt}")
    summary_lines.append("")
    summary_lines.append("## Unmatched by Category")
    summary_lines.append("")
    for cat, cnt in sorted(unmatched_counter.items()):
        summary_lines.append(f"- `{cat or '(blank)'}`: {cnt}")

    if top_unmatched:
        summary_lines.append("")
        summary_lines.append("## Top Unmatched Rows (first 25)")
        summary_lines.append("")
        headers_unmatched = [
            "category",
            "title",
            "url",
            "generation_mode_split",
            "output_format",
            "model_guess",
        ]
        summary_lines.append(to_markdown_table(top_unmatched, headers_unmatched))

    OUT_MD.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"WROTE {OUT_CSV}")
    print(f"WROTE {OUT_MD}")
    print(
        "SUMMARY total={total} matched={matched} active_matched={active} with_active_rules={rules} gm_covered={gm}".format(
            total=total,
            matched=matched_count,
            active=active_matched,
            rules=with_active_rules,
            gm=gm_covered_count,
        )
    )


if __name__ == "__main__":
    main()
