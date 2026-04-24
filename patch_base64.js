const fs = require('fs');
const src = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let text = fs.readFileSync(src, 'utf8');

text = text.replace(
    'const [analysisUiReport, setAnalysisUiReport] = useState(null);',
    `const [phase1AnalysisReport, setPhase1AnalysisReport] = useState(null);
    const [phase2AnalysisReport, setPhase2AnalysisReport] = useState(null);c
);

fs.writeFileSync(src, text);
console.log('patched state');