import { collectLlmJsonTextCandidates, sanitizeLlmTextForJsonImport } from './frontend/src/lib/llmJsonExtract.js';

const sample = "reasoning prefix```json\n{\"characters\":[{\"name\":\"Lin Rui\"}]}\n```";
console.log('candidates', collectLlmJsonTextCandidates(sample).length);
console.log('sanitized starts', sanitizeLlmTextForJsonImport(sample).slice(0, 20));
