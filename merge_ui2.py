import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Fix Stage 3 sub-category badge
text = text.replace(
    "badge: catJson ? t('可导入', 'Importable') : t('待输出', 'Pending'),",
    "badge: catJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending'),"
)

# 2. Fix the label array in categories
text = text.replace("btnZh: '重跑 道具'", "btnZh: '局部导入重跑道具'")
text = text.replace("btnZh: ' 重跑封面'", "btnZh: '局部导入重跑封面'")

# 3. Merge actions for Stage 3 partial categories loop
def repl_stage3_partial(match):
    return """                actions: [
                    {
                        key: `reimport-stage3-${cat.key}-and-rerun`,
                        label: t(cat.btnZh, cat.btnEn),
                        icon: 'refresh',
                        onClick: async () => {
                            await handleImportStageArtifact({
                                content: catJson,
                                importType: 'json',
                                label: `stage3 ${cat.key} json`,
                                importOptions: {
                                    subjectsJson: catObj || null,
                                    suppressAlerts: false,
                                },
                            });
                            handleRetryPhase2({ targetEntityTypes: [cat.key] });
                        },
                        disabled: isAnalyzing || isRetryingPhase2 || !catJson || !getStageOutputContent('stage2', 'subject_index'),
                        loading: isRetryingPhase2 && (phase2RetryOptionsRef.current?.targetEntityTypes?.includes(cat.key)),
                    }
                ],"""

text = re.sub(r"actions:\s*\[[\s\S]*?label:\s*t\('局部导入'[\s\S]*?targetEntityTypes:\s*\[cat\.key\][\s\S]*?\},?\s*\]\,", repl_stage3_partial, text)


# 4. Check for any missing visualBackfill badge: 
# Earlier my regex might have failed for "待输 出"
text = text.replace("t('可导入', 'Importable') : t('待输 出', 'Pending')", "t('展开可导入', 'Importable') : t('展开待输出', 'Pending')")

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done Stage 3 Partial")
