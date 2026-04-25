const fs = require('fs');
const file = 'C:/AS/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx';
let content = fs.readFileSync(file, 'utf8');

content = content.replace(/t\('当前没有可分析的“用户上传图片”主体。系统生成图片将被自动跳过[^']*,/g, "t('当前没有可分析的“用户上传图片”主体。系统生成图片将被自动跳过。',");
content = content.replace(/t\('提示词反推请求发起失败[^']*,/g, "t('提示词反推请求发起失败：',");
content = content.replace(/t\('生图任务请求发起失败[^']*,/g, "t('生图任务请求发起失败：',");
content = content.replace(/t\('主体信息已更新[^']*,/g, "t('主体信息已更新。',");
content = content.replace(/t\('更新主体信息失败[^']*,/g, "t('更新主体信息失败：',");

// A foolproof general fix for `t('Chinese<corrupted char>, 'English')`
// which got mapped to `t('Chinese?, 'English')` where `?` is the `\xEF\xBF\xBD` or similar.
const regex = /t\('((?:[^',]|,(?! '))*)[\x80-\uFFFF],\s*'/g;
content = content.replace(regex, "t('$1。', '");

fs.writeFileSync(file, content, 'utf8');
console.log('Fixed errors');
