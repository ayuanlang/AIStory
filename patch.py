with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''                                    } else if (stableKind === 'start') {
                                        const nextData = { image_url: resultUrl };
                                        await onUpdateShot(stableShotId, nextData);
                                        setEditingShot((prev) => (prev && String(prev.id) === stableShotId ? { ...prev, ...nextData } : prev));
                                    } else {
                                        let tech = {};'''

replacement = '''                                    } else if (stableKind === 'start') {
                                        try {
                                            await new Promise((resolve) => {
                                                const img = new Image();
                                                img.onload = resolve;
                                                img.onerror = resolve;
                                                img.src = resultUrl;
                                            });
                                        } catch (e) {}
                                        const nextData = { image_url: resultUrl };
                                        await onUpdateShot(stableShotId, nextData);
                                        setEditingShot((prev) => (prev && String(prev.id) === stableShotId ? { ...prev, ...nextData } : prev));
                                    } else {
                                        let tech = {};'''

if target in text:
    text = text.replace(target, replacement)
    with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated!')
else:
    print('Target not found')
