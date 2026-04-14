const fs = require('fs');
const path = 'frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(path, 'utf8');

// Fix advanced analysis phase 2 auto trigger
const advMatch = content.match(/const defaultPromptText = `Proceed to Phase 2 Entity Design\\.\\\\n\\\\nExtracted Subject Index:\\\\n\\$\\{generatedSubjectIndex\\}`;\\s*try \\{\\s*const res = await fetchPrompt\\("skill:scene_analysis_feature_stack\\/entity_design\\.md"\\);/);

if(advMatch) {
    let replaced = advMatch[0].replace(/const defaultPromptText = `Proceed to Phase 2 Entity Design\\.\\\\n\\\\nExtracted Subject Index:\\\\n\\$\\{generatedSubjectIndex\\}`;/, "const metaPartsStr = buildProjectMetaParts(project);\\n                 const defaultPromptText = `Proceed to Phase 2 Entity Design.\\\\n\\\\nExtracted Subject Index:\\\\n${generatedSubjectIndex}`;\\n                 const fullPromptText = metaPartsStr ? `${metaPartsStr}\\\\n\\\\n${defaultPromptText}` : defaultPromptText;");
    
    // now replace setUserPrompt(defaultPromptText) with fullPromptText further down
    const blockMatch = content.match(/setUserPrompt\\(defaultPromptText\\);/g);
    if(blockMatch) {
        content = content.replace(/setUserPrompt\\(defaultPromptText\\);/g, "setUserPrompt(fullPromptText);");
    }
    
    content = content.replace(advMatch[0], replaced);
}

fs.writeFileSync(path, content, 'utf8');

