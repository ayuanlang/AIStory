import re
with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

target = r"\} else if \(stableKind === 'start'\) \{\s*const nextData = \{ image_url: resultUrl \};\s*await onUpdateShot\(stableShotId, nextData\);\s*setEditingShot\(\(prev\) => \(prev && String\(prev\.id\) === stableShotId \? \{ \.\.\.prev, \.\.\.nextData \} : prev\)\);\s*\} else \{"
replacement = r"} else if (stableKind === 'start') {\n                                        try {\n                                            await new Promise((resolve) => {\n                                                const img = new Image();\n                                                img.onload = resolve;\n                                                img.onerror = resolve;\n                                                img.src = resultUrl;\n                                            });\n                                        } catch (e) {}\n                                        const nextData = { image_url: resultUrl };\n                                        await onUpdateShot(stableShotId, nextData);\n                                        setEditingShot((prev) => (prev && String(prev.id) === stableShotId ? { ...prev, ...nextData } : prev));\n                                    } else {"

match = re.search(target, text)
if match:
    text = text.replace(match.group(0), replacement)
    with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Updated start frame preload!!")
else:
    print("Not found by regex")
