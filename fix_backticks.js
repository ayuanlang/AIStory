const fs = require('fs');
const file = 'C:/AS/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx';
let content = fs.readFileSync(file, 'utf8');

content = content.replace(/将批量提示词反推并反[\s\S]*?是否继续？`/, 
  "将批量提示词反推并反写 ${targets.length} 个“用户上传图片”主体信息 ${skippedSystemCount > 0 ? `（自动跳过系统生图 ${skippedSystemCount} 个）` : ''}，是否继续？`"
);

content = content.replace(/将批量进行[\s\S]*?进行参考生图，是否继续？`/,
  "将批量进行 ${targets.length} 个主体图片生成 ${skippedSystemCount > 0 ? `（自动跳过已有 ${skippedSystemCount} 个用户上传图片）` : ''}，这将消耗 ${targets.length * 3} 积分。\\n\\n只有当前没有绑定外部生图链接的主体才会进行参考生图，是否继续？`"
);

fs.writeFileSync(file, content, 'utf8');
console.log('Fixed backticks');
