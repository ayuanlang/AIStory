import re

path = r"c:\AS\AIStory\frontend\src\pages\Editor.jsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# We need to replace the check logic
for t in ["character", "prop", "environment", "poster", "cover"]:
    old_logic = f"""                            if (existingEntityMap.has(normalizeEntityKey('{t}', entityName)) || (entityNameEn && existingEntityMap.has(normalizeEntityKey('{t}', entityNameEn)))) {{
                                logSkippedExistingSubject('{t}', entityName, entityNameEn);
                                continue;
                            }}"""
    
    new_logic = f"""                            const existingForName = existingEntityMap.get(normalizeEntityKey('{t}', entityName)) || (entityNameEn ? existingEntityMap.get(normalizeEntityKey('{t}', entityNameEn)) : null);
                            if (existingForName) {{
                                if (String(existingForName.episode_id) === String(activeEpisode?.id)) {{
                                    logSkippedExistingSubject('{t}', entityName, entityNameEn);
                                    continue;
                                }} else {{
                                    char.visual_dependencies = Array.isArray(char.visual_dependencies) ? char.visual_dependencies : (typeof char.visual_dependencies === 'string' ? [char.visual_dependencies] : []);
                                    // Use format expected by the backend/prompts
                                    char.visual_dependencies.push(`existing_id:${{existingForName.id}}`);
                                }}
                            }}"""
    
    # Needs a bit of customization for the loop variable which is char, prop, env, or poster
    var_name = {"character": "char", "prop": "prop", "environment": "env", "poster": "poster", "cover": "poster"}[t]
    
    mod_new_logic = new_logic.replace("char.visual_dependencies", f"{var_name}.visual_dependencies")
    
    content = content.replace(old_logic, mod_new_logic)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("done")
