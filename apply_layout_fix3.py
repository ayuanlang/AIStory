import sys
import re

file_path = 'c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Start Frame Block
# We split by 'openAssetDetailModal('start')}>' up to the matching PromptMentionTextarea

def patch_block(text, open_modal_marker):
    parts = text.split(open_modal_marker)
    if len(parts) < 2: return text
    
    # Target string is:
    # <div style={mediaAspectStyle} className={`bg-black rounded border relative group overflow... ${!isPortrait ? ...} ...`} onClick={() => openAssetDetailModal('start')}>
    
    # We find the start of the <div style={mediaAspectStyle} that corresponds to this marker
    pre_marker = parts[0]
    start_idx = pre_marker.rfind('<div style={mediaAspectStyle}')
    if start_idx == -1: return text

    post_marker = parts[1]
    
    # Find the PromptMentionTextarea in post_marker
    prompt_start_idx = post_marker.find('<PromptMentionTextarea')
    if prompt_start_idx == -1: return text
    
    # We need to find the matching closing div for the media block before the prompt textarea
    media_block = pre_marker[start_idx:] + open_modal_marker + post_marker[:prompt_start_idx]
    
    rest_after_media = post_marker[prompt_start_idx:]
    
    # Find the end of <PromptMentionTextarea /> in rest_after_media
    prompt_end_idx = rest_after_media.find('/>') + 2
    prompt_block = rest_after_media[:prompt_end_idx]
    
    rest_after_prompt = rest_after_media[prompt_end_idx:]
    # Structure after prompt is:
    # </div>
    # <div>
    # <ReferenceManager ... />
    
    ref_mgr_start_idx = rest_after_prompt.find('<ReferenceManager')
    if ref_mgr_start_idx == -1: return text
    
    # find where ReferenceManager ends
    ref_mgr_end_idx = rest_after_prompt.find('/>', ref_mgr_start_idx) + 2
    ref_mgr_block = rest_after_prompt[ref_mgr_start_idx:ref_mgr_end_idx]
    
    rest_after_ref_mgr = rest_after_prompt[ref_mgr_end_idx:]
    # find the next </div>
    end_div_idx = rest_after_ref_mgr.find('</div>') + 6
    
    # Complete replacement
    return pre_marker[:start_idx] + f'''
                                        <div className={{isPortrait ? "flex flex-row gap-2 h-[260px]" : "space-y-2"}}>
                                            <div className={{isPortrait ? "w-[50%] shrink-0 h-full" : "w-full"}}>
{media_block}
                                            </div>
                                            <div className={{isPortrait ? "w-[50%] shrink-0 h-full" : "w-full hidden"}}>
                                                {ref_mgr_block}
                                            </div>
                                        </div>
                                        <div className={{!isPortrait ? "w-full" : "w-full hidden"}}>
                                            {ref_mgr_block}
                                        </div>
                                        {prompt_block}
    ''' + rest_after_ref_mgr[end_div_idx:]

# Process start frame
text = patch_block(text, "onClick={() => openAssetDetailModal('start')}>")

# Process end frame
text = patch_block(text, "onClick={() => openAssetDetailModal('end')}>")

# Process video frame
text = patch_block(text, "onClick={() => openAssetDetailModal('video')}>")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied side-by-side reference layout!")
