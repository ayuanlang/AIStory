with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

target1 = '''            const startUrl = String(startUpload?.url || '').trim();
            const endUrl = String(endUpload?.url || '').trim();
            if (!startUrl || !endUrl) {
                throw new Error('Failed to upload split start/end frame assets');
            }

            try {
                const preloadUrl = (url) => new Promise((resolve) => {
                    if (!url) return resolve();
                    const img = new Image();
                    img.onload = resolve;
                    img.onerror = resolve;
                    img.src = url;
                });
                await Promise.all([preloadUrl(startUrl), preloadUrl(endUrl)]);
            } catch (e) {
                console.warn('Failed to preload split frames, continuing...', e);
            }'''

replace1 = '''            const startUrl = String(startUpload?.url || '').trim();
            const endUrl = String(endUpload?.url || '').trim();
            if (!startUrl || !endUrl) {
                throw new Error('Failed to upload split start/end frame assets');
            }

            try {
                const preloadUrl = (url) => new Promise((resolve) => {
                    if (!url) return resolve();
                    const img = new Image();
                    img.onload = () => {
                        try { if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(url); } catch(e){}
                        resolve();
                    };
                    img.onerror = resolve;
                    img.src = getFullUrl(url);
                });
                await Promise.all([preloadUrl(startUrl), preloadUrl(endUrl)]);
            } catch (e) {
                console.warn('Failed to preload split frames, continuing...', e);
            }'''

target2 = '''                                    } else if (stableKind === 'start') {
                                        try {
                                            await new Promise((resolve) => {
                                                const img = new Image();
                                                img.onload = resolve;
                                                img.onerror = resolve;
                                                img.src = resultUrl;
                                            });
                                        } catch (e) {}
                                        const nextData = { image_url: resultUrl };'''

replace2 = '''                                    } else if (stableKind === 'start') {
                                        try {
                                            await new Promise((resolve) => {
                                                const img = new Image();
                                                img.onload = () => {
                                                    try { if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(resultUrl); } catch(e){}
                                                    resolve();
                                                };
                                                img.onerror = resolve;
                                                img.src = getFullUrl(resultUrl);
                                            });
                                        } catch (e) {}
                                        const nextData = { image_url: resultUrl };'''

target3 = '''                                    } else if (stableKind === 'end') {
                                        let tech = {};'''

replace3 = '''                                    } else if (stableKind === 'end') {
                                        try {
                                            await new Promise((resolve) => {
                                                const img = new Image();
                                                img.onload = () => {
                                                    try { if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(resultUrl); } catch(e){}
                                                    resolve();
                                                };
                                                img.onerror = resolve;
                                                img.src = getFullUrl(resultUrl);
                                            });
                                        } catch (e) {}
                                        let tech = {};'''

total = 0
if target1 in text:
    text = text.replace(target1, replace1)
    total += 1
if target2 in text:
    text = text.replace(target2, replace2)
    total += 1
if target3 in text:
    text = text.replace(target3, replace3)
    total += 1

if total > 0:
    with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Patched {total} locations")
else:
    print("Zero patches")
