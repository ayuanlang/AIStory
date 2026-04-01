const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

const targetStr = '<SafeImage src={viewingEntity.image_url} alt={viewingEntity.name} className="max-w-full max-h-full object-contain" fallback={<div className="flex flex-col items-center justify-center p-8 text-neutral-500 gap-4"><Image className="w-12 h-12 opacity-50" /><span className="text-sm">暂无图片</span></div>} />';

const newStr = '<SafeImage src={viewingEntity.image_url} alt={viewingEntity.name} className="w-full h-full object-contain" fallback={<div className="flex flex-col items-center justify-center p-8 text-neutral-500 gap-4"><Image className="w-12 h-12 opacity-50" /><span className="text-sm">暂无图片</span></div>} />';

if (content.includes(targetStr)) {
    content = content.replace(targetStr, newStr);
    console.log("ViewingEntity target found and replaced!");
} else {
    console.log("ViewingEntity target NOT found. Checking what's there...");
    const regex = /<SafeImage\s+src=\{viewingEntity\.image_url\}[^>]*\/>/g;
    const match = content.match(regex);
    if (match) {
        console.log("Found matches:");
        match.forEach(m => console.log(m));
    }
}

fs.writeFileSync('frontend/src/pages/Editor.jsx', content, 'utf8');
