const fs = require('fs');
const file = 'c:\\AIStory\\frontend\\src\\pages\\editor\\components\\ScriptEditor.jsx';
let content = fs.readFileSync(file, 'utf8');

const anchor = 'if (importReport && typeof importReport === \\'object\\') {\\n                importReport = {\\n                    ...importReport,\\n                    sceneSubjectPostImportReport: postImportSceneSubjectReport,\\n                };\\n            }';

const replacement = anchor + '\\n\\n            // Check if autoGenerateShots is enabled and scenes were imported\\n            if (autoGenerateShots && importReport?.scenes?.length > 0) {\\n                try {\\n                    importReport.fromAutoGenerateShots = true;\\n                } catch (e) {}\\n            }\\n';

content = content.replace(anchor, replacement);
fs.writeFileSync(file, content);
console.log('Done!');
