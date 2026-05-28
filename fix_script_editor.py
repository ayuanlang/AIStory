import re

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix 1: autoSaveScriptBeforeAnalysis wait
orig1 = """    const autoSaveScriptBeforeAnalysis = async () => {
        if (!activeEpisode?.id || typeof onUpdateScript !== 'function') return;
        const latestScript = String(getCurrentScriptContent() || '');
        const savedScript = String(activeEpisode?.script_content || '');"""

new1 = """    const autoSaveScriptBeforeAnalysis = async () => {
        if (!activeEpisode?.id || typeof onUpdateScript !== 'function') return;
        
        let latestScript = String(getCurrentScriptContent() || '');
        if (!latestScript.trim() && rawContent.trim()) {
            latestScript = rawContent;
        }

        const savedScript = String(activeEpisode?.script_content || '');"""

text = text.replace(orig1, new1)

# Fix 2: useEffect text clearing guard
orig2 = """    useEffect(() => {
        if (activeEpisode?.script_content) {
            setRawContent(activeEpisode.script_content);
        } else {
            setRawContent('');
        }"""

new2 = """    useEffect(() => {
        if (activeEpisode?.script_content) {
            setRawContent(activeEpisode.script_content);
        } else {
            // Guard: Do not wipe if user has typed something and backend returned empty by mistake
            if (!rawContent) {
                setRawContent('');
            } else {
                console.warn("[ScriptEditor] activeEpisode has no script_content, but rawContent exists. Ignoring clear.");
            }
        }"""

text = text.replace(orig2, new2)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Applied ScriptEditor fixes.")
