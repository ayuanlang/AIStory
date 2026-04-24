import os

filepath = 'frontend/src/pages/editor/components/ShotsView.jsx'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update dropdown options
old_opts = '''                                                    <option value="start">{t('仅起始', 'Start Only')}</option>
                                                    <option value="end">{t('仅结束', 'End Only')}</option>
                                                    <option value="entity_refs">{t('实体参考图模式', 'Entity Refs Mode')}</option>'''

new_opts = '''                                                    <option value="start">{t('仅起始', 'Start Only')}</option>
                                                    <option value="entity_refs">{t('实体参考图模式', 'Entity Refs Mode')}</option>
                                                    <option value="entity_refs_start_end">{t('参考图+首尾帧', 'Ref+StartEnd')}</option>'''

text = text.replace(old_opts, new_opts)

old_opts_2 = '''                                                                        <option value="start">{t('仅起始', 'Start Only')}</option>
                                                                        <option value="end">{t('仅结束', 'End Only')}</option>
                                                                        <option value="entity_refs">{t('实体参考图模式', 'Entity Refs Mode')}</option>'''

new_opts_2 = '''                                                                        <option value="start">{t('仅起始', 'Start Only')}</option>
                                                                        <option value="entity_refs">{t('实体参考图模式', 'Entity Refs Mode')}</option>
                                                                        <option value="entity_refs_start_end">{t('参考图+首尾帧', 'Ref+StartEnd')}</option>'''

text = text.replace(old_opts_2, new_opts_2)

# 2. Inject prompt
old_prompt_inj = '''            const globalCtx = getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(submitPrompt) });
            const finalPrompt = isManual ? submitPrompt : (submitPrompt + globalCtx);

            onLog?.(
                `Video API payload mode=${effectiveVideoMode}, visible_refs=${uniqueRefs.length}, ref=${Array.isArray(apiRefImageUrl) ? `list(${apiRefImageUrl.length})` : (apiRefImageUrl ? 'single' : 'none')}, ref_videos=${Array.isArray(apiRefVideoUrls) ? apiRefVideoUrls.length : 0}, last_frame=${apiLastFrameUrl ? 'yes' : 'no'}, keyframes=${Array.isArray(apiKeyframes) ? apiKeyframes.length : 0}, duration=${durParam}`,
                'info'
            );'''

new_prompt_inj = '''            const globalCtx = getGlobalContextStr({ includeStyle: !/\[Global Style\]\s*\(/i.test(submitPrompt) });
            let finalPrompt = isManual ? submitPrompt : (submitPrompt + globalCtx);

            if (effectiveVideoMode === 'entity_refs_start_end') {
                const currentStartFrameUrl = String(shotSnapshot.image_url || '').trim();
                const endRefUrl = String(tech.end_frame_url || '').trim();
                const resolvedStartUrl = await resolveBlobUrlIfAny(currentStartFrameUrl);
                const resolvedEndUrl = await resolveBlobUrlIfAny(endRefUrl);
                
                const startIdx = resolvedUniqueRefs.indexOf(resolvedStartUrl) + 1;
                const endIdx = resolvedUniqueRefs.indexOf(resolvedEndUrl) + 1;

                if (startIdx > 0 && endIdx > 0) {
                    finalPrompt = `首帧为图片${startIdx}, ` + finalPrompt + `, 尾帧定格为图片${endIdx}`;
                } else if (startIdx > 0) {
                    finalPrompt = `首帧为图片${startIdx}, ` + finalPrompt;
                } else if (endIdx > 0) {
                    finalPrompt = finalPrompt + `, 尾帧定格为图片${endIdx}`;
                }
            }

            onLog?.(
                `Video API payload mode=${effectiveVideoMode}, visible_refs=${uniqueRefs.length}, ref=${Array.isArray(apiRefImageUrl) ? `list(${apiRefImageUrl.length})` : (apiRefImageUrl ? 'single' : 'none')}, ref_videos=${Array.isArray(apiRefVideoUrls) ? apiRefVideoUrls.length : 0}, last_frame=${apiLastFrameUrl ? 'yes' : 'no'}, keyframes=${Array.isArray(apiKeyframes) ? apiKeyframes.length : 0}, duration=${durParam}`,
                'info'
            );'''

if old_prompt_inj in text:
    text = text.replace(old_prompt_inj, new_prompt_inj)
else:
    print("WARNING: Could not find prompt injection anchor in ShotsView.jsx")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated ShotsView.jsx')
