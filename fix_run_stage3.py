import re

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace in runStage3Task in both executeAdvancedAnalysis and handleRestartStage2

replacement1 = """                const runStage3Task = async () => {
                    try {
                        return await runPostImportSceneSubjectPipeline(null, globalStage2_1Text || stage2_1Text, {
                            explicitSubjectIndexText: globalStage2_1Text || stage2_1Text
                        });
                    } catch (e) {"""

# Replace in executeAdvancedAnalysis
text = re.sub(
    r"const runStage3Task = async \(\) => \{\s*if \(!autoStartSubjectAnalysis\) return null;\s*try \{\s*return await runPostImportSceneSubjectPipeline\(null, null, \{\s*explicitSubjectIndexText: globalStage2_1Text \|\| stage2_1Text\s*\}\);\s*\} catch \(e\) \{",
    replacement1,
    text
)

# And in handleRestartStage2 it was written like this:
replacement2 = """            const runStage3Task = async () => {
                try {
                    return await runPostImportSceneSubjectPipeline(null, globalStage2_1Text || stage2_1Text, {
                        explicitSubjectIndexText: globalStage2_1Text || stage2_1Text
                    });
                } catch (e) {"""

text = re.sub(
    r"const runStage3Task = async \(\) => \{\s*try \{\s*return await runPostImportSceneSubjectPipeline\(null, null, \{\s*explicitSubjectIndexText: globalStage2_1Text \|\| stage2_1Text\s*\}\);\s*\} catch \(e\) \{",
    replacement2,
    text
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated runStage3Task.")
