import re

with open('frontend/src/pages/editor/components/SceneManager.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    "export const SceneManager = ({ activeEpisode, projectId, project, onLog, onImportText, onSwitchToShots, uiLang = 'zh' }) => {",
    "export const SceneManager = ({ activeEpisode, projectId, project, onLog, onImportText, onSwitchToShots, uiLang = 'zh' }) => {\n    const functionApiConfigs = useFunctionApis();"
)

text = text.replace(
    '<div className="flex gap-2">\n                    <button\n                        onClick={runBatchGenerateAiShotsForAllScenes}',
    '<div className="flex gap-2 items-center">\n                    <FunctionApiSelector functionName="ai_shot" configs={functionApiConfigs} />\n                    <button\n                        onClick={runBatchGenerateAiShotsForAllScenes}'
)

text = text.replace(
    '<button onClick={handleGenerateShots} className="px-6 py-2 bg-blue-600 text-white rounded-lg flex items-center gap-2 hover:bg-blue-700 disabled:opacity-50" disabled={shotPromptModal.loading}>',
    '<FunctionApiSelector functionName="ai_shot" configs={functionApiConfigs} />\n                                <button onClick={handleGenerateShots} className="px-6 py-2 bg-blue-600 text-white rounded-lg flex items-center gap-2 hover:bg-blue-700 disabled:opacity-50" disabled={shotPromptModal.loading}>'
)

text = text.replace(
    '<button onClick={handleShotRegenSubmit} disabled={shotRegenModal.submitting}\n                                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium">',
    '<FunctionApiSelector functionName="ai_shot" configs={functionApiConfigs} />\n                            <button onClick={handleShotRegenSubmit} disabled={shotRegenModal.submitting}\n                                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium">'
)

with open('frontend/src/pages/editor/components/SceneManager.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Patched SceneManager")
