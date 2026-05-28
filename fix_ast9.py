import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = r"""                const { adaptedScriptText, userInput: stage2UserInput } = buildStage2UserInputFromStage1(analyzedText || '', selectedReuseSubjectAssets);
                if (!String(adaptedScriptText || '').trim()) {
                    throw new Error('第一阶段未提取到“修改后的剧本”正文，请确认 返回结果包含第二部分剧本正文后重试。');
                }

                setAdaptationText(adaptedScriptText);"""

new_block = r"""                const { adaptedScriptText, userInput: stage2UserInput } = buildStage2UserInputFromStage1(analyzedText || '', selectedReuseSubjectAssets);
                if (!String(adaptedScriptText || '').trim()) {
                    throw new Error('第一阶段未提取到“修改后的剧本”正文，请确认 返回结果包含第二部分剧本正文后重试。');
                }

                // Guard against upstream AI model providers returning backend JSON error strings instead of markdown text.
                if (!/(?:【场景\s*[^\n]+】|\*\*【场景\s*[^\n]+】\*\*|Scene\s*\d+\s*[:：]|\[Scene\s*\d+[^\n]*\])/im.test(adaptedScriptText)) {
                     let errMsg = '第一阶段“优化后剧本”未能识别出任何有效的场景标识 (如【场景 1】)。请确认剧本格式规范。';
                     try {
                         const matchObjStr = adaptedScriptText.trim().replace(/^```json\s*/i, '').replace(/\s*```$/, '');
                         if (matchObjStr.startsWith('{')) {
                             const parseObj = JSON.parse(matchObjStr);
                             if (parseObj.code || parseObj.error) {
                                 errMsg = `上游模型接口返回了系统异常，未能生成剧本：${parseObj.msg || parseObj.error?.message || matchObjStr}`;
                             }
                         }
                     } catch(e) {
                         // Ignore parse error, maybe it's just plain text complaining about constraints
                         if (/服务器错误|maintained|too many requests|rate limit/i.test(adaptedScriptText)) {
                             errMsg = `上游模型接口可能已熔断或维护中，返回异常状态：${adaptedScriptText.slice(0, 100)}...`;
                         }
                     }
                     throw new Error(errMsg);
                }

                setAdaptationText(adaptedScriptText);"""

if old_block in text:
    text = text.replace(old_block, new_block)
    with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Done refactoring Stage 1 scene validation!")
else:
    print("Old block not found!")
