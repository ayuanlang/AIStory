import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = re.compile(
    r"(const \{ adaptedScriptText, userInput: stage2UserInput \} = buildStage2UserInputFromStage1(?:.*?)\n\s*if \(\!String\(adaptedScriptText \|\| \'\'\)\.trim\(\)\) \{\n\s*throw new Error\(\'第一阶段未提取到.*?\'\);\n\s*\}\n\n\s*setAdaptationText\(adaptedScriptText\);)", 
    re.DOTALL
)

new_code = r"""\1

                // Guard against upstream AI model providers returning backend JSON error strings instead of markdown text.
                if (!/(?:【场景\s*[^\n]+】|\*\*\s*【场景\s*[^\n]+】\s*\*\*|Scene\s*\d+\s*[:：]|\[Scene\s*\d+[^\n]*\])/im.test(adaptedScriptText)) {
                     let errMsg = '第一阶段“优化后剧本”未能识别出任何有效的场景标识 (如【场景 1】)。请确认剧本格式规范是否有误或是否被上游服务吞字。';
                     try {
                         const matchObjStr = adaptedScriptText.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
                         if (matchObjStr.startsWith('{')) {
                             const parseObj = JSON.parse(matchObjStr);
                             if (parseObj.code || parseObj.error || parseObj.msg) {
                                 errMsg = `上游模型接口返回了系统异常，未能正常生成剧本：\n${parseObj.msg || parseObj.error?.message || matchObjStr}`;
                             }
                         }
                     } catch(e) {
                         // Ignore parse error, maybe it's just plain text complaining about constraints
                         if (/服务器错误|maintained|too many requests|rate limit/i.test(adaptedScriptText)) {
                             errMsg = `上游模型接口可能已熔断或维护中，返回异常状态：\n${adaptedScriptText.slice(0, 150)}...`;
                         }
                     }
                     throw new Error(errMsg);
                }"""

# Actually I'll do a simple string replace.
def find_and_inject():
    search_str = "setAdaptationText(adaptedScriptText);"
    idx = text.find(search_str)
    if idx == -1: return False
    
    inject = """

                // Guard against upstream AI model providers returning backend JSON error strings instead of markdown text.
                if (!/(?:【场景\\s*[^\\n]+】|\\*\\*\\s*【场景\\s*[^\\n]+】\\s*\\*\\*|Scene\\s*\\d+\\s*[:：]|\\[Scene\\s*\\d+[^\\n]*\\])/im.test(adaptedScriptText)) {
                     let errMsg = '第一阶段“优化后剧本”未能识别出任何有效的场景标识 (如【场景 1】)。请确认上游模型是否未按格式要求生成，或发生了内部中断被网关拦截返回了异常串。\\n返回内容片段：' + adaptedScriptText.slice(0, 50) + '...';
                     try {
                         const matchObjStr = adaptedScriptText.trim().replace(/^```(?:json)?\\s*/i, '').replace(/\\s*```$/, '');
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
                
    modified = text[:idx + len(search_str)] + inject + text[idx + len(search_str):]
    with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
        f.write(modified)
    return True

if find_and_inject():
    print("Injected hook successfully!")
else:
    print("Could not find anchor string!")
