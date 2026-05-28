import sys

file_path = r"c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

click_old = """    const handleAnalysisClick = async () => {
        if (!rawContent || rawContent.trim().length < 10) {
            alert("Script content is too short for analysis.");
            return;
        }"""
click_new = """    const handleAnalysisClick = async () => {
        const actualContent = getCurrentScriptContent();
        if (!actualContent || actualContent.trim().length < 10) {
            alert("Script content is too short for analysis.");
            return;
        }"""
text = text.replace(click_old, click_new)

body_old = """        if (rawContent && rawContent.trim().length > 2500) {
            const ok = window.confirm(t("""
body_new = """        if (actualContent && actualContent.trim().length > 2500) {
            const ok = window.confirm(t("""
text = text.replace(body_old, body_new)

text = text.replace("await splitEpisodeScript(projectId, activeEpisode.id, { script_content: rawContent });", "await splitEpisodeScript(projectId, activeEpisode.id, { script_content: actualContent });")

body2_old = """        if (rawContent && rawContent.trim().length > 2500) {
            const ok = await confirmUiMessage(t("""
body2_new = """        if (actualContent && actualContent.trim().length > 2500) {
            const ok = await confirmUiMessage(t("""
text = text.replace(body2_old, body2_new)

text = text.replace("const stage1Input = ensureStage1ProjectContextInjected(rawContent);", "const stage1Input = ensureStage1ProjectContextInjected(actualContent);")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("done")
