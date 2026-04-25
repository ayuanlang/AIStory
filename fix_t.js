const fs = require('fs');
const file = 'C:/AS/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx';
let content = fs.readFileSync(file, 'utf8');

// Find any instance of t('<some chinese chars>?, 'English...')
// 1. Where there is a t( and the first argument doesn't end with a quote.
// A typical call is t('Chinese', 'English')
// Let's replace any `t('...<weird char>, '...` with `t('...<fixed>.', '...`

// General regex to find `t('` followed by non-ASCII, then `, '`
const regex = /t\('([^']{1,50})[^\x00-\x7F],\s*'/g;

let match;
while ((match = regex.exec(content)) !== null) {
  console.log("Found match: " + match[0]);
}

// Let's just fix the specific ones
const patches = [
  [/t\('批量参考生图任务正在运行中，请稍候[^']*,/g, "t('批量参考生图任务正在运行中，请稍候。',"],
  [/t\('已添加到渲染队列[^']*,/g, "t('已添加到渲染队列。',"],
  [/t\('渲染任务已发起，但加入队列超时[^']*,/g, "t('渲染任务已发起，但加入队列超时。',"],
  [/t\('渲染请求失败[^']*,/g, "t('渲染请求失败：',"]
];

patches.forEach(([pattern, replace]) => {
  content = content.replace(pattern, replace);
});

// Since there could be more unknown cases, I will systematically fix all missing quotes inside t() where there's a comma right after a non-ascii byte:
// We look for: t( ' <chinese> , 'English
// regex: t\('([\u4e00-\u9fa5\w\s]+?)[^\x20-\x7E]\,\s*'/g
// And replace with t('$1', '
// Let's see:
let fixed = content.replace(/t\('([^']{2,100}?)[^\x00-\x7F],\s*'/g, "t('$1。', '");

fs.writeFileSync(file, fixed, 'utf8');
console.log('Auto-fixed missing quotes in t()');
