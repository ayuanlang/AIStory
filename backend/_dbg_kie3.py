import sqlite3, json
conn=sqlite3.connect(r"c:\AS\AIStory\backend\aistory.db")
conn.row_factory=sqlite3.Row
cur=conn.cursor()
for api_id in (364,1085,1105):
    print("==== API", api_id)
    api=dict(cur.execute("SELECT id,provider,model,name,config FROM system_api_settings WHERE id=?", (api_id,)).fetchone())
    cfg=api.get("config")
    if isinstance(cfg,str):
        try: cfg=json.loads(cfg)
        except: pass
    print("provider/model", api["provider"], api["model"])
    print("config keys", list(cfg.keys()) if isinstance(cfg,dict) else type(cfg))
    rules=cur.execute("SELECT id,name,is_active,priority,billing_unit_type,billing_cost,billing_cost_input,billing_cost_output,charge_multiplier,supplier_price,supplier_price_input,supplier_price_output,extra_conditions,width_min,width_max,height_min,height_max,duration_seconds_min,duration_seconds_max,has_audio,generation_mode FROM system_api_billing_rules WHERE system_api_id=? ORDER BY id", (api_id,)).fetchall()
    for r in rules:
        d=dict(r)
        extra=d.pop("extra_conditions")
        if isinstance(extra,str):
            try: extra=json.loads(extra)
            except: pass
        print("--- rule", d["id"], d["name"], "active", d["is_active"], "unit", d["billing_unit_type"], "cost", d["billing_cost"], "supplier", d["supplier_price"], "mul", d["charge_multiplier"])
        print(" dims", {k:d[k] for k in ("width_min","width_max","height_min","height_max","duration_seconds_min","duration_seconds_max","has_audio","generation_mode")})
        if isinstance(extra,dict) and extra:
            print(" extra", json.dumps(extra, ensure_ascii=False)[:800])
# matrix anywhere
hits=0
for r in cur.execute("SELECT id, system_api_id, name, billing_unit_type, is_active, extra_conditions FROM system_api_billing_rules"):
    text=str(r["extra_conditions"] or "")
    if "video_second" in text:
        hits+=1
        if hits<=30:
            print("HIT", r["id"], r["system_api_id"], r["name"], r["billing_unit_type"], r["is_active"], text[:200])
print("hits", hits)
