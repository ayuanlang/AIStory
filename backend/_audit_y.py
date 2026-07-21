from pathlib import Path
import re

# Map schema class blocks in workspace episodes/scenes/shots
for name in ["episodes", "scenes", "shots"]:
    p = Path(f"app/api/routers/workspace/{name}.py")
    lines = p.read_text(encoding="utf-8").splitlines()
    print(f"\n===== {name} =====")
    classes = []
    for i,l in enumerate(lines,1):
        if l.startswith("class ") and "BaseModel" in l:
            classes.append((i,l[:90]))
        if l.startswith("@router.") and classes:
            break
    for i,l in classes:
        print(f"{i:5} {l}")
    # also show first route line
    for i,l in enumerate(lines,1):
        if l.startswith("@router."):
            print(f"first route {i}")
            break

# billing helper dependency chain in generation/shared around the functions we need
gs = Path("app/api/routers/generation/shared.py").read_text(encoding="utf-8")
for name in [
    "_extract_llm_routing_metadata",
    "_apply_llm_routing_to_billing_details",
    "_attach_llm_provider_usage_to_billing_details",
    "_safe_int_token",
    "_resolve_usage_token_total",
    "_build_standard_billing_details",
    "_reservation_tx_id",
    "_finalize_model_invocation_billing",
    "_cancel_reservation_quietly",
]:
    m = re.search(rf"^def {name}\(", gs, re.M)
    print(name, "line", gs[:m.start()].count("\n")+1 if m else "MISSING")