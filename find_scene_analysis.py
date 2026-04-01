import re

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    content = f.read()

# I want to find the JSX for Scene Analysis which starts with a button or a div handling isCreateSceneAnalysisCollapsed
# and the entire !isCreateSceneAnalysisCollapsed && block.
import re

scene_analysis_pattern = r"""\s*<div className="mt-4 border-t border-white/10 pt-3">\s*<button.*?onClick=\{\(\) => setIsCreateSceneAnalysisCollapsed\(!isCreateSceneAnalysisCollapsed\)\}.*?</button>\s*</div>\s*\{!isCreateSceneAnalysisCollapsed && \([\s\S]*?</div>\s*\)\}"""

# Wait, what exactly does the scene analysis string look like? I'll just print out a slice.
match = re.search(r'(<div[^>]*>.*?isCreateSceneAnalysisCollapsed.*?</div>\s*<div[^>]*>.*?\{!isCreateSceneAnalysisCollapsed &&)', content, re.DOTALL)
if match:
    print(match.group(1)[:500])
else:
    print("Not found with this simple regex. Let me do a flexible search.")
