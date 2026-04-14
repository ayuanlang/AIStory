#!/usr/bin/env python3

import re
import sys

FILE_PATH = r"c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx"

def read_file():
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(content):
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

def patch_add_useState_hooks(content):
    pattern = r"(    const \[showAnalysisModal, setShowAnalysisModal\] = useState\(false\);)"
    replacement = r"""\1
    const [subjectIndexText, setSubjectIndexText] = useState('');
    const [isEditingSubjectIndex, setIsEditingSubjectIndex] = useState(false);
    const [isRetryingPhase2, setIsRetryingPhase2] = useState(false);"""
    
    new_content = re.sub(pattern, replacement, content)
    if new_content == content:
        print("ERROR: Could not find setShowAnalysisModal line to add useState hooks")
        return None
    return new_content

def patch_save_subject_index_after_extraction(content):
    pattern = r"(        \} else \{\s+subjectIndexText = authoritativeSubjectText;\s+onLog\?\.\(`\[Asset Gen Tracking\] Failed to find Subject Index header or dashes!.*?\`, 'warning'\);\s+\})"
    
    save_logic = r"""\1

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
        }"""
    
    new_content = re.sub(pattern, save_logic, content, flags=re.DOTALL)
    if new_content == content:
        print("ERROR: Could not find subject index extraction block for adding save logic")
        return None
    return new_content

def main():
    content = read_file()
    if not content: return False
    
    content = patch_add_useState_hooks(content)
    if content is None: return False
    
    content = patch_save_subject_index_after_extraction(content)
    if content is None: return False
    
    write_file(content)
    print("Patched successfully")
    return True

if __name__ == '__main__':
    sys.exit(0 if main() else 1)