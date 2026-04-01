const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

const menuRegex = /const MENU_ITEMS = \[\s*\{\s*id:\s*'overview',\s*label:\s*'项目信息',\s*icon:\s*Briefcase\s*\},[\s\S]*?\{\s*id:\s*'generator',\s*label:\s*'生成器',\s*icon:\s*Wand2\s*\},[\s\S]*?\];/;

const newMenu = `const MENU_ITEMS = [
    { id: 'overview', label: '项目信息', icon: Briefcase },
    { id: 'script', label: '剧本', icon: FileText },
    { id: 'subjects', label: '角色', icon: Users },
    { id: 'scenes', label: '场景', icon: ImageIcon },
    { id: 'shots', label: '分镜', icon: Film },
    { id: 'montage', label: '剪辑', icon: Video }
];`;

if (menuRegex.test(content)) {
    content = content.replace(menuRegex, newMenu);
    fs.writeFileSync('frontend/src/pages/Editor.jsx', content);
    console.log("MENU_ITEMS updated");
} else {
    console.log("MENU_ITEMS not found");
}
