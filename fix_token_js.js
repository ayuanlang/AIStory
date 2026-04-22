const fs = require('fs');

const path = 'c:\\AS\\AIStory\\frontend\\src\\lib\\entityToken.js';
let data = fs.readFileSync(path, 'utf8');

data = data.replace(
    /text = text\.replace\(\/\^\(CHAR\|ENV\|PROP\|VEFX\|SFX\)\\s\*:\\s\*\/\i, ''\)\.trim\(\);/,
    "text = text.replace(/^(CHAR|ENV|PROP|VEFX|SFX|角色|人物|环境|场景|道具|物件|特效|视觉特效|音效|声音特效)\\s*[:：]\\s*/i, '').trim();"
);

fs.writeFileSync(path, data, 'utf8');
