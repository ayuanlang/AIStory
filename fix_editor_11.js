const fs = require('fs');
const path = 'frontend/src/pages/Editor.jsx';
let content = fs.readFileSync(path, 'utf8');

// Regex fix attempt
const envMatch = content.match(/if \\(data\\.environments && Array\\.isArray\\(data\\.environments\\)\\) \\{[\\s\\S]*?type: 'environment',\\n                                        name: entityName,\\n                                        name_en: entityNameEn \\|\\| '',\\n                                        id: created\\.id,\\n                                    \\}\\);\\n                                \\}\\n                            \\} catch \\(err\\) \\{[\\s\\S]*?\\}\\n                        \\}\\n                    \\}/);

if(envMatch){
    let posterBlock = envMatch[0].replace(/environments/g, 'posters');
    posterBlock = posterBlock.replace(/environment/g, 'poster');
    posterBlock = posterBlock.replace(/Environment/g, 'Poster');
    posterBlock = posterBlock.replace(/env\\./g, 'poster.');
    posterBlock = posterBlock.replace(/const env of/g, 'const poster of');
    const newContent = envMatch[0] + '\\n\\n                    // Posters\\n                    ' + posterBlock;
    content = content.replace(envMatch[0], newContent);
    fs.writeFileSync(path, content, 'utf8');
} else {
    console.log("Could not find environment block");
}

let sumLogOld = "`Reused existing subjects without overwrite: character=\\${skippedExistingSubjectCounts.character}, prop=\\${skippedExistingSubjectCounts.prop}, environment=\\${skippedExistingSubjectCounts.environment}.`";
let sumLogNew = "`Reused existing subjects without overwrite: character=\\${skippedExistingSubjectCounts.character}, prop=\\${skippedExistingSubjectCounts.prop}, environment=\\${skippedExistingSubjectCounts.environment}, poster=\\${skippedExistingSubjectCounts.poster}.`";
content = content.replace(sumLogOld, sumLogNew);

let extOld = "{character: importedSubjectCounts.character, prop: importedSubjectCounts.prop, environment: importedSubjectCounts.environment}";
let extNew = "{character: importedSubjectCounts.character, prop: importedSubjectCounts.prop, environment: importedSubjectCounts.environment, poster: importedSubjectCounts.poster}";
content = content.replace(extOld, extNew);

fs.writeFileSync(path, content, 'utf8');

