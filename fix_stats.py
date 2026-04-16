import re

content = open("c:\\AS\\AIStory\\frontend\\src\\pages\\editor\\components\\ScriptEditor.jsx", "r", encoding="utf-8").read()

new_block1 = """                importReport = {
                    ...importReport,
                    sceneSubjectPostImportReport: postImportSceneSubjectReport,
                };
                if (postImportSceneSubjectReport?.importedSubjectCounts) {
                    importReport.importedSubjectCounts = {
                        character: (importReport.importedSubjectCounts?.character || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.character) || 0),
                        prop: (importReport.importedSubjectCounts?.prop || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.prop) || 0),
                        environment: (importReport.importedSubjectCounts?.environment || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.environment) || 0),
                    };
                }"""

content = re.sub(
    r'                importReport = \{\s*\.\.\.importReport,\s*sceneSubjectPostImportReport: postImportSceneSubjectReport,\s*\};',
    new_block1,
    content
)

new_block2 = """                const newImportReport = {
                    ...analysisUiReport.importReport,
                    sceneSubjectPostImportReport: postImportSceneSubjectReport,
                };
                if (postImportSceneSubjectReport?.importedSubjectCounts) {
                    newImportReport.importedSubjectCounts = {
                        character: (newImportReport.importedSubjectCounts?.character || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.character) || 0),
                        prop: (newImportReport.importedSubjectCounts?.prop || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.prop) || 0),
                        environment: (newImportReport.importedSubjectCounts?.environment || 0) + (Number(postImportSceneSubjectReport.importedSubjectCounts.environment) || 0),
                    };
                }"""

content = re.sub(
    r'                const newImportReport = \{\s*\.\.\.analysisUiReport\.importReport,\s*sceneSubjectPostImportReport: postImportSceneSubjectReport,\s*\};',
    new_block2,
    content
)

open("c:\\AS\\AIStory\\frontend\\src\\pages\\editor\\components\\ScriptEditor.jsx", "w", encoding="utf-8").write(content)
print("done")
