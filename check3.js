const fs = require('fs');
const eslint = require('eslint');

(async function main() {
    try {
        const fileContent = fs.readFileSync('frontend/src/pages/editor/components/ScriptEditor.jsx', 'utf-8');
        // just parse it with acorn to ensure no syntax errors
        const acorn = require('acorn');
        const jsx = require('acorn-jsx');
        const parser = acorn.Parser.extend(jsx());
        parser.parse(fileContent, { sourceType: 'module', ecmaVersion: 2020 });
        console.log("Syntax OK!");
    } catch(e) {
        console.error(e);
        process.exit(1);
    }
})();
