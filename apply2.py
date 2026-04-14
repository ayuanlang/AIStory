import re

with open("frontend/src/pages/editor/components/ShotsView.jsx", "r", encoding="utf-8") as f:
    text = f.read()

start_idx = text.find("{/* 3 Column Layout")
end_idx = text.find("{/* Keyframes Section (Enhanced) */}", start_idx)
block = text[start_idx:end_idx]

original_str = 'className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border'
new_str = 'className={`${isPortrait ? "h-[260px] lg:h-[300px] w-auto mx-auto shrink-0" : "aspect-video w-full"} bg-black rounded border'

block = block.replace(original_str, new_str)
block = block.replace("overflow-y-auto custom-scrollbar", "overflow-hidden flex flex-col justify-between")

text = text[:start_idx] + block + text[end_idx:]

with open("frontend/src/pages/editor/components/ShotsView.jsx", "w", encoding="utf-8") as f:
    f.write(text)

print("Replacement done.")
