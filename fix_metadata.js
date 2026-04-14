const fs = require('fs');
const path = 'frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(path, 'utf8');

// Fix non-superuser auto-trigger to include metadata
const autoTriggerMatch = content.match(/if \\(!isSuperuser\\) \\{\\s*\\/\\/ Automatically chain into Step 2 Entity Design[\\s\\S]*?executeEntityDesignAnalysis\\(`Proceed to Phase 2 Entity Design\\.\\\n\\\\nExtracted Subject Index:\\\n\\$\\{generatedSubjectIndex\\}`, sysPrompt\\);/);

if(autoTriggerMatch) {
    let replaced = autoTriggerMatch[0].replace(/executeEntityDesignAnalysis\\(`Proceed to Phase 2 Entity Design\\.\\\n\\\\nExtracted Subject Index:\\\n\\$\\{generatedSubjectIndex\\}`, sysPrompt\\);/, "const metaPartsStr = buildProjectMetaParts(project);\\n                      const defaultPromptText = `Proceed to Phase 2 Entity Design.\\\\n\\\\nExtracted Subject Index:\\\\n${generatedSubjectIndex}`;\\n                      const fullPromptText = metaPartsStr ? `${metaPartsStr}\\\\n\\\\n${defaultPromptText}` : defaultPromptText;\\n                      executeEntityDesignAnalysis(fullPromptText, sysPrompt);");
    content = content.replace(autoTriggerMatch[0], replaced);
}

// And fix the handleReRunEntityDesignAnalysis one
const rerunMatch = content.match(/} else \\{\\s*executeEntityDesignAnalysis\\(`Proceed to Phase 2 Entity Design\\.\\\n\\\\nExtracted Subject Index:\\\n\\$\\{subjectIndex\\}`\\);\\s*\\}/);
if(rerunMatch) {
    let replaced = rerunMatch[0].replace(/executeEntityDesignAnalysis\\(`Proceed to Phase 2 Entity Design\\.\\\n\\\\nExtracted Subject Index:\\\n\\$\\{subjectIndex\\}`\\);/, "const metaPartsStr = buildProjectMetaParts(project);\\n              const defaultPromptText = `Proceed to Phase 2 Entity Design.\\\\n\\\\nExtracted Subject Index:\\\\n${subjectIndex}`;\\n              const fullPromptText = metaPartsStr ? `${metaPartsStr}\\\\n\\\\n${defaultPromptText}` : defaultPromptText;\\n              executeEntityDesignAnalysis(fullPromptText);");
    content = content.replace(rerunMatch[0], replaced);
}

fs.writeFileSync(path, content, 'utf8');

