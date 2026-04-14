import symtable

with open("app/api/endpoints.py", "r", encoding="utf-8") as f:
    text = f.read()

st = symtable.symtable(text, "endpoints.py", "exec")
for child in st.get_children():
    if child.get_name() == "analyze_scene":
        print("analyze_scene variables:")
        for sym in child.get_symbols():
            if sym.get_name() == "re":
                print(f"  re is local: {sym.is_local()}")
                print(f"  re is global: {sym.is_global()}")
                print(f"  re is free: {sym.is_free()}")
                print(f"  re is assigned: {sym.is_assigned()}")
                print(f"  re is imported: {sym.is_imported()}")
        for sub in child.get_children():
            if sub.get_name() == "_detect_scene_output_sections":
                print("  _detect_scene_output_sections variables:")
                for s in sub.get_symbols():
                    if s.get_name() == "re":
                        print(f"    re is local: {s.is_local()}")
                        print(f"    re is free: {s.is_free()}")
                        print(f"    re is global: {s.is_global()}")
