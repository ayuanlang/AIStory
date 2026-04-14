import re

with open("frontend/src/pages/editor/components/ShotsView.jsx", "r", encoding="utf-8") as f:
    text = f.read()

start_idx = text.find("{/* 3 Column Layout")
end_idx = text.find("{/* Keyframes Section", start_idx)
block = text[start_idx:end_idx]

# Remove the inline styles and fix classes
# We will replace the image containers to have dynamic portrait classes that center and scale

def replacer_img(m):
    # Group(1) is the opening up to style. We will remove style completely if we want to rely on tailwind or keep it but add sizing classes.
    # Actually let's just add the right classes
    
    # Wait, the current block is:
    # <div style={isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined} className={`${isPortrait ? "" : "aspect-video"} bg-black rounded ...
    return m.group(0).replace(
        'className={`${isPortrait ? "" : "aspect-video"} bg-black rounded border',
        'className={`${isPortrait ? "h-auto max-h-[320px] lg:max-h-[400px] w-auto mx-auto shrink-0" : "aspect-video w-full"} bg-black rounded border'
    )

new_block = re.sub(
    r'<div\s+style=\{isPortrait[^>]+className="[^"]+bg-black rounded border[^>]+>',
    replacer_img,
    block
)

# And for the wrapper: remove overflow-y-auto from the left side so it doesn't stretch and scroll
# <div className={`flex-1 space-y-2 flex flex-col ${isPortrait ? 'min-w-0 max-h-full overflow-y-auto custom-scrollbar pr-1' : ''}`}>
def replacer_wrap(m):
    return m.group(0).replace("overflow-y-auto custom-scrollbar pr-1", "overflow-y-auto custom-scrollbar")

new_block = new_block.replace("overflow-y-auto custom-scrollbar pr-1", "overflow-hidden pr-1 justify-center")

text = text[:start_idx] + new_block + text[end_idx:]

with open("frontend/src/pages/editor/components/ShotsView.jsx", "w", encoding="utf-8") as f:
    f.write(text)

print("Patching classes...")
