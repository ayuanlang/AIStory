const fs = require('fs');
const file = 'C:/AS/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx';
let lines = fs.readFileSync(file, 'utf8').split('\n');

lines[510] = "            onLog?.(t('主体历史图片已删除。', 'Subject history image deleted.'), 'warning');";
lines[512] = "            onLog?.(t('删除历史图片失败：', 'Failed to delete subject history image: ') + (e?.response?.data?.detail || e?.message || 'unknown error'), 'error');";

fs.writeFileSync(file, lines.join('\n'), 'utf8');
console.log('Fixed lines directly');
