import re

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# PATCH 1: applyJointShotDiptychResult
target1 = r'''            const startUrl = String\(startUpload\?\.url \|\| \'\'\)\.trim\(\);
            const endUrl = String\(endUpload\?\.url \|\| \'\'\)\.trim\(\);
            if \(\!startUrl \|\| \!endUrl\) \{
                throw new Error\(\'Failed to upload split start/end frame assets\'\);
            \}

            try \{
                const preloadUrl = \(url\) => new Promise\(\(resolve\) => \{
                    if \(\!url\) return resolve\(\);
                    const img = new Image\(\);
                    img\.onload = resolve;
                    img\.onerror = resolve;
                    img\.src = url;
                \}\);
                await Promise\.all\(\[preloadUrl\(startUrl\), preloadUrl\(endUrl\)\]\);
            \} catch \(e\) \{
                console\.warn\(\'Failed to preload split frames, continuing\.\.\.\', e\);
            \}'''

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
                        if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(url);
                        resolve();
                    };
                    img.onerror = resolve;
                    img.src = getFullUrl(url);
                });
                await Promise.all([preloadUrl(startUrl), preloadUrl(endUrl)]);
            } catch (e) {
                console.warn('Failed to preload split frames, continuing...', e);
            }'''

# PATCH 2: onImageJobComplete start
target2 = r'''\} else if \(stableKind === \'start\'\) \{\s*try \{\s*await new Promise\(\(resolve\) => \{\s*const img = new Image\(\);\s*img\.onload = resolve;\s*img\.onerror = resolve;\s*img\.src = resultUrl;\s*\}\);\s*\} catch \(e\) \{\}\s*const nextData = \{ image_url: resultUrl \};'''

replace2 = '''} else if (stableKind === 'start') {
                                        try {
                                            await new Promise((resolve) => {
                                                const img = new Image();
                                                img.onload = () => {
                                                    if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(resultUrl);
                                                    resolve();
                                                };
                                                img.onerror = resolve;
                                                img.src = getFullUrl(resultUrl);
                                            });
                                        } catch (e) {}
                                        const nextData = { image_url: resultUrl };'''

# Also patch stableKind === 'end' just in case
target3 = r'''\} else if \(stableKind === \'end\'\) \{\s*let tech = \{\};\s*try \{\s*tech = JSON\.parse\(currentShot\?\.technical_notes \|\| \'\{\}\'\);\s*\} catch \{\s*tech = \{\};\s*\}\s*tech\.end_frame_url = resultUrl;'''

replace3 = '''} else if (stableKind === 'end') {
                                        try {
                                            await new Promise((resolve) => {
                                                const img = new Image();
                                                img.onload = () => {
                                                    if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(resultUrl);
                                                    resolve();
                                                };
                                                img.onerror = resolve;
                                                img.src = getFullUrl(resultUrl);
                                            });
                                        } catch (e) {}
                                        let tech = {};
                                        try {
                                            tech = JSON.parse(currentShot?.technical_notes || '{}');
                                        } catch {
                                            tech = {};
                                        }
                                        tech.end_frame_url = resultUrl;'''

# Execute patches
m1 = re.search(target1, text)
if m1:
    text = text.replace(m1.group(0), replace1)
    print("Patched 1")
else:
    print("Missed 1")

m2 = re.search(target2, text)
if m2:
    text = text.replace(m2.group(0), replace2)
    print("Patched 2")
else:
    print("Missed 2")

m3 = re.search(target3, text)
if m3:
    text = text.replace(m3.group(0), replace3)
    print("Patched 3")
else:
    print("Missed 3")

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

