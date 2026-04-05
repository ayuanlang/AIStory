import sys
with open('frontend/src/pages/editor/components/ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

target = """                                <div className="text-white/40 pt-2 border-t border-white/5 mt-2">
                                    {t('总生成时间：', 'Total Time: ')} {analysisUiReport.durationMs ? `${(analysisUiReport.durationMs / 1000).toFixed(1)} ${t('秒', 's')}` : '--'}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}"""

replacement = """                                <div className="text-white/40 pt-2 border-t border-white/5 mt-2">
                                    {t('总生成时间：', 'Total Time: ')} {analysisUiReport.durationMs ? `${(analysisUiReport.durationMs / 1000).toFixed(1)} ${t('秒', 's')}` : '--'}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            );
            })()}"""
            
if target in text:
    text = text.replace(target, replacement)
    with open('frontend/src/pages/editor/components/ScriptEditor.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Replaced Successfully!")
else:
    print("Target not found.")