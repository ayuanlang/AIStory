const fs = require('fs');

(async function main() {
    try {
        const fileContent = fs.readFileSync('frontend/src/pages/editor/components/ScriptEditor.jsx', 'utf-8');
        // Using acorn to parse it: Wait, do I have acorn installed? I'll use simple node syntax check
        // Oh wait, node -c only works for pure JS. For JSX this is fine, but JSX will fail node -c.
        // Let's just output the last few lines to ensure we haven't truncated anything.
        console.log(fileContent.slice(-100));
        console.log("Content exists and is " + fileContent.length + " bytes long.");
    } catch(e) {
        console.error(e);
        process.exit(1);
    }
})();
