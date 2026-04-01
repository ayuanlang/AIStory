const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

// The SafeImage wrapper right now:
const oldSafeImage = `<div ref={containerRef} className={\`relative flex items-center justify-center overflow-hidden bg-[#151515] \${className ? className.replace('object-cover', '').replace('object-contain', '') : ''}\`}>`;

const newSafeImage = `<div ref={containerRef} className={\`relative flex items-center justify-center overflow-hidden bg-[#151515] \${className ? className.replace('object-cover', '').replace('object-contain', '').replace('max-w-full', 'w-full').replace('max-h-full', 'h-full') : ''}\`}>`;

if (content.includes(oldSafeImage)) {
    content = content.replace(oldSafeImage, newSafeImage);
    console.log("SafeImage updated");
} else {
    console.log("SafeImage not found");
}

fs.writeFileSync('frontend/src/pages/Editor.jsx', content, 'utf8');
