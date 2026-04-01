const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

const regex = /<SafeImage\s+src=\{viewingEntity\.image_url\}\s+alt=\{viewingEntity\.name\}\s+className="max-w-full\s+max-h-full\s+object-contain"\s+fallback=\{\s*<div\s+className="flex\s+flex-col\s+items-center\s+justify-center\s+text-white\/20">/g;

const replacement = `<SafeImage src={viewingEntity.image_url} alt={viewingEntity.name} className="w-full h-full object-contain" fallback={<div className="w-full h-full flex flex-col items-center justify-center text-white/20">`;

if (content.match(regex)) {
    content = content.replace(regex, replacement);
    fs.writeFileSync('frontend/src/pages/Editor.jsx', content, 'utf8');
    console.log("Replaced max-w-full with w-full for viewingEntity image model");
} else {
    console.log("Regex didn't match.");
}
