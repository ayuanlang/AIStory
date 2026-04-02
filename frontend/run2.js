const fs = require('fs');
let code = fs.readFileSync('src/pages/Settings.jsx', 'utf8');

const target = \<div className="bg-black/20 p-4 sm:p-6 rounded-xl border border-cyan-400/20 space-y-4 shadow-sm">
                            <div className="flex items-center justify-between gap-3">
                                <h3 className="text-base font-medium">{t('选择默认激活的 API 配置', 'Select Default Activated API Config')}</h3>\;

const altTarget = \<div className="bg-black/20 p-4 sm:p-6 rounded-xl border border-cyan-400/20 space-y-4 shadow-sm">
                            <div className="flex items-center justify-between gap-3">
                                <h3 className="text-base font-medium">{t('閫夋嫨榛樿婵€娲荤殑 API 閰嶇疆', 'Select Default Activated API Config')}</h3>\;


const replacement = \<div className="bg-black/20 p-4 sm:p-6 rounded-xl border border-cyan-400/20 space-y-4 shadow-sm">
                            <div className="flex items-center justify-between gap-3">
                                <h3 className="text-base font-medium">{t('统一功能 API 默认配置', 'Unified Function API Defaults')}</h3>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                {t('在此处为各个功能项选择默认的全局 API（持久化）。如果在具体功能页面进行了选择，则优先使用该临时配置（刷新丢失）。', 'Select the default persistent global API for each function here. This will be overridden by temporary selections in specific function blocks.')}
                            </p>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                {Object.keys(functionApiConfigs || {}).map((funcName) => {
                                    let displayName = funcName;
                                    if (funcName === 'script_analysis') displayName = t('剧本自动配置分析', 'Script Auto Analysis');
                                    else if (funcName === 'generate_subjects') displayName = t('生成实体(角色/场景/道具)', 'Generate Subjects(Char/Scene/Prop)');
                                    else if (funcName === 'generate_shot_images') displayName = t('生成分镜图片', 'Generate Shot Images');
                                    else if (funcName === 'generate_videos') displayName = t('生成分镜视频', 'Generate Shot Videos');
                                    else if (funcName === 'subject_image_analysis') displayName = t('实体特征分析', 'Subject Feature Analysis');
                                    else if (funcName === 'generate_cover') displayName = t('生成项目封面', 'Generate Project Cover');

                                    return (
                                    <div key={'func_cfg_' + funcName} className="flex flex-col gap-1.5 p-3 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors">
                                        <span className="text-sm font-medium text-white/90 break-words">{displayName} <span className="text-white/30 text-xs truncate">- {funcName}</span></span>
                                        <div className="w-full flex-col items-start w-full">
                                            <FunctionApiSelector functionName={funcName} configs={functionApiConfigs} persistent={true} className="w-full flex-col items-start gap-1 text-white" />
                                        </div>
                                    </div>
                                )})}
                            </div>
                        </div>

                        \ + altTarget; // injecting before the legacy block

if (code.includes(altTarget)) {
    code = code.replace(altTarget, replacement);
    fs.writeFileSync('src/pages/Settings.jsx', code, 'utf8');
    console.log('Fixed Settings.jsx successfully.');
} else {
    console.log('Target block not found!');
}