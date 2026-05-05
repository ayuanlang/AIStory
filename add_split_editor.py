import re
file_path = 'frontend/src/pages/editor/components/ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_str = """        if (isAnalyzing || analysisRunInFlightRef?.current || analysisResumeInFlightRef?.current) {
            onLog?.("Already analyzing, duplicate click prevented.");
            return;
        }"""

new_str = """        if (isAnalyzing || analysisRunInFlightRef?.current || analysisResumeInFlightRef?.current) {
            onLog?.("Already analyzing, duplicate click prevented.");
            return;
        }

        if (rawContent && rawContent.trim().length > 2500) {
            const ok = window.confirm(t(
                '检测到剧本内容超过2500字，考虑到大模型可能漏剧情，建议先进行分集处理。是否允许AI帮您自动切分集并保存？(选择“取消”则忽略并继续分析整段内容)',
                'Script length exceeds 2500 characters. Large models might miss plot details. Auto-split it into episodes? (Cancel to proceed analyzing as a whole)'
            ));
            if (ok) {
                if (onLog) onLog("开始调用剧本分隔提示词自动分集...");
                try {
                    const { splitEpisodeScript } = await import('../../../services/api');
                    await splitEpisodeScript(projectId, activeEpisode.id, { script_content: rawContent });
                    if (onLog) onLog("分集保存成功，即将刷新！");
                    window.location.reload();
                } catch (e) {
                    console.error("Script split failed", e);
                    alert("分集失败: " + e.message);
                }
                return;
            }
        }"""

if old_str in content:
    content = content.replace(old_str, new_str)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced!")
else:
    print("Not found!")
