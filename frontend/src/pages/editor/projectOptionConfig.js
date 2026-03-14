export const PROJECT_EP_TYPE_OPTIONS = [
    "实拍 / Live Action",
    "实拍（真人剧/电影感8K） / Live Action (Live-Action Drama/Cinematic 8K)",
    "二维动画 / 2D Animation",
    "三维动画 / 3D Animation",
    "定格动画 / Stop Motion",
    "特摄 / Tokusatsu",
    "舞台剧 / Stage Play",
    "CG动画 / CG Animation",
    "混合媒介 / Mixed Media",
    "纪录片 / Documentary",
    "商品宣传 / Product Promotion",
    "文旅宣传 / Cultural Tourism Promotion",
    "企业宣传 / Corporate Promotion",
];

export const PROJECT_EP_LANGUAGE_OPTIONS = [
    "中文 / Chinese",
    "英文 / English",
    "中英双语 / Bilingual (CN/EN)",
    "日语 / Japanese",
    "韩语 / Korean",
    "法语 / French",
    "西班牙语 / Spanish",
    "德语 / German",
    "其他 / Other",
];

export const PROJECT_EP_BASE_POSITIONING_OPTIONS = [
    "都市情感 / Urban Romance",
    "科幻冒险 / Sci-Fi Adventure",
    "悬疑惊悚 / Mystery / Thriller",
    "古装武侠 / Period / Wuxia",
    "奇幻史诗 / Fantasy Epic",
    "现代职场 / Modern Workplace",
    "校园青春 / High School / Youth",
    "赛博朋克 / Cyberpunk",
    "恐怖 / Horror",
    "喜剧 / Comedy",
    "剧情 / Drama",
    "动作 / Action",
    "历史 / Historical",
];

export const PROJECT_EP_GLOBAL_STYLE_OPTIONS = [
    "写实电影感，8k杰作 / Photorealistic, Cinematic Lighting, 8k, Masterpiece",
    "超写实人像，RAW质感，极致细节 / Hyperrealistic Portrait, RAW Photo, Ultra Detailed",
    "赛博朋克 / Cyberpunk",
    "极简主义 / Minimalist",
    "写实风格 / Photorealistic",
    "迪士尼风格 / Disney Style",
    "吉卜力风格 / Ghibli Style",
    "黑色电影 / Film Noir",
    "蒸汽朋克 / Steampunk",
    "水彩风格 / Watercolor",
    "油画风格 / Oil Painting",
    "像素艺术 / Pixel Art",
    "蒸汽波 / Vaporwave",
    "哥特风格 / Gothic",
    "超现实主义 / Surrealism",
];

export const PROJECT_EP_TONE_OPTIONS = [
    "冷色调 / Cool",
    "暖色调 / Warm",
    "中性色调 / Neutral",
    "高对比 / High Contrast",
    "暗调氛围 / Dark / Moody",
    "梦幻感 / Dreamy",
    "高饱和 / Vibrant",
    "去饱和 / Desaturated",
    "粉彩感 / Pastel",
    "粗粝感 / Gritty",
    "肤色优化 / Skin Tone Optimized",
    "胶片质感 / Film Presence",
    "低饱和色彩 / Muted Tones",
    "肤色优化，梦幻感 / Skin Tone Optimized, Dreamy",
    "胶片质感，低饱和 / Film Presence, Muted Tones",
    "中性，高对比 / Neutral, High Contrast",
    "暗调，粗粝感 / Dark / Moody, Gritty",
    "高饱和，高对比 / Vibrant, High Contrast",
];

export const PROJECT_EP_LIGHTING_OPTIONS = [
    "自然光 / Natural Light",
    "柔光 / Soft Light",
    "硬光 / Hard Light",
    "轮廓光 / Rim Light",
    "伦勃朗光 / Rembrandt",
    "霓虹赛博光 / Neon / Cyber",
    "电影光效 / Cinematic",
    "低调光 / Low Key",
    "高调光 / High Key",
    "体积光 / Volumetric",
    "蝴蝶光 / Butterfly Light",
    "棚拍光 / Studio Light",
    "黄金时刻 / Golden Hour",
    "窗光 / Window Light",
    "分割光 / Split Light",
    "蝴蝶光，柔光 / Butterfly Light, Soft Light",
    "伦勃朗光，体积光 / Rembrandt, Volumetric",
    "电影光，轮廓光，体积光 / Cinematic, Rim Light, Volumetric",
    "棚拍光，硬光 / Studio Light, Hard Light",
    "自然光，窗光 / Natural Light, Window Light",
];

export const PROJECT_EP_QUALITY_OPTIONS = [
    "超高 / Ultra High",
    "高 / High",
    "中 / Medium",
    "低 / Low",
    "草稿 / Draft",
];

