import re

with open('c:/AIStory/frontend/src/services/api.js', 'r', encoding='utf-8') as f:
    text = f.read()

def_video = '''export const generateVideo = async (prompt, provider = null, ref_image_url = null, ref_video_urls = null, last_frame_url = null, duration = 5, options = {}, keyframes = [], negative_prompt = null) => {
    const effectiveNegativePrompt = String(negative_prompt ?? options?.negative_prompt ?? '').trim();
    const {
        job_timeout_ms,
        job_poll_interval_ms,
        on_job_created,
        ...requestOptions
    } = options || {};'''

new_video = '''export const generateVideo = async (prompt, provider = null, ref_image_url = null, ref_video_urls = null, last_frame_url = null, duration = 5, options = {}, keyframes = [], negative_prompt = null) => {
    const effectiveNegativePrompt = String(negative_prompt ?? options?.negative_prompt ?? '').trim();
    
    let {
        job_timeout_ms,
        job_poll_interval_ms,
        on_job_created,
        ...requestOptions
    } = options || {};

    if (requestOptions.function_name) {
        requestOptions.system_api_id = Number(localStorage.getItem('func_api_' + requestOptions.function_name)) || null;
    }'''

text = text.replace(def_video, new_video)

with open('c:/AIStory/frontend/src/services/api.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("patched api.js")
