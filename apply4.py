import re

with open("frontend/src/pages/editor/components/ShotsView.jsx", "r", encoding="utf-8") as f:
    text = f.read()

start_idx = text.find("{/* 3 Column Layout")
end_idx = text.find("{/* Keyframes Section (Enhanced) */}", start_idx)
if start_idx == -1 or end_idx == -1:
    print("Could not find blocks.")
else:
    block = text[start_idx:end_idx]

    # Increase max height of the column wrappers further
    block = block.replace("max-h-[540px] xl:max-h-[600px]", "max-h-[650px] 2xl:max-h-[720px]")

    # Increase the height of the image to make it significantly wider
    block = block.replace("h-[340px] xl:h-[380px]", "h-[420px] 2xl:h-[480px]")

    text = text[:start_idx] + block + text[end_idx:]

    with open("frontend/src/pages/editor/components/ShotsView.jsx", "w", encoding="utf-8") as f:
        f.write(text)

    print("Updated height bounds to increase width.")
