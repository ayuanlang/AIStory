import re

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

# The string block to extract:
extract_block = r"""                                        <label className="block text-sm font-semibold tracking-wide text-primary mt-4 mb-2">\{t\('项目描述（可选）', 'Project Description \(Optional\)'\)\}</label>\s*<textarea\s*className="w-full px-4 py-2\.5 bg-background border border-white/15 rounded-lg focus:ring-2 focus:ring-primary/30 focus:border-primary/50 outline-none resize-y min-h-\[84px\]"\s*value=\{newDescription\}\s*onChange=\{e => setNewDescription\(e\.target\.value\)\}\s*placeholder=\{t\('可留空。用于记录项目背景、目标或备注', 'Can be left empty\. Add context, goals, or notes for this project'\)\}\s*/>\s*<label className="block text-sm font-semibold tracking-wide text-primary mt-4 mb-2">\{t\('剧本内容（可选）', 'Script Content \(Optional\)'\)\}</label>\s*<textarea\s*className="w-full px-4 py-2\.5 bg-background border border-white/15 rounded-lg focus:ring-2 focus:ring-primary/30 focus:border-primary/50 outline-none resize-y min-h-\[120px\]"\s*value=\{newScriptText\}\s*onChange=\{e => setNewScriptText\(e\.target\.value\)\}\s*placeholder=\{t\('输入剧本内容，创建项目后将自动生成第一集并导入此内容', 'Enter script content\.\.\.'\)\}\s*/>\s*"""

match = re.search(extract_block, text)
if not match:
    print("Could not find the textareas.")
    exit(1)

extracted_text = match.group(0)

# Remove it from the original place
text = text.replace(extracted_text, "")

# Find the insertion point: immediately before the collaboration block
insert_target = """                                        </label>

                                        <div className="mb-6 pb-3 mt-4 border-t border-white/10 pt-6">
                                            <button onClick={() => setIsCreateCollaboratorsCollapsed(!isCreateCollaboratorsCollapsed)}"""

final_text = text.replace(insert_target, extracted_text + "\n" + insert_target)

with open("frontend/src/pages/ProjectList.jsx", "w", encoding="utf-8") as f:
    f.write(final_text)

print("Done moving Script Content and Project Description.")
