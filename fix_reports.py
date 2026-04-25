import re

filepath = r"c:\AS\AIStory\frontend\src\pages\editor\components\ScriptEditor.jsx"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Phase 2 text to be more user friendly and combine considerations.
# We modify "🎉 报告！发现" sections to be more humane:

# 1. First "Recovery" phase
content = re.sub(
    r'`🎉 第二阶段\(资产生成\)恢复成功！自动补充了 \$\{createdCount\} 个资产 \(跳过 \$\{skippedCount\} 个\)。`, `Phase 2 recovered successfully! Created \$\{createdCount\} assets \(skipped \$\{skippedCount\}\).`',
    r'`🎉 恢复成功！系统回溯了进度，顺利为您生成了 ${createdCount} 个全新资产（有 ${skippedCount} 个已存在从而跳过）。`, `Recovery successful. Generated ${createdCount} new assets (skipped ${skippedCount}).`',
    content
)

# 2. Main report conditions
# '🎉 报告！发现'
content = re.sub(
    r'`🎉 报告！发现 \$\{postImportMissingItems\} 个需要补充的资产，我们成功搞定了 \$\{postImportSupplementCreated\} 个（跳过 \$\{postImportSupplementSkipped\} 个，失败 \$\{postImportSupplementFailed\} 个）。`, `Analysis completed: \$\{postImportMissingItems\} missing entities were detected\. Auto-supplement created \$\{postImportSupplementCreated\}, failed \$\{postImportSupplementFailed\}, skipped \$\{postImportSupplementSkipped\}\.`',
    r'`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产，遇到 ${postImportSupplementFailed} 个构建异常）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped, ${postImportSupplementFailed} failed).`',
    content
)

content = re.sub(
    r'`🎉 报告！发现 \$\{postImportMissingItems\} 个需要补充的资产，我们自动补充了 \$\{postImportSupplementCreated\} 个（跳过 \$\{postImportSupplementSkipped\} 个）。`, `Analysis completed: \$\{postImportMissingItems\} missing entities were detected\. Auto-supplement created \$\{postImportSupplementCreated\} \(skipped \$\{postImportSupplementSkipped\}\)\.`',
    r'`🎉 解析大功告成！我们在剧本中识别出 ${postImportMissingItems} 个核心元素，并为您自动化构建了 ${postImportSupplementCreated} 个专属资产（跳过 ${postImportSupplementSkipped} 个已存资产）。`, `Analysis complete! Auto-generated ${postImportSupplementCreated} new assets based on your story (${postImportSupplementSkipped} skipped).`',
    content
)

# "✅ 工作圆满完成！未发现缺失的资产"
content = re.sub(
    r"'✅ 工作圆满完成！未发现缺失的资产。', 'Analysis completed: no missing entities detected, workflow finished\.'",
    r"'✅ 分析管线已完成！该场景暂未发现需要新补充的主体资产。', 'Analysis pipeline completed. No missing entities to construct.'",
    content
)

# "🎉 补充实体资产生成完毕！"
content = content.replace(
    '"🎉 补充实体资产生成完毕！"',
    '"🎉 专属实体资产定制完毕，可随时投产使用！"'
)

# Warning strings
content = re.sub(
    r'"第二阶段未返回可导入的具体实体数据。AI并未输出正确的JSON资产格式，请查阅原文后重试。"',
    r'"AI 引擎在整理出场名单时开小差了，未能返回标准数据表，这可能是由于内容过长。请点击查阅原文检查，是否可以手动重新生成。"',
    content
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("done")
