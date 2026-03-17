import argparse
import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.edge.options import Options

from _extract_runninghub_standard_openapi import ROOT, _derive_api_id, _load_index_text, _safe_slug, parse_llms_index


def _resolve_output_dir(path_value: str) -> Path:
    output_dir = Path(path_value)
    if not output_dir.is_absolute():
        output_dir = (ROOT / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _build_output_path(output_dir: Path, url: str, title: str) -> Path:
    api_id = _derive_api_id(url)
    title_slug = _safe_slug(title)
    stem = api_id or title_slug or "runninghub-page"
    return output_dir / f"{stem}.html"


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture browser-rendered RunningHub detail pages into a local cache directory")
    parser.add_argument("--index-file", required=True, help="Local llms-style index file")
    parser.add_argument("--out-dir", required=True, help="Directory to write rendered HTML pages")
    parser.add_argument("--category", default="", help="Optional category filter")
    parser.add_argument("--service-tier", default="", help="Optional service tier filter")
    parser.add_argument("--limit", type=int, default=0, help="Optional capture limit")
    parser.add_argument("--wait-seconds", type=int, default=8, help="Seconds to wait for page render")
    args = parser.parse_args()

    entries = parse_llms_index(_load_index_text(args.index_file))
    if args.category:
        category_filter = args.category.strip().lower()
        entries = [entry for entry in entries if entry.category.lower() == category_filter]
    if args.service_tier:
        service_tier_filter = args.service_tier.strip().lower()
        entries = [entry for entry in entries if entry.service_tier.lower() == service_tier_filter]
    if args.limit and args.limit > 0:
        entries = entries[: args.limit]

    output_dir = _resolve_output_dir(args.out_dir)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    manifest = []
    driver = webdriver.Edge(options=options)
    try:
        for index, entry in enumerate(entries, start=1):
            output_path = _build_output_path(output_dir, entry.url, entry.title)
            print(f"[{index}/{len(entries)}] capturing {entry.title}")
            driver.get(entry.url)
            time.sleep(max(1, args.wait_seconds))
            rendered_html = driver.execute_script("return document.documentElement.outerHTML") or ""
            output_path.write_text(rendered_html, encoding="utf-8")
            manifest.append(
                {
                    "title": entry.title,
                    "doc_url": entry.url,
                    "service_tier": entry.service_tier,
                    "category": entry.category,
                    "path": str(output_path),
                }
            )
    finally:
        driver.quit()

    manifest_path = output_dir / "capture_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {manifest_path}")


if __name__ == "__main__":
    main()