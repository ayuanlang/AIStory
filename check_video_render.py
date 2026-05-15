import os
import re

mediamodals_path = r"c:\AS\AIStory\frontend\src\pages\editor\components\MediaModals.jsx"

with open(mediamodals_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """                  const isVideo = isAssetVideoLike(asset);
                  const isSelected = selectedMedias.some((m) => m.id === asset.id);
                  return (
                    <button
                      key={asset.id}
                      onClick={() => handleToggleSelect(asset)}
                      className="group relative flex flex-col items-center justify-center rounded-lg border border-transparent overflow-hidden"
                    >
                      <div className="w-full aspect-square bg-[#151515] relative">
                        {isVideo ? (
                          <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                            <Video className="w-8 h-8 text-white/50" />
                          </div>
                        ) : (
                          <SafeImage
                            src={asset.url}
                            alt="asset"
                            className="w-full h-full object-cover rounded-lg"
                          />
                        )}"""

# If the code differs slightly, let's just grab the whole function or write a regex.
