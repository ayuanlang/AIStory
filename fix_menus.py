import sys

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace start frame
old_start = '''                                                                    {renderDetailActionButton({
                                                                        label: t('生成起始帧', 'Generate Start Frame'),
                                                                        busyLabel: t('起始帧生成中...', 'Generating Start Frame...'),
                                                                        onClick: () => generateAssetWithLang('start', -1, { cfg: currentImageCfgValue }),       
                                                                        disabled: currentShotGenerating,
                                                                        busy: currentShotGenerating,
                                                                        variant: 'primary',
                                                                    })}
                                                                    {renderDetailActionButton({
                                                                        label: t('裁边', 'Trim Edges'),'''

new_start = '''                                                                    {renderDetailActionButton({
                                                                        label: t('生成起始帧', 'Generate Start Frame'),
                                                                        busyLabel: t('起始帧生成中...', 'Generating Start Frame...'),
                                                                        onClick: () => generateAssetWithLang('start', -1, { cfg: currentImageCfgValue }),       
                                                                        disabled: currentShotGenerating,
                                                                        busy: currentShotGenerating,
                                                                        variant: 'primary',
                                                                    })}
                                                                    {renderPromptLangMenu()}
                                                                    {renderDetailActionButton({
                                                                        label: t('裁边', 'Trim Edges'),'''

text = text.replace(old_start, new_start)

# Replace end frame
old_end = '''                                                                    {renderDetailActionButton({
                                                                        label: t('生成结束帧', 'Generate End Frame'),
                                                                        busyLabel: t('结束帧生成中...', 'Generating End Frame...'),
                                                                        onClick: () => generateAssetWithLang('end', -1, { cfg: currentImageCfgValue }),
                                                                        disabled: currentShotGenerating,
                                                                        busy: currentShotGenerating,
                                                                        variant: 'primary',
                                                                    })}
                                                                    {renderDetailActionButton({
                                                                        label: t('裁边', 'Trim Edges'),'''

new_end = '''                                                                    {renderDetailActionButton({
                                                                        label: t('生成结束帧', 'Generate End Frame'),
                                                                        busyLabel: t('结束帧生成中...', 'Generating End Frame...'),
                                                                        onClick: () => generateAssetWithLang('end', -1, { cfg: currentImageCfgValue }),
                                                                        disabled: currentShotGenerating,
                                                                        busy: currentShotGenerating,
                                                                        variant: 'primary',
                                                                    })}
                                                                    {renderPromptLangMenu()}
                                                                    {renderDetailActionButton({
                                                                        label: t('裁边', 'Trim Edges'),'''

text = text.replace(old_end, new_end)

# Replace video frame
old_video = '''                                                                    {renderDetailActionButton({
                                                                        label: t('生成视频', 'Generate Video'),
                                                                        busyLabel: t('视频生成中...', 'Generating Video...'),
                                                                        onClick: () => generateAssetWithLang('video'),
                                                                        disabled: currentShotGenerating,
                                                                        busy: currentShotGenerating,
                                                                        variant: 'primary',
                                                                    })}
                                                                    {renderDetailActionButton({
                                                                        label: t('生成配音', 'Generate Voiceover'),'''

new_video = '''                                                                    {renderDetailActionButton({
                                                                        label: t('生成视频', 'Generate Video'),
                                                                        busyLabel: t('视频生成中...', 'Generating Video...'),
                                                                        onClick: () => generateAssetWithLang('video'),
                                                                        disabled: currentShotGenerating,
                                                                        busy: currentShotGenerating,
                                                                        variant: 'primary',
                                                                    })}
                                                                    {renderPromptLangMenu()}
                                                                    {renderDetailActionButton({
                                                                        label: t('生成配音', 'Generate Voiceover'),'''

text = text.replace(old_video, new_video)

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done")
