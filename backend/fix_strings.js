const fs = require('fs');
const path = './frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(path, 'utf8');

// Update UI button prompt
content = content.replace(
  /<Loader2 className=\"w-4 h-4 animate-spin\" \/> \{t\('分析中\.\.\.', 'Analyzing\.\.\.'\)\}/g,
  '<Loader2 className=\"w-4 h-4 animate-spin\" /> {t(\\\'AI正在为您深度拆解剧本...\\\', \\\'AI is deeply analyzing your script...\\\')}'
);

// Update phases
content = content.replace(/检测到进行中的分析任务，正在恢复监听\.\.\./g, '业务恢复：识别到您正在进行中的AI分镜进度，正在为您恢复现场...');
content = content.replace(/已提交 LLM，正在等待返回。提交阶段超时约 300s，整体等待最长约 600s。/g, 'AI 收到您的要求，正为您深度推演分镜结构，此过程包含数万 Token 推理解析，可能需要 1~2 分钟，敬请稍作等待...');
content = content.replace(/LLM 已返回，正在自动导入\.\.\./g, '推演完成：已成功获取 AI 的导演级解析框架，正在为您结构化导入至工作台...');
content = content.replace(/场景与 subjects 导入完成，正在逐个场景检查实体缺失\.\.\./g, '主体信息同步完毕！AI 正在查漏补缺，智能扫描并修复各分镜画面的上下文元素...');
content = content.replace(/未检测到可停止的分析任务。/g, '当前没有正在运行的分镜推演任务需要被终止。');
content = content.replace(/正在检查 Subject 一致性\.\.\./g, '即将完成！正在为您进行最终的实体逻辑校验与角色一致性排查...');
content = content.replace(/正在导入实体\.\.\./g, '素材同步：正在为您分选核心角色与场景，自动并入当前项目素材引擎...');
content = content.replace(/分析与导入已完成。/g, '深度拆解与自动构建已完美收官！请移步工作台检阅分镜详情。');
content = content.replace(/正在重新导入重生成 LLM 内容\.\.\./g, '正在为您刷新工作台，将最新分镜数据导入画布...');
content = content.replace(/正在自动执行检查：Subject 一致性\.\.\./g, 'AI品控：正在校验全篇人物逻辑连贯性与主体一致性...');
content = content.replace(/检查结果已确认，已切换到 Scenes。/g, '一切就绪！已为您平滑切换到场景画板工作区。');

fs.writeFileSync(path, content);
console.log('Progress strings updated successfully.');