const PROJECT_EP_TYPE_LEGACY_MAP = {
    "Live Action": "实拍 / Live Action",
    "Live Action (Realism/Cinematic 8K)": "实拍（真人剧/电影感8K） / Live Action (Live-Action Drama/Cinematic 8K)",
    "实拍（写实/电影感8K） / Live Action (Realism/Cinematic 8K)": "实拍（真人剧/电影感8K） / Live Action (Live-Action Drama/Cinematic 8K)",
    "Live Action (Live-Action Drama/Cinematic 8K)": "实拍（真人剧/电影感8K） / Live Action (Live-Action Drama/Cinematic 8K)",
    "2D Animation": "二维动画 / 2D Animation",
    "3D Animation": "三维动画 / 3D Animation",
    "Stop Motion": "定格动画 / Stop Motion",
    "Tokusatsu": "特摄 / Tokusatsu",
    "Stage Play": "舞台剧 / Stage Play",
    "CG Animation": "CG动画 / CG Animation",
    "Mixed Media": "混合媒介 / Mixed Media",
    "Documentary": "纪录片 / Documentary",
    "商品宣传": "商品宣传 / Product Promotion",
    "文旅宣传": "文旅宣传 / Cultural Tourism Promotion",
    "企业宣传": "企业宣传 / Corporate Promotion",
    "Product Promotion": "商品宣传 / Product Promotion",
    "Cultural Tourism Promotion": "文旅宣传 / Cultural Tourism Promotion",
    "Corporate Promotion": "企业宣传 / Corporate Promotion",
};

const PROJECT_EP_LANGUAGE_LEGACY_MAP = {
    "Chinese": "中文 / Chinese",
    "English": "英文 / English",
    "Bilingual (CN/EN)": "中英双语 / Bilingual (CN/EN)",
    "Japanese": "日语 / Japanese",
    "Korean": "韩语 / Korean",
    "French": "法语 / French",
    "Spanish": "西班牙语 / Spanish",
    "German": "德语 / German",
    "Other": "其他 / Other",
    "中文": "中文 / Chinese",
    "英文": "英文 / English",
    "中英双语": "中英双语 / Bilingual (CN/EN)",
    "日语": "日语 / Japanese",
    "韩语": "韩语 / Korean",
    "法语": "法语 / French",
    "西班牙语": "西班牙语 / Spanish",
    "德语": "德语 / German",
    "其他": "其他 / Other",
};

const PROJECT_EP_BASE_POSITIONING_LEGACY_MAP = {
    "Urban Romance": "都市情感 / Urban Romance",
    "Sci-Fi Adventure": "科幻冒险 / Sci-Fi Adventure",
    "Mystery / Thriller": "悬疑惊悚 / Mystery / Thriller",
    "Period / Wuxia": "古装武侠 / Period / Wuxia",
    "Fantasy Epic": "奇幻史诗 / Fantasy Epic",
    "Modern Workplace": "现代职场 / Modern Workplace",
    "High School / Youth": "校园青春 / High School / Youth",
    "Cyberpunk": "赛博朋克 / Cyberpunk",
    "Horror": "恐怖 / Horror",
    "Comedy": "喜剧 / Comedy",
    "Drama": "剧情 / Drama",
    "Action": "动作 / Action",
    "Historical": "历史 / Historical",
    "都市情感": "都市情感 / Urban Romance",
    "科幻冒险": "科幻冒险 / Sci-Fi Adventure",
    "悬疑惊悚": "悬疑惊悚 / Mystery / Thriller",
    "古装武侠": "古装武侠 / Period / Wuxia",
    "奇幻史诗": "奇幻史诗 / Fantasy Epic",
    "现代职场": "现代职场 / Modern Workplace",
    "校园青春": "校园青春 / High School / Youth",
    "赛博朋克": "赛博朋克 / Cyberpunk",
    "恐怖": "恐怖 / Horror",
    "喜剧": "喜剧 / Comedy",
    "剧情": "剧情 / Drama",
    "动作": "动作 / Action",
    "历史": "历史 / Historical",
};

const PROJECT_EP_GLOBAL_STYLE_LEGACY_MAP = {
    "Photorealistic, Cinematic Lighting, 8k, Masterpiece": "写实电影感，8k杰作 / Photorealistic, Cinematic Lighting, 8k, Masterpiece",
    "Hyperrealistic Portrait, RAW Photo, Ultra Detailed": "超写实人像，RAW质感，极致细节 / Hyperrealistic Portrait, RAW Photo, Ultra Detailed",
    "Cyberpunk": "赛博朋克 / Cyberpunk",
    "Minimalist": "极简主义 / Minimalist",
    "Photorealistic": "写实风格 / Photorealistic",
    "Disney Style": "迪士尼风格 / Disney Style",
    "Ghibli Style": "吉卜力风格 / Ghibli Style",
    "Film Noir": "黑色电影 / Film Noir",
    "Steampunk": "蒸汽朋克 / Steampunk",
    "Watercolor": "水彩风格 / Watercolor",
    "Oil Painting": "油画风格 / Oil Painting",
    "Pixel Art": "像素艺术 / Pixel Art",
    "Vaporwave": "蒸汽波 / Vaporwave",
    "Gothic": "哥特风格 / Gothic",
    "Surrealism": "超现实主义 / Surrealism",
};

