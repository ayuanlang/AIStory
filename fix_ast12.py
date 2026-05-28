import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = r"""                // Guard against upstream AI model providers returning backend JSON error strings instead of markdown text.
                if (!/(?:【场景\s*[^\n]+】|\*\*\s*【场景\s*[^\n]+】\s*\*\*|Scene\s*\d+\s*[:：]|\[Scene\s*\d+[^\n]*\])/im.test(adaptedScriptText)) {
                     let errMsg = '第一阶段“优化后剧本”未能识别出任何有效的场景标识 (如【场景 1】)。请确认上游模型是否未按格式要求生成，或发生了内部中断被网关拦截返回了异常串。\n返回内容片段：' + adaptedScriptText.slice(0, 50) + '...';
                     try {
                         const matchObjStr = adaptedScriptText.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
                         if (matchObjStr.startsWith('{')) {
                             const parseObj = JSON.parse(matchObjStr);
                             if (parseObj.code || parseObj.error || parseObj.msg) {
                                 errMsg = `上游底层大语言模型接口异常 (拦截网关)：${parseObj.msg || parseObj.error?.message || matchObjStr}`;
                             }
                         }
                     } catch(e) {
                         if (/服务器错误|maintained|too many requests|rate limit/i.test(adaptedScriptText)) {
                             errMsg = `上游接口熔断或系统正在维护中，返回了异常拦截页：${adaptedScriptText.slice(0, 100)}`;
                         }
                     }
                     throw new Error(errMsg);
                }"""

new_block = r"""                // Guard against upstream AI model providers returning backend JSON error strings instead of markdown text.
                let isUpstreamError = false;
                let errMsg = '';
                const matchObjStr = adaptedScriptText.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
                if (matchObjStr.startsWith('{')) {
                    try {
                        const parseObj = JSON.parse(matchObjStr);
                        if (parseObj.code === 500 || parseObj.error || parseObj.msg) {
                            isUpstreamError = true;
                            errMsg = `上游底层大语言模型接口异常 (拦截网关)：${parseObj.msg || parseObj.error?.message || matchObjStr}`;
                        }
                    } catch(e) {}
                }
                if (!isUpstreamError && /服务器错误|maintained|too many requests|rate limit/i.test(adaptedScriptText)) {
                    isUpstreamError = true;
                    errMsg = `上游接口熔断或系统正在维护中，返回了异常拦截页：${adaptedScriptText.slice(0, 100)}`;
                }
                if (isUpstreamError) {
                    throw new Error(errMsg);
                }"""

if old_block in text:
    text = text.replace(old_block, new_block)
    with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Done refactoring Stage 1 validation!")
else:
    print("Old block not found!")
