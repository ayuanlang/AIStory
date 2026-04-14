const fs = require('fs');
const path = 'frontend/src/pages/Editor.jsx';
let content = fs.readFileSync(path, 'utf8');

// 3. Find the end of data.environments block to insert data.posters
const envMatch = content.match(/if \\(data\\.environments && Array\\.isArray\\(data\\.environments\\)\\) \\{[\\s\\S]*?importedSubjectCounts\\.environment \\+= 1;[\\s\\S]*?type: 'environment'[\\s\\S]*?\\}\\n                            \\} catch \\(err\\) \\{[\\s\\S]*?\\}\\n                        \\}\\n                    \\}/);

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

