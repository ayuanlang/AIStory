const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ScriptEditor.jsx', 'utf-8');
text = text.replace(/\r\n/g, '\n');

// 1. view switch
const viewSwitchRegex = /                    \{segments\.length > 0 && \(\n                        <button[\s\S]*?Switch to Table View[\s\S]*?<\/button>\n                    \)}\n/g;
text = text.replace(viewSwitchRegex, '');

// 2. import button
const importBtnRegex = /                    <button\n                        onClick=\{[^\n]*doImportText[\s\S]*?Manual Import Model Analysis Result[\s\S]*?<\/button>\n/g;
text = text.replace(importBtnRegex, '');

// 3. workspace
const start_str = '                <div className="border-t border-white/10 bg-black/10 shrink-0">';
const start_idx = text.indexOf(start_str);

if (start_idx !== -1) {
    let depth = 0;
    // START pos exactly at the '<div' !!
    let pos = text.indexOf('<div', start_idx);
    
    while(pos < text.length) {
        if (text.startsWith('<div', pos)) {
            const closeBracket = text.indexOf('>', pos);
            if (closeBracket !== -1 && text[closeBracket - 1] === '/') {
                pos = closeBracket + 1; // self-closing!
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
        
        if (depth === 0) break; // we broke perfectly!
    }
    
    while(text[pos] !== '>' && pos < text.length) pos++;
    pos++; 
    
    // Now ws_start can capture spaces before start_str
    let ws_start = text.indexOf('<div', start_idx);
    while(ws_start > 0 && text[ws_start - 1] === ' ') ws_start--;
    
    const before = text.substring(0, ws_start);
    const middle = text.substring(ws_start, pos);
    const after = text.substring(pos);
    
    const newMiddle = "                {isSuperuser && (\n" + middle + "\n                )}\n";
    text = before + newMiddle + after;
    console.log('Wrapped accurately!!!');
}

fs.writeFileSync('src/pages/editor/components/ScriptEditor.jsx', text);
