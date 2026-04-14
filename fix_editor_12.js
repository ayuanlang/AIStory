const fs = require('fs');
const path = 'frontend/src/pages/Editor.jsx';
let content = fs.readFileSync(path, 'utf8');

const startIdx = content.indexOf('if (data.environments && Array.isArray(data.environments)) {');
const endStr = `                                }\\n                            } catch (err) {\\n                                addLog(\\`Environment import failed (\\${entityName}): \\${err?.message || err}\\`, 'warning');\\n                            }\\n                        }\\n                    }`;
const endIdx = content.indexOf(endStr, startIdx);

if (startIdx !== -1 && endIdx !== -1) {
    const block = content.substring(startIdx, endIdx + endStr.length);
    let posterBlock = block.replace(/environments/g, 'posters');
    posterBlock = posterBlock.replace(/environment/g, 'poster');
    posterBlock = posterBlock.replace(/Environment/g, 'Poster');
    posterBlock = posterBlock.replace(/env\\./g, 'poster.');
    posterBlock = posterBlock.replace(/const env of/g, 'const poster of');
    
    const newContent = block + '\\n\\n                    // Posters\\n                    ' + posterBlock;
    content = content.replace(block, newContent);
    fs.writeFileSync(path, content, 'utf8');
}

