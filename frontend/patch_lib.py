import re
with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

import_statement = "import { generateEntityFromText, generateEntityFromImage, generateEntityDerived } from '../../../services/api';"
if "generateEntityFromText" not in text:
    text = text.replace("import { \n    fetchProject,", import_statement + "\nimport { \n    fetchProject,")

pattern = re.compile(r'const handleGenerateEntityFromText = async \(textDesc\) => \{[^\}]*\};', re.MULTILINE | re.DOTALL)
replacement = '''    const handleGenerateEntityFromText = async (textDesc) => {
        try {
            setIsGeneratingRow(true);
            await generateEntityFromText(projectId, textDesc, functionApiConfigs?.script_analysis);
            await loadAssets();
            setShowAiEntityCreateModal(false);
        } catch (e) {
            console.error(e);
            alert("生成失败: " + String(e));
        } finally {
            setIsGeneratingRow(false);
        }
    };'''
text = pattern.sub(replacement, text)

pattern = re.compile(r'const handleGenerateEntityFromImage = async \(imageFile\) => \{[^\}]*\};', re.MULTILINE | re.DOTALL)
replacement = '''    const handleGenerateEntityFromImage = async (imageFile) => {
        try {
            setIsGeneratingRow(true);
            await generateEntityFromImage(projectId, imageFile, functionApiConfigs?.vision_analysis);
            await loadAssets();
            setShowAiEntityCreateModal(false);
        } catch (e) {
            console.error(e);
            alert("生成失败: " + String(e));
        } finally {
            setIsGeneratingRow(false);
        }
    };'''
text = pattern.sub(replacement, text)

pattern = re.compile(r'const handleGenerateDerivedEntity = async \(baseEntityId, textDesc\) => \{[^\}]*\};', re.MULTILINE | re.DOTALL)
replacement = '''    const handleGenerateDerivedEntity = async (baseEntityId, textDesc) => {
        try {
            setIsGeneratingRow(true);
            await generateEntityDerived(projectId, baseEntityId, textDesc, functionApiConfigs?.script_analysis);
            await loadAssets();
            setShowAiEntityCreateModal(false);
        } catch (e) {
            console.error(e);
            alert("生成失败: " + String(e));
        } finally {
            setIsGeneratingRow(false);
        }
    };'''
text = pattern.sub(replacement, text)

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Patched SubjectLibrary.jsx")
