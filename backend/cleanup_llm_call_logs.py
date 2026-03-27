from pathlib import Path


def main() -> int:
    logs_dir = Path(__file__).resolve().parent / "logs"
    if not logs_dir.exists() or not logs_dir.is_dir():
        print("[boot] cleanup_llm_call_logs: logs dir not found, skip")
        return 0

    removed = 0
    failed = 0
    for p in sorted(logs_dir.glob("llm_calls.log*")):
        try:
            if p.is_file():
                p.unlink(missing_ok=True)
                removed += 1
        except Exception as exc:
            failed += 1
            print(f"[boot][WARN] cleanup_llm_call_logs failed for {p.name}: {exc}")

    print(f"[boot] cleanup_llm_call_logs done removed={removed} failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
