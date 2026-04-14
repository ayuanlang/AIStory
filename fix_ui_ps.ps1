$path = "frontend/src/pages/editor/components/ScriptEditor.jsx"
$c = [System.IO.File]::ReadAllText($path)

$c = $c -replace "\{\[\s*\{\s*key:\s*'autosaving'[\s\S]*?\}]\.map.*\{[\s\S]*?const isActive = !isTerminalFailed[^;]*;", "{[
                            { key: 'autosaving', label: '自动保存' },
                            { key: 'analyzing_scene', label: '场景分析' },
                            { key: 'saving_scenes', label: '场景保存' },
                            { key: 'generating_assets', label: '资产生成' },
                            { key: 'importing_assets', label: '导入资产' },
                            { key: 'completed', label: '分析报告' },
                        ].map((step, idx) => {
                            const stepOrder = ['autosaving', 'analyzing_scene', 'saving_scenes', 'generating_assets', 'importing_assets', 'completed'];
                            const phase = analysisFlowStatus.phase || 'idle';
                            const currentIndex = stepOrder.indexOf(phase);
                            const stepIndex = stepOrder.indexOf(step.key);
                            const hasFinalReport = !!(analysisUiReport && analysisUiReport.status !== 'running');
                            const isTerminalWarning = phase === 'warning';
                            const isTerminalFailed = phase === 'failed';
                            const isDone = !isTerminalFailed && (
                                hasFinalReport
                                    ? stepIndex <= 5
                                    : (isTerminalWarning ? stepIndex <= 2 : currentIndex > stepIndex || phase === 'completed')
                            );
                            const isActive = !isTerminalFailed && !isTerminalWarning && currentIndex === stepIndex;"

$c = $c -replace "phase: 'analyzing'", "phase: 'analyzing_scene'"
$c = $c -replace "phase: 'processing_output_workspace'", "phase: 'saving_scenes'"
$c = $c -replace "phase: 'importing',[\s\S]*?message: t\('正在解析并导入场景", "phase: 'saving_scenes',`r`n                    message: t('正在解析并导入场景"

$c = $c -replace "phase: 'completed',[\s\S]*?message: postImportMissingItems > 0", "phase: 'saving_scenes',`r`n                message: postImportMissingItems > 0"

$c = $c -replace "phase: 'processing', message: '正在生成实体", "phase: 'generating_assets', message: '正在生成实体"
$c = $c -replace "phase: 'persisting', message: '正在安全持久化数据", "phase: 'generating_assets', message: '正在安全持久化数据"
$c = $c -replace "phase: 'importing', message: '实体提取完成", "phase: 'importing_assets', message: '实体提取完成"

$c = $c -replace "md:grid-cols-6", "md:grid-cols-6"

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($path, $c, $utf8NoBom)
