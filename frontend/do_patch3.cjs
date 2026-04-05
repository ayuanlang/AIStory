const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ScriptEditor.jsx', 'utf-8');

text = text.replace(/\r\n/g, '\n');

// 1. view switch
const viewSwitchRegex = /                    \{segments\.length > 0 && \(\n                        <button[\s\S]*?Switch to Table View[\s\S]*?<\/button>\n                    \)}\n/g;
text = text.replace(viewSwitchRegex, '');
console.log('Removed view switch regex match:', (text.match(/Switch to Table View/) === null));

// 2. import button
const importBtnRegex = /                    <button\n                        onClick=\{[^\n]*doImportText[\s\S]*?Manual Import Model Analysis Result[\s\S]*?<\/button>\n/g;
text = text.replace(importBtnRegex, '');
console.log('Removed import btn regex match:', (text.match(/Manual Import Model Analysis Result/) === null));

// 3. workspace
const start_str = '                <div className="border-t border-white/10 bg-black/10 shrink-0">';
const start_idx = text.indexOf(start_str);

if (start_idx !== -1) {
    let depth = 0;
    let pos = start_idx;
    
    while(pos < text.length) {
        if (text.startsWith('<div', pos)) {
            depth++;
            pos += 4;
        } else if (text.startsWith('</div', pos)) {
            depth--;
            pos += 5;
        } else {
            pos++;
        }
        if (depth === 0 && pos > start_idx + 10) break;
    }
    
    pos++;
    
    const before = text.substring(0, start_idx);
    const middle = text.substring(start_idx, pos);
    const after = text.substring(pos);
    
    const newMiddle = "                {isSuperuser && (\n" + middle + "\n                )}\n";
    text = before + newMiddle + after;
    console.log('Wrapped output workspace');
} else {
    console.log('Workspace NOT FOUND');
}

fs.writeFileSync('src/pages/editor/components/ScriptEditor.jsx', text);