const PROJECT_EP_TONE_LEGACY_MAP = {
    "Cool": "冷色调 / Cool",
    "Warm": "暖色调 / Warm",
    "Neutral": "中性色调 / Neutral",
    "High Contrast": "高对比 / High Contrast",
    "Dark / Moody": "暗调氛围 / Dark / Moody",
    "Dreamy": "梦幻感 / Dreamy",
    "Vibrant": "高饱和 / Vibrant",
    "Desaturated": "去饱和 / Desaturated",
    "Pastel": "粉彩感 / Pastel",
    "Gritty": "粗粝感 / Gritty",
    "Skin Tone Optimized": "肤色优化 / Skin Tone Optimized",
    "Film Presence": "胶片质感 / Film Presence",
    "Muted Tones": "低饱和色彩 / Muted Tones",
    "Skin Tone Optimized, Dreamy": "肤色优化，梦幻感 / Skin Tone Optimized, Dreamy",
    "Film Presence, Muted Tones": "胶片质感，低饱和 / Film Presence, Muted Tones",
    "Neutral, High Contrast": "中性，高对比 / Neutral, High Contrast",
    "Dark / Moody, Gritty": "暗调，粗粝感 / Dark / Moody, Gritty",
    "Vibrant, High Contrast": "高饱和，高对比 / Vibrant, High Contrast",
};

const PROJECT_EP_LIGHTING_LEGACY_MAP = {
    "Natural Light": "自然光 / Natural Light",
    "Soft Light": "柔光 / Soft Light",
    "Hard Light": "硬光 / Hard Light",
    "Rim Light": "轮廓光 / Rim Light",
    "Rembrandt": "伦勃朗光 / Rembrandt",
    "Neon / Cyber": "霓虹赛博光 / Neon / Cyber",
    "Cinematic": "电影光效 / Cinematic",
    "Low Key": "低调光 / Low Key",
    "High Key": "高调光 / High Key",
    "Volumetric": "体积光 / Volumetric",
    "Butterfly Light": "蝴蝶光 / Butterfly Light",
    "Studio Light": "棚拍光 / Studio Light",
    "Golden Hour": "黄金时刻 / Golden Hour",
    "Window Light": "窗光 / Window Light",
    "Split Light": "分割光 / Split Light",
    "Butterfly Light, Soft Light": "蝴蝶光，柔光 / Butterfly Light, Soft Light",
    "Rembrandt, Volumetric": "伦勃朗光，体积光 / Rembrandt, Volumetric",
    "Cinematic, Rim Light, Volumetric": "电影光，轮廓光，体积光 / Cinematic, Rim Light, Volumetric",
    "Studio Light, Hard Light": "棚拍光，硬光 / Studio Light, Hard Light",
    "Natural Light, Window Light": "自然光，窗光 / Natural Light, Window Light",
};

const PROJECT_EP_QUALITY_LEGACY_MAP = {
    "Ultra High": "超高 / Ultra High",
    "High": "高 / High",
    "Medium": "中 / Medium",
    "Low": "低 / Low",
    "Draft": "草稿 / Draft",
    "超高": "超高 / Ultra High",
    "高": "高 / High",
    "中": "中 / Medium",
    "低": "低 / Low",
    "草稿": "草稿 / Draft",
};

export const normalizeProjectEpisodeType = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return raw;
    if (PROJECT_EP_TYPE_OPTIONS.includes(raw)) return raw;
    return PROJECT_EP_TYPE_LEGACY_MAP[raw] || raw;
};

export const normalizeProjectEpisodeLanguage = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return raw;
    if (PROJECT_EP_LANGUAGE_OPTIONS.includes(raw)) return raw;
    return PROJECT_EP_LANGUAGE_LEGACY_MAP[raw] || raw;
};

export const normalizeProjectEpisodeBasePositioning = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return raw;
    if (PROJECT_EP_BASE_POSITIONING_OPTIONS.includes(raw)) return raw;
    return PROJECT_EP_BASE_POSITIONING_LEGACY_MAP[raw] || raw;
};

export const normalizeProjectEpisodeGlobalStyle = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return raw;
    if (PROJECT_EP_GLOBAL_STYLE_OPTIONS.includes(raw)) return raw;
    return PROJECT_EP_GLOBAL_STYLE_LEGACY_MAP[raw] || raw;
};

export const normalizeProjectEpisodeTone = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return raw;
    if (PROJECT_EP_TONE_OPTIONS.includes(raw)) return raw;
    return PROJECT_EP_TONE_LEGACY_MAP[raw] || raw;
};

export const normalizeProjectEpisodeLighting = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return raw;
    if (PROJECT_EP_LIGHTING_OPTIONS.includes(raw)) return raw;
    return PROJECT_EP_LIGHTING_LEGACY_MAP[raw] || raw;
};

export const normalizeProjectEpisodeQuality = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return raw;
    if (PROJECT_EP_QUALITY_OPTIONS.includes(raw)) return raw;
    return PROJECT_EP_QUALITY_LEGACY_MAP[raw] || raw;
};
