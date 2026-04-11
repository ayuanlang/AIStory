import sys
import re

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'

# First, restore ShotsView to a pristine state so regexes match perfectly
import subprocess
subprocess.run(['git', 'checkout', file_path])

with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. AnimatePresence wrapper and isPortrait calculation
p1_old = '''             <AnimatePresence>
                {editingShot && (() => {
                    const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || '16:9';
                    const aspectParts = parseAspectRatioParts(preferredAspectRatio);
                    const isPortrait = aspectParts && aspectParts.heightPart > aspectParts.widthPart;
                    const mediaAspectStyle = isPortrait ? { aspectRatio: `${aspectParts.widthPart}/${aspectParts.heightPart}` } : undefined;
                    return (
                    <motion.div'''
p1_new = '''             <AnimatePresence>
                {editingShot && (() => {
                    const preferredAspectRatio = getProjectPreferredAspectRatio(project?.global_info, activeEpisode?.episode_info) || "16:9";
                    const aspectParts = parseAspectRatioParts(preferredAspectRatio) || { widthPart: 16, heightPart: 9 };
                    const isPortrait = aspectParts.heightPart > aspectParts.widthPart;
                    const mediaAspectStyle = isPortrait ? { aspectRatio: aspectParts.widthPart + "/" + aspectParts.heightPart } : undefined;
                    return (
                    <motion.div'''
text = text.replace(p1_old, p1_new)
text = text.replace("const aspectParts = parseAspectRatioParts(preferredAspectRatio);\n                    const isPortrait = aspectParts && aspectParts[1] > aspectParts[0];\n                    const mediaAspectStyle = isPortrait ? { aspectRatio: `${aspectParts[0]}/${aspectParts[1]}` } : undefined;", "const aspectParts = parseAspectRatioParts(preferredAspectRatio) || { widthPart: 16, heightPart: 9 };\n                    const isPortrait = aspectParts.heightPart > aspectParts.widthPart;\n                    const mediaAspectStyle = isPortrait ? { aspectRatio: aspectParts.widthPart + '/' + aspectParts.heightPart } : undefined;")

# We need to change the grid columns from generic space-y-6 to the grid array
p_grid_old = '''                                {/* 3 Column Layout: Start | End | Video */}
                                <div className="space-y-6">'''
p_grid_new = '''                                {/* 3 Column Layout: Start | End | Video */}
                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">'''
text = text.replace(p_grid_old, p_grid_new)

# --- START FRAME ---
start_search = r'(<div className=\"space-y-2\">\s*<div className=\"flex min-h-\[52px\].*?</div>\s*<div.*?onClick=\{\(\) => openAssetDetailModal\(\'start\'\)\}>.*?</button>\s*</>\s*\)\s*:\s*\(\s*<div.*?</ImageIcon></div>\s*\)\}\s*</div>)\s*(<PromptMentionTextarea.*?/>)\s*</div>\s*<div>\s*(<ReferenceManager.*?>)\s*</div>'

def start_repl(m):
    media_and_header = m.group(1)
    prompt = m.group(2)
    ref_mgr = m.group(3)
    # The reference manager should have isPortrait
    ref_mgr = ref_mgr.replace('title={t(\'参考图（起始帧）\', \'Refs (Start)\')}', 'title={t(\'参考图（起始帧）\', \'Refs (Start)\')} isPortrait={isPortrait}')
    return f'''
<div className="space-y-2">
    <div className={{isPortrait ? "flex flex-row gap-2 items-start" : "space-y-2"}}>
        <div className={{isPortrait ? "w-[45%] shrink-0 space-y-2" : "w-full space-y-2"}}>
            {media_and_header}
        </div>
        <div className={{isPortrait ? "w-[55%] shrink-0" : "w-full hidden"}}>
            {ref_mgr}</div>
    </div>
    <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
        {ref_mgr}</div>
    <div className="mt-2">
        {prompt}
    </div>
</div>'''

text = re.sub(start_search, start_repl, text, flags=re.DOTALL)

# --- END FRAME ---
end_search = r'(<div className=\"space-y-2\">\s*<div className=\"flex min-h-\[52px\].*?</div>\s*<div.*?onClick=\{\(\) => openAssetDetailModal\(\'end\'\)\}>.*?</button>\s*</>\s*\)\s*:\s*\(\s*<div.*?</ImageIcon></div>\s*\)\}\s*</div>)\s*(<PromptMentionTextarea.*?/>)\s*</div>\s*<div>\s*(<ReferenceManager.*?>)\s*</div>'

def end_repl(m):
    media_and_header = m.group(1)
    prompt = m.group(2)
    ref_mgr = m.group(3)
    ref_mgr = ref_mgr.replace('title={t(\'参考图（结束帧）\', \'Refs (End)\')}', 'title={t(\'参考图（结束帧）\', \'Refs (End)\')} isPortrait={isPortrait}')
    return f'''
<div className="space-y-2">
    <div className={{isPortrait ? "flex flex-row gap-2 items-start" : "space-y-2"}}>
        <div className={{isPortrait ? "w-[45%] shrink-0 space-y-2" : "w-full space-y-2"}}>
            {media_and_header}
        </div>
        <div className={{isPortrait ? "w-[55%] shrink-0" : "w-full hidden"}}>
            {ref_mgr}</div>
    </div>
    <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
        {ref_mgr}</div>
    <div className="mt-2">
        {prompt}
    </div>
</div>'''

text = re.sub(end_search, end_repl, text, flags=re.DOTALL)

# --- VIDEO FRAME (Keyframes & Video) ---
video_search = r'(<div className=\"space-y-2\">\s*<div className=\"flex min-h-\[52px\].*?</div>\s*<div className=\"flex gap-2 overflow-x-auto pb-2 custom-scrollbar\".*?</LazyHoverVideo>\s*\)\s*:\s*\(\s*<div.*?</VideoIcon></div>\s*\)\}\s*</div>\s*<div.*?</div>\s*</div>)\s*(<PromptMentionTextarea.*?/>)\s*</div>\s*<div className.*?>\s*(<ReferenceManager.*?>)\s*</div>'

def video_repl(m):
    media_and_header = m.group(1)
    prompt = m.group(2)
    ref_mgr = m.group(3)
    # The reference manager should have isPortrait
    ref_mgr = ref_mgr.replace('title={t(\'参考图（实体）\', \'Refs (Entity)\')}', 'title={t(\'参考图（实体）\', \'Refs (Entity)\')} isPortrait={isPortrait}')
    return f'''
<div className="space-y-2">
    <div className={{isPortrait ? "flex flex-row gap-2 items-start" : "space-y-2"}}>
        <div className={{isPortrait ? "w-[45%] shrink-0 space-y-2" : "w-full space-y-2"}}>
            {media_and_header}
        </div>
        <div className={{isPortrait ? "w-[55%] shrink-0" : "w-full hidden"}}>
            {ref_mgr}</div>
    </div>
    <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
        {ref_mgr}</div>
    <div className="mt-2">
        {prompt}
    </div>
</div>'''

text = re.sub(video_search, video_repl, text, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Layout restructuring completely applied")
