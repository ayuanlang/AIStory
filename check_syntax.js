const fs = require('fs');
const babel = require('@babel/parser');

try {
    const code = fs.readFileSync('c:\\AS\\AIStory\\frontend\\src\\pages\\editor\\components\\ScriptEditor.jsx', 'utf-8');
    babel.parse(code, {
        sourceType: 'module',
        plugins: ['jsx', 'optionalChaining', 'nullishCoalescingOperator']
    });
    console.log("Syntax check passed!");
} catch (e) {
    console.error("Syntax Error:", e);
}
