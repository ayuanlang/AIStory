import re

jsx_path = r"c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx"
with open(jsx_path, 'r', encoding='utf-8') as f:
    content = f.read()

buggy_regex = r"const dashMatch = authoritativeSubjectText\.match\(/-\{5,\}\\s\*\\n\(\[\\s\\S\]\*\?\)\\n\\s\*\-\{5,\}/\);[\s\S]*?if \(\!subjectIndexText\.trim\(\)\) \{"

fixed_block = """const dashMatch = authoritativeSubjectText.match(/-{5,}\\s*\\n([\\s\\S]*?)\\n\\s*-{5,}/);
        if (dashMatch && dashMatch[1].trim()) {
            subjectIndexText = dashMatch[1].trim();
            onLog?.(`[Asset Gen Tracking] Extracted Subject Index wrapped by dashes (length: ${subjectIndexText.length})`);
        } else {
            // Fallback to header matching if dashes are not found
            const match = authoritativeSubjectText.match(/(?:###?|##)\\s*(?:Subject Index|角色|道具|场景|设计资产|Entities)[\\s\\S]*/i);
            if (match) {
                subjectIndexText = match[0].trim();
                onLog?.(`[Asset Gen Tracking] Extracted Subject Index via header (length: ${subjectIndexText.length})`);
            } else {
                subjectIndexText = authoritativeSubjectText.trim();
                onLog?.(`[Asset Gen Tracking] Failed to find Subject Index header or dashes! Using fallback full text for asset generation.`, 'warning');    
            }
        }

        // Phase 2 Preparation: Save extracted subjectIndexText to episode and set UI state
        if (subjectIndexText.trim()) {
            setSubjectIndexText(subjectIndexText);
            try {
                await updateEpisode(activeEpisode.id, {
                    ai_scene_analysis_subject_index: subjectIndexText
                });
                onLog?.(`[Phase 2] Saved ai_scene_analysis_subject_index (length: ${subjectIndexText.length})`);
            } catch (error) {
                onLog?.(`[Phase 2] Warning: Failed to save subject index to episode: ${error.message}`);
            }
        }

        if (!subjectIndexText.trim()) {"""

parsed = re.sub(buggy_regex, fixed_block, content, count=1)
if parsed == content:
    print("Failed to replace buggy bracket logic!")
else:
    print("Replaced bracket logic.")
    content = parsed

new_hook = r"""
    useEffect(() => {
        if (isEditingSubjectIndex) return;

        const authoritativeText = llmRawResultContent || activeEpisode?.ai_scene_analysis_result || '';
        if (!authoritativeText) return;

        let extracted = '';
        const dashMatch = authoritativeText.match(/-{5,}\s*\n([\s\S]*?)\n\s*-{5,}/);
        if (dashMatch && dashMatch[1].trim()) {
            extracted = dashMatch[1].trim();
        } else {
            const match = authoritativeText.match(/(?:###?|##)\s*(?:Subject Index|角色|道具|场景|设计资产|Entities)[\s\S]*/i);
            if (match) {
                extracted = match[0].trim();
            } else {
                extracted = authoritativeText.trim();
            }
        }

        if (extracted && extracted !== subjectIndexText && extracted.length > 5) {
            setSubjectIndexText(extracted);
            if (activeEpisode?.id && extracted !== activeEpisode.ai_scene_analysis_subject_index) {
                updateEpisode(activeEpisode.id, { ai_scene_analysis_subject_index: extracted }).catch(() => {});
            }
        }
    }, [llmRawResultContent, activeEpisode?.ai_scene_analysis_result, activeEpisode?.id, isEditingSubjectIndex, subjectIndexText, updateEpisode]);
"""

hook_regex = r"(useEffect\(\(\) => \{\s*isSuperuserRef\.current = isSuperuser;\s*\}, \[isSuperuser\]\);)"
parsed2 = re.sub(hook_regex, r"\1" + new_hook, content, count=1)

if parsed2 == content:
    print("Failed to insert new hook!")
else:
    print("Inserted new hook.")
    content = parsed2

with open(jsx_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
