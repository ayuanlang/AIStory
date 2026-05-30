const fs = require('fs');
const code = fs.readFileSync('c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx', 'utf8');
const match = code.match(/const extractAnalysisSections = useCallback\(\(rawText\) => \{([\s\S]*?)return \{\r?\n\s*authoritativeSubjectText/);

if (!match) {
    console.error('Could not find extractAnalysisSections');
    process.exit(1);
}

const fnBody = match[1] + `return {
    authoritativeSubjectText,
    subjectIndexText: hasStructuredSubjectIndex ? extractedText : '',
    adaptationText: extractedAdaptationText,
    hasStructuredSubjectIndex,
};`;

const extractAnalysisSections = new Function('rawText', fnBody);

const mockText = `### Subject Index
subject_no | subject_type | subject_name_zh | subject_name_en | dependency_reference | entity_attributes | script_entity_coverage --- | --- | --- | --- | --- | --- | --- S001 | character | 布鲁克·海斯 | Brooke Hayes | None | Protagonist, Neutral faction, fake wife acting as twin sister, female, late 20s, Caucasian. Wearing Claire's expensive silk nightrobe. Cold, suppressed, isolated demean。。。`;

console.log(extractAnalysisSections(mockText));
