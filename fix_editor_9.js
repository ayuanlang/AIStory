const fs = require('fs');
const path = 'frontend/src/pages/Editor.jsx';
let content = fs.readFileSync(path, 'utf8');

// 1. Add posters to skippedExistingSubjectCounts
content = content.replace(/const skippedExistingSubjectCounts = \\{ character: 0, prop: 0, environment: 0 \\};/g, 'const skippedExistingSubjectCounts = { character: 0, prop: 0, environment: 0, poster: 0 };');

// 2. Add posters to planned counts block
let plannedBlock = `                    const plannedEnvironmentCount = Array.isArray(data.environments) ? data.environments.length : 0;\\n                    const plannedPosterCount = Array.isArray(data.posters) ? data.posters.length : 0;\\n                    addLog(\\n                        \\`Entities block detected: character=\\${plannedCharacterCount}, prop=\\${plannedPropCount}, environment=\\${plannedEnvironmentCount}, poster=\\${plannedPosterCount}\\`,\\n                        \\'info\\'\\n                    );`;
content = content.replace(/const plannedEnvironmentCount = [\\s\\S]*?'info'\\s*\\);/, plannedBlock);

// 3. Find the end of data.environments block to insert data.posters
const envMatch = content.match(/if \\(data\\.environments && Array\\.isArray\\(data\\.environments\\)\\) \\{[\\s\\S]*?importedSubjectCounts\\.environment \\+= 1;[\\s\\S]*?\\}\\n                    \\}/);

if(envMatch){
    let posterBlock = envMatch[0].replace(/environments/g, 'posters');
    posterBlock = posterBlock.replace(/environment/g, 'poster');
    posterBlock = posterBlock.replace(/env\\./g, 'poster.');
    posterBlock = posterBlock.replace(/const env of/g, 'const poster of');
    const newContent = envMatch[0] + '\\n\\n                    ' + posterBlock;
    content = content.replace(envMatch[0], newContent);
}

// 4. Update final success log message
content = content.replace(/addLog\\(`Successfully extracted \\$\\{importedSubjectCounts\\.character\\} characters/g, 'addLog(`Successfully extracted ${importedSubjectCounts.character} characters, ${importedSubjectCounts.prop} props, ${importedSubjectCounts.environment} environments, ${importedSubjectCounts.poster} posters (${count} total).`');

fs.writeFileSync(path, content, 'utf8');

