import re
with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Normalize
# let's just use re.sub for specific lines.

t1 = r'const preloadUrl = \(url\) => new Promise\(\(resolve\) => \{\s*if \(\!url\) return resolve\(\);\s*const img = new Image\(\);\s*img\.onload = resolve;\s*img\.onerror = resolve;\s*img\.src = url;\s*\}\);'
r1 = r"const preloadUrl = (url) => new Promise((resolve) => {\n                    if (!url) return resolve();\n                    const img = new Image();\n                    img.onload = () => {\n                        try { if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(url); } catch(e){}\n                        resolve();\n                    };\n                    img.onerror = resolve;\n                    img.src = getFullUrl(url);\n                });"

if re.search(t1, text):
    text = re.sub(t1, r1, text)
    print("P1 ok")

t2 = r'\} else if \(stableKind === \'start\'\) \{\s*try \{\s*await new Promise\(\(resolve\) => \{\s*const img = new Image\(\);\s*img\.onload = resolve;\s*img\.onerror = resolve;\s*img\.src = resultUrl;\s*\}\);\s*\} catch \(e\) \{\}'
r2 = r"} else if (stableKind === 'start') {\n                                        try {\n                                            await new Promise((resolve) => {\n                                                const img = new Image();\n                                                img.onload = () => {\n                                                    try { if (typeof rememberWarmMediaUrl === 'function') rememberWarmMediaUrl(resultUrl); } catch(e){}\n                                                    resolve();\n                                                };\n                                                img.onerror = resolve;\n                                                img.src = getFullUrl(resultUrl);\n                                            });\n                                        } catch (e) {}"

if re.search(t2, text):
    text = re.sub(t2, r2, text)
    print("P2 ok")

with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

