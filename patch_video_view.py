import os

filepath = r"c:\AS\AIStory\frontend\src\pages\editor\components\MediaModals.jsx"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

target = """                {isVideo ? (
                    <div className="w-full h-full flex items-center justify-center bg-black/50">
                        <Video className="w-7 h-7 text-white/65" />
                    </div>
                ) : (
                    <SafeImage src={asset.url} className="w-full h-full object-cover" alt={resolveAssetContextLabel(asset)} />
                )}"""

replacement = """                {isVideo ? (
                    <div className="relative w-full h-full">
                        <video src={asset.url} className="w-full h-full object-cover" preload="metadata" />
                        <div className="absolute inset-0 flex items-center justify-center bg-black/20 pointer-events-none">
                            <Video className="w-7 h-7 text-white/80" />
                        </div>
                    </div>
                ) : (
                    <SafeImage src={asset.url} className="w-full h-full object-cover" alt={resolveAssetContextLabel(asset)} />
                )}"""

content = content.replace(target, replacement)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Video view patched!")