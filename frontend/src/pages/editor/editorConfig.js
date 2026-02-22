export const PROVIDER_LABELS = {
    image: {
        "Midjourney": "Midjourney",
        "Doubao": "Doubao (豆包 - Volcengine)",
        "Grsai-Image": "Grsai (Aggregation)",
        "DALL-E 3": "DALL-E 3",
        "Stable Diffusion": "Stable Diffusion (SDXL/Pony)",
        "Flux": "Flux.1",
        "Tencent Hunyuan": "Tencent Hunyuan (腾讯混元)"
    },
    video: {
        "Runway": "Runway Gen-2/Gen-3",
        "Luma": "Luma Dream Machine",
        "Kling": "Kling AI (可灵)",
        "Sora": "Sora (OpenAI)",
        "Grsai-Video": "Grsai (Standard)",
        "Grsai-Video (Upload)": "Grsai (File Upload)",
        "Stable Video": "Stable Video Component",
        "Doubao Video": "Doubao (豆包 - Volcengine)",
        "Wanxiang": "Wanxiang (通义万相 - Aliyun)",
        "Vidu (Video)": "Vidu (Shengshu)"
    }
};

export const MODEL_OPTIONS = {
    image: {
        "Midjourney": [
            { label: "Standard (v6.0)", value: "default" },
            { label: "Niji (Anime)", value: "niji" }
        ],
        "Stable Diffusion": [
            { label: "SDXL 1.0 (Stability)", value: "stable-diffusion-xl-1024-v1-0" },
            { label: "SD 1.6", value: "stable-diffusion-v1-6" },
            { label: "SD3 Large", value: "sd3-large" },
            { label: "SD3 Large Turbo", value: "sd3-large-turbo" }
        ],
        "DALL-E 3": [
            { label: "DALL-E 3 (High Quality)", value: "dall-e-3" }
        ],
        "Doubao": [
            { label: "Doubao Image (Seedream)", value: "doubao-seedream-4-5-251128" }
        ],
        "Tencent Hunyuan": [
            { label: "Hunyuan Vision", value: "hunyuan-vision" },
            { label: "Standard (201)", value: "201" }
        ],
        "Grsai-Image": [
            { label: "Sora Image", value: "sora-image" },
            { label: "GPT Image 1.5", value: "gpt-image-1.5" },
            { label: "Nano Banana Pro", value: "nano-banana-pro" },
            { label: "Nano Banana Pro VT", value: "nano-banana-pro-vt" },
            { label: "Nano Banana Fast", value: "nano-banana-fast" },
            { label: "Nano Banana Pro CL", value: "nano-banana-pro-cl" },
            { label: "Nano Banana Pro VIP", value: "nano-banana-pro-vip" },
            { label: "Nano Banana", value: "nano-banana" },
            { label: "Nano Banana Pro 4K VIP", value: "nano-banana-pro-4k-vip" }
        ],
        "Flux": [
            { label: "Flux.1 Pro", value: "flux-pro" },
            { label: "Flux.1 Dev", value: "flux-dev" },
            { label: "Flux.1 Schnell", value: "flux-schnell" }
        ]
    },
    video: {
        "Runway": [
            { label: "Gen-3 Alpha", value: "gen-3-alpha" },
            { label: "Gen-2 (Standard)", value: "gen-2" }
        ],
        "Luma": [
            { label: "Ray 2", value: "ray-2" },
            { label: "Ray 1.6", value: "ray-1-6" }
        ],
        "Kling": [
            { label: "Kling v1.0", value: "kling-v1" },
            { label: "Kling v1.5", value: "kling-v1-5" }
        ],
        "Sora": [
             { label: "Sora", value: "sora" }
        ],
        "Grsai-Video": [
            { label: "Sora Video", value: "sora-video" },
            { label: "Sora V2", value: "sora-2" },
            { label: "Luma Ray 2", value: "luma-ray-2" },
            { label: "Luma Ray 1-6", value: "luma-ray-1-6" },
            { label: "Runway Gen3", value: "runway-gen3" },
            { label: "Runway Gen3 Alpha", value: "runway-gen3-alpha" },
            { label: "Runway Gen2", value: "runway-gen2" },
            { label: "Kling v1", value: "kling-v1" },
            { label: "Kling v1.5", value: "kling-v1-5" },
            { label: "Minimax Video", value: "minimax-video" },
            { label: "CogVideoX", value: "cogvideox" },
            { label: "Hunyuan Video (Tencent)", value: "hunyuan-video" }
        ],
        "Grsai-Video (Upload)": [
             { label: "Default (Upload Mode)", value: "default-upload" }
        ],
        "Stable Video": [
             { label: "SVD 1.1", value: "svd-xt-1-1" }
        ],
        "Doubao Video": [
            { label: "Doubao Video", value: "doubao-vid-s-251128" },
            { label: "Doubao Video Pro", value: "doubao-seedance-1-5-pro-251215" }
        ],
        "Wanxiang": [
            { label: "WanX 2.1 (Image2Video)", value: "wanx2.1-i2v-plus" },
            { label: "WanX 2.1 (KeyFrame2Video)", value: "wanx2.1-kf2v-plus" },
            { label: "WanX 2.0 (Text2Video)", value: "wanx2.0-t2v-turbo" }
        ],
        "Vidu (Video)": [
             { label: "Vidu 2.0", value: "vidu2.0" }
        ]
    }
};

export const getSettingSourceByCategory = (settings, category) => {
    const active = (settings || []).find((item) => item?.category === category && item?.is_active);
    if (!active) return 'unset';
    if (active?.config?.selection_source === 'system' || active?.config?.use_system_setting_id) return 'system';
    return 'user';
};

export const sourceBadgeClass = (source) => {
    if (source === 'system') return 'bg-green-500/20 text-green-300 border-green-500/30';
    if (source === 'user') return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
    return 'bg-white/10 text-muted-foreground border-white/20';
};

export const sourceBadgeText = (source) => {
    if (source === 'system') return 'System';
    if (source === 'user') return 'User';
    return 'Unset';
};

export const formatProviderModelEndpointError = (err) => {
    const detail = err?.response?.data?.detail || err?.message || String(err || 'Unknown error');
    const providerMatch = String(detail).match(/provider=([^,\]]+)/i);
    const modelMatch = String(detail).match(/model=([^,\]]+)/i);
    const endpointMatch = String(detail).match(/endpoint=([^\]]+)/i);

    if (!providerMatch && !modelMatch && !endpointMatch) {
        return String(detail);
    }

    const provider = (providerMatch?.[1] || '').trim();
    const model = (modelMatch?.[1] || '').trim();
    const endpoint = (endpointMatch?.[1] || '').trim();
    const lines = [
        `Provider: ${provider || '-'}`,
        `Model: ${model || '-'}`,
        `Endpoint: ${endpoint || '-'}`,
    ];

    return `${lines.join('\n')}\n\nRaw: ${detail}`;
};
