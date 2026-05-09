import re

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx'

with open(file_path, 'r', encoding='utf-8') as f:
    original_code = f.read()

code = original_code

# Fix 1: handleRetryPhase2 missing clearAnalysisTaskMarker
retry_pattern = r'''(        } catch \(error\) \{
            console\.error\("Retry Phase 2 failed:", error\);
            onLog\?\(`Retry Phase 2 failed: \$\{error\.message \|\| String\(error\)\}`, 'error'\);
            alert\(`Retry Phase 2 failed: \$\{error\.message\}`\);
        \} finally \{
            setIsRetryingPhase2\(false\);
        \})'''

def replace_retry(m):
    return m.group(1).replace('        } finally {', '        } finally {\n            clearAnalysisTaskMarker(activeEpisode?.id);')

code = re.sub(retry_pattern, replace_retry, code, count=1)

# Fix 2: tryResumeAnalysisFromExistingArtifacts missing clearAnalysisTaskMarker
resume_pattern = r'''(        } catch \(err\) \{
            console\.error\(err\);
            setAnalysisFlowStatus\(\{ phase: 'failed', message: '❌ 资产生成失败: ' \+ err\.message \}\);
            setAnalysisUiReport\(\{
                status: 'failed',
                startedAt,
                durationMs: Date\.now\(\) - startedAt,
                phaseTimings: null,
                importReport: null,
                runtimeMeta: null,
                warning: combinedWarning,
                error: err\.message,
            \}\);
        \})'''

def replace_resume(m):
    return m.group(1) + '\n        } finally {\n            clearAnalysisTaskMarker(activeEpisode?.id);\n            setIsAnalyzing(false);\n            analysisRunInFlightRef.current = false;\n        }'

code = re.sub(resume_pattern, replace_resume, code, count=1)

# Fix 3: add lock & isAnalyzing(true) inside tryResumeAnalysisFromExistingArtifacts
resume_start_pattern = r'''(        const startedAt = Date\.now\(\);
        setAnalysisUiReport\(\{
            status: 'running',
            startedAt,
            durationMs: 0,)'''

def replace_resume_start(m):
    return '''        if (analysisRunInFlightRef.current || analysisResumeInFlightRef.current) return true;
        analysisRunInFlightRef.current = true;
        setIsAnalyzing(true);
''' + m.group(1)

code = re.sub(resume_start_pattern, replace_resume_start, code, count=1)

# Make sure we got them all
if code == original_code:
    print("NO CHANGES MADE! Check regex.")
else:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print("Changes applied successfully!")
