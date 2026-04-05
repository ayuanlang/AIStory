import re

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

# We need to insert the textareas back just before the collaboration block.
collaboration_marker = r'<div className="mb-6 pb-3 mt-4 border-t border-white/10 pt-6">\s*<button onClick=\{\(\) => setIsCreateCollaboratorsCollapsed\(!isCreateCollaboratorsCollapsed\)\}'

textareas_to_insert = """                                        <label className="block text-sm font-semibold tracking-wide text-primary mt-4 mb-2">{t('项目描述（可选）', 'Project Description (Optional)')}</label>
                                        <textarea
                                            className="w-full px-4 py-2.5 bg-background border border-white/15 rounded-lg focus:ring-2 focus:ring-primary/30 focus:border-primary/50 outline-none resize-y min-h-[84px]"
                                            value={newDescription}
                                            onChange={e => setNewDescription(e.target.value)}
                                            placeholder={t('可留空。用于记录项目背景、目标或备注', 'Can be left empty. Add context, goals, or notes for this project')}
                                        />
                                        <label className="block text-sm font-semibold tracking-wide text-primary mt-4 mb-2">{t('剧本内容（可选）', 'Script Content (Optional)')}</label>
                                        <textarea
                                            className="w-full px-4 py-2.5 bg-background border border-white/15 rounded-lg focus:ring-2 focus:ring-primary/30 focus:border-primary/50 outline-none resize-y min-h-[120px]"
                                            value={newScriptText}
                                            onChange={e => setNewScriptText(e.target.value)}
                                            placeholder={t('输入剧本内容，创建项目后将自动生成第一集并导入此内容', 'Enter script content...')}
                                        />

                                        <div className="mb-6 pb-3 mt-4 border-t border-white/10 pt-6">
                                            <button onClick={() => setIsCreateCollaboratorsCollapsed(!isCreateCollaboratorsCollapsed)}"""

new_text = re.sub(collaboration_marker, textareas_to_insert, text)

with open("frontend/src/pages/ProjectList.jsx", "w", encoding="utf-8") as f:
    f.write(new_text)

print("Restored textareas correctly.")
