const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ScriptEditor.jsx', 'utf-8');
text = text.replace(/\r\n/g, '\n');

// 1. view switch
const viewSwitchRegex = /                    \{segments\.length > 0 && \(\n                        <button[\s\S]*?Switch to Table View[\s\S]*?<\/button>\n                    \)}\n/g;
text = text.replace(viewSwitchRegex, '');
console.log('Removed view switch:', (text.match(/Switch to Table View/) === null));

// 2. import button
const importBtnRegex = /                    <button\n                        onClick=\{[^\n]*doImportText[\s\S]*?Manual Import Model Analysis Result[\s\S]*?<\/button>\n/g;
text = text.replace(importBtnRegex, '');
console.log('Removed import btn:', (text.match(/Manual Import Model Analysis Result/) === null));

// 3. workspace
// Find the exact workspace start string
const start_str = '                <div className="border-t border-white/10 bg-black/10 shrink-0">';
const start_idx = text.indexOf(start_str);

if (start_idx !== -1) {
    let depth = 0;
    let pos = start_idx;
    
    while(pos < text.length) {
        if (text.startsWith('<div', pos)) {
            // is it self closed?
            const closeBracket = text.indexOf('>', pos);
            if (closeBracket !== -1 && text[closeBracket - 1] === '/') {
                // self-closing div!
                pos = closeBracket + 1;
            } else {
                depth++;
                pos += 4;
            }
        } else if (text.startsWith('</div', pos)) {
            depth--;
            pos += 5;
        } else {
            pos++;
        }
        
        if (depth === 0 && pos > start_idx + 10) break;
    }
    
    while(text[pos] !== '>' && pos < text.length) pos++;
    pos++; 
    
    let ws_start = start_idx;
    while(ws_start > 0 && text[ws_start - 1] === ' ') ws_start--;
    
    const before = text.substring(0, ws_start);
    const middle = text.substring(ws_start, pos);
    const after = text.substring(pos);
    
    const newMiddle = "                {isSuperuser && (\n" + middle + "\n                )}\n";
    text = before + newMiddle + after;
    console.log('Wrapped output workspace cleanly');
} else {
    console.log('Workspace NOT FOUND');
}

fs.writeFileSync('src/pages/editor/components/ScriptEditor.jsx', text);
