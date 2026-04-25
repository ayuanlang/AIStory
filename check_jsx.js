const fs = require('fs');
const parser = require('@babel/parser');
const content = fs.readFileSync('C:/AS/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx', 'utf8');

try {
  parser.parse(content, {
    sourceType: 'module',
    plugins: ['jsx']
  });
  console.log('No syntax errors found by babel.');
} catch (e) {
  console.error(e.message);
  console.log('Error at location:', e.loc);
}
