import os
import re

mediamodals_path = r"c:\AS\AIStory\frontend\src\pages\editor\components\MediaModals.jsx"

with open(mediamodals_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    } else if (secondaryFilterKind === 'shot') {
      // Only narrow by exact shot when user explicitly chooses a shot value.
      if (secondaryFilterValue) {"""

replacement = """    } else if (secondaryFilterKind === 'shot') {
      // Shot scope should not mix in entity assets (subjects).
      filtered = filtered.filter((asset) => isShotBoundAsset(asset) || !asset.meta_info?.asset_type || asset.meta_info.asset_type !== 'subject');
      
      // Only narrow by exact shot when user explicitly chooses a shot value.
      if (secondaryFilterValue) {"""

content = content.replace(target, replacement)

with open(mediamodals_path, "w", encoding="utf-8") as f:
    f.write(content)

print("MediaModals patched!")
