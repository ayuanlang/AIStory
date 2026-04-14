import re

with open("frontend/src/pages/editor/components/ShotsView.jsx", "r", encoding="utf-8") as f:
    text = f.read()

start_idx = text.find("{/* 3 Column Layout")
end_idx = text.find("{/* Keyframes Section (Enhanced) */}", start_idx)
block = text[start_idx:end_idx]

# 1. Increase max height of the column wrappers to allow the prompt to show
block = block.replace("max-h-[350px]", "max-h-[540px] xl:max-h-[600px]")

# 2. Increase the height of the image to make it wider
block = block.replace("h-[260px] lg:h-[300px]", "h-[340px] xl:h-[380px]")

# 3. Ensure the text area acts as a block and does not shrink to 0 height
block = block.replace("resize-none h-[60px]", "resize-none h-[72px] shrink-0")
block = block.replace("h-[60px] focus", "h-[72px] shrink-0 focus")

text = text[:start_idx] + block + text[end_idx:]

with open("frontend/src/pages/editor/components/ShotsView.jsx", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated height and width parameters.")
