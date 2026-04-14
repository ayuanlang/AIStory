#!/usr/bin/env python3

import re

FILE_PATH = r"c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx"

def read_file():
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(content):
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    content = read_file()
    
    # Check if handleRetryPhase2 exists
    if "const handleRetryPhase2 =" not in content:
        # Add handleRetryPhase2 right before the return statement of ScriptEditor component
        # Look for the main return statement: if (!activeEpisode) return <div ...> return ( <div className="p-4...
        pattern = r"(    if \(!activeEpisode\) return <div className=\"p-8 text-muted-foreground\">\{t\('请选择或创建一个分集开始写作。', 'Select or create an episode to start writing.'\)\}</div>;\n\n    return \()"
        
        handler_code = r"""
    const handleRetryPhase2 = async () => {
        if (!activeEpisode?.id) return;
        setIsRetryingPhase2(true);
        try {
            onLog?.('Retrying Phase 2 (Asset Generation)...', 'process');
            // Re-run the second pass with the (potentially edited) subjectIndexText
            // It will also bust deduplication cache by using sceneAnalysisMode = "2_pass_generate_assets" internally
            const postImportSceneSubjectReport = await runPostImportSceneSubjectPipeline(
                analysisUiReport?.importReport || {},
                subjectIndexText
            );
            
            // Update the UI report with the new asset counts
            if (analysisUiReport && typeof analysisUiReport === 'object') {
                const newImportReport = {
                    ...analysisUiReport.importReport,
                    sceneSubjectPostImportReport: postImportSceneSubjectReport,
                };
                
                setAnalysisUiReport(prev => ({
                    ...prev,
                    importReport: newImportReport,
                }));
                
                const postImportMissingItems = Number(postImportSceneSubjectReport?.missingItemCount || 0);
                const postImportSupplementCreated = Number(postImportSceneSubjectReport?.supplementReport?.createdItems?.length || 0);
                const postImportSupplementFailed = Number(postImportSceneSubjectReport?.supplementReport?.failedItems?.length || 0);
                const postImportSupplementSkipped = Number(postImportSceneSubjectReport?.supplementReport?.skippedItems?.length || 0);
                
                setAnalysisFlowStatus({
                    phase: 'completed',
                    message: postImportMissingItems > 0
                        ? (
                            postImportSupplementFailed > 0
                                ? t(`重试分析完成：检测到 ${postImportMissingItems} 个缺失实体，已自动补充成功 ${postImportSupplementCreated} 项、失败 ${postImportSupplementFailed} 项、跳过 ${postImportSupplementSkipped} 项。`, `Retry completed: ${postImportMissingItems} missing entities detected. Supplement created ${postImportSupplementCreated}, failed ${postImportSupplementFailed}, skipped ${postImportSupplementSkipped}.`)
                                : t(`重试分析完成：检测到 ${postImportMissingItems} 个缺失实体，已自动补充 ${postImportSupplementCreated} 项（跳过 ${postImportSupplementSkipped} 项）。`, `Retry completed: ${postImportMissingItems} missing entities detected. Supplement created ${postImportSupplementCreated} (skipped ${postImportSupplementSkipped}).`)
                        )
                        : t('重试分析完成：未检测到实体缺失，流程已结束。', 'Retry completed: no missing entities detected, workflow finished.'),
                });
                
                onLog?.('Phase 2 Asset Generation Retry Completed.', 'success');
            }
        } catch (error) {
            console.error("Retry Phase 2 failed:", error);
            onLog?.(`Retry Phase 2 failed: ${error.message || String(error)}`, 'error');
            alert(`Retry Phase 2 failed: ${error.message}`);
        } finally {
            setIsRetryingPhase2(false);
        }
    };\n
\1"""
        content = re.sub(pattern, handler_code, content)
        print("Added handleRetryPhase2 function.")
    else:
        print("handleRetryPhase2 already exists.")
        
    write_file(content)
    print("Done fixing ScriptEditor.jsx.")

if __name__ == '__main__':
    main()
