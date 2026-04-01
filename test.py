import sys

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

def remove_block(text, keyword):
    idx = text.find(keyword)
    if idx == -1: return text
    
    start_tag = '<div className="mt-5 rounded-xl border border-white/10 bg-black/15">'
    start_idx = text.rfind(start_tag, 0, idx)
    if start_idx == -1:
        # maybe another layout?
        start_tag = '<div className="mt-4 pt-3 border-t border-white/10">'
        start_idx = text.rfind(start_tag, 0, idx)
        
    if start_idx == -1:
        print(f"Could not find start tag for {keyword}")
        return text

    # Count divs from start_idx
    i = start_idx
    div_count = 0
    in_block = True
    while i < len(text) and in_block:
        tag_start = text.find('<', i)
        if tag_start == -1: break
        
        if text[tag_start:tag_start+5] == '<div ' or text[tag_start:tag_start+5] == '<div>':
            div_count += 1
            i = tag_start + 4
        elif text[tag_start:tag_start+6] == '</div>':
            div_count -= 1
            i = tag_start + 6
            if div_count == 0:
                end_idx = i
                break
        else:
            i = tag_start + 1

    if div_count == 0:
        return text[:start_idx] + text[end_idx:]
    else:
        print(f"Could not balance divs for {keyword}")
        return text

# We want to remove the scene analysis and collaborators old blocks.
# Let's check how many time "isCreateSceneAnalysisCollapsed" exists.
t1 = remove_block(text, "SceneAnalysisCollapsed((prev)")
if t1 != text:
    print("Removed Scene Analysis block")
    
t2 = remove_block(t1, "CollaboratorsCollapsed((prev)")
if t2 != t1:
    print("Removed Collaborators block")
    
with open("test_out.jsx", "w", encoding="utf-8") as f:
    f.write(t2)

