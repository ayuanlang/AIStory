const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

const regex = /const MENU_ITEMS = \[[\s\S]*?\];/;
const replacement = `const MENU_ITEMS = [
    { id: 'overview', label: '项目信息', icon: Briefcase },
    { id: 'generator', label: '生成器', icon: Wand2 },
    { id: 'script', label: '剧本', icon: FileText },
    { id: 'subjects', label: '角色', icon: Users },
    { id: 'scenes', label: '场景', icon: Image },
    { id: 'shots', label: '分镜', icon: Film },
    { id: 'montage', label: '剪辑', icon: Video }
];`;

content = content.replace(regex, replacement);

fs.writeFileSync('frontend/src/pages/Editor.jsx', content);
console.log('MENU_ITEMS replaced');
