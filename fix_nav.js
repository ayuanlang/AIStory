const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

// Fix isActive logic
content = content.replace(
    /const isActive = activeTab === item\.id \|\| \(item\.subIds && item\.subIds\.includes\(activeTab\)\);/g,
    'const isActive = activeTab === item.id;'
);

// Fix navigateTopMenu
const navSearch = /const navigateTopMenu = \(item\) => {[\s\S]*?};/g;
const navReplace = `const navigateTopMenu = (item) => {
        setActiveTab(item.id);
    };`;
content = content.replace(navSearch, navReplace);

fs.writeFileSync('frontend/src/pages/Editor.jsx', content);
console.log('Menu logic restored');
