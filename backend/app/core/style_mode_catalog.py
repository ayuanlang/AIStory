# -*- coding: utf-8 -*-
"""基础风格模式（Style Mode）闭集。与 frontend styleModeCatalog.js 同核。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

STYLE_MODE_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "contemporary_urban",
        "label": "当代都市 / Contemporary Urban",
        "visual_key": "当代",
        "temperament": "都市",
        "global_style": "视觉基调=当代｜气质=都市｜影像质感=干净可读的当代城市影像，玻璃幕墙与街道反光克制｜落点=日常建材、交通灯色、窗光与路灯分层、少霓虹堆砌",
        "lighting": "自然光，窗光 / Natural Light, Window Light",
        "tone": "中性，高对比 / Neutral, High Contrast",
        "color_spectrum": "同温层次",
        "borrowed_films": ["她", "寄生虫"],
    },
    {
        "id": "period_retro",
        "label": "年代复古 / Period Retro",
        "visual_key": "年代",
        "temperament": "民俗",
        "global_style": "视觉基调=年代｜气质=民俗｜影像质感=胶片颗粒与过期色彩，旧灯具与织物质地可读｜落点=年代家具、暖钨丝、褪色海报、街道招牌旧漆",
        "lighting": "黄金时刻，窗光 / Golden Hour, Window Light",
        "tone": "胶片质感，低饱和 / Film Presence, Muted Tones",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["阳光灿烂的日子", "天堂电影院"],
    },
    {
        "id": "republican_modern",
        "label": "民国摩登 / Republican Modern",
        "visual_key": "复古",
        "temperament": "精致",
        "global_style": "视觉基调=复古｜气质=精致｜影像质感=海派摩登与旧上海灯色，旗袍面料与石库门砖墙｜落点=铜灯、雨巷青石、报纸油墨、舞厅暖金",
        "lighting": "低调光，窗光 / Low Key, Window Light",
        "tone": "暖色调 / Warm",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["色，戒", "风声"],
    },
    {
        "id": "imperial_court",
        "label": "古典宫廷 / Imperial Court",
        "visual_key": "古典/古装",
        "temperament": "奢华",
        "global_style": "视觉基调=古典/古装｜气质=奢华｜影像质感=殿宇轴线与礼制等级可见，金铜木石分层｜落点=藻井、丹陛、仪仗色、烛火与窗格光",
        "lighting": "电影光，轮廓光，体积光 / Cinematic, Rim Light, Volumetric",
        "tone": "暖色调 / Warm",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["满城尽带黄金甲", "末代皇帝"],
    },
    {
        "id": "ancient_war",
        "label": "古装战争 / Ancient War",
        "visual_key": "古典/古装",
        "temperament": "粗粝",
        "global_style": "视觉基调=古典/古装｜气质=粗粝｜影像质感=甲胄尘土与旗阵规模，战场烟霭压过妆面光｜落点=铠甲反光、马蹄扬尘、多面军旗、营火与铁器冷光",
        "lighting": "硬光，低调光 / Hard Light, Low Key",
        "tone": "暗调，粗粝感 / Dark / Moody, Gritty",
        "color_spectrum": "冷暖对比",
        "borrowed_films": ["赤壁", "勇敢的心"],
    },
    {
        "id": "wuxia_jianghu",
        "label": "武侠江湖 / Wuxia Jianghu",
        "visual_key": "古典/古装",
        "temperament": "粗粝",
        "global_style": "视觉基调=古典/古装｜气质=粗粝｜影像质感=客栈雨巷与刃光，布衣侠气压过宫廷金碧｜落点=竹林雾、湿石台阶、酒旗、剑穗与斗笠轮廓",
        "lighting": "自然光，体积光 / Natural Light, Volumetric",
        "tone": "低饱和色彩 / Muted Tones",
        "color_spectrum": "同温层次",
        "borrowed_films": ["卧虎藏龙", "英雄"],
    },
    {
        "id": "xianxia_cultivation",
        "label": "仙侠修真 / Xianxia Cultivation",
        "visual_key": "奇幻",
        "temperament": "精致",
        "global_style": "视觉基调=奇幻｜气质=精致｜影像质感=云海宗门与法光点缀，空灵但不退成水墨灰糊｜落点=飞檐仙府、剑光、雾霭层云、玉石与丝绸反光",
        "lighting": "体积光，轮廓光 / Volumetric, Rim Light",
        "tone": "梦幻感 / Dreamy",
        "color_spectrum": "冷暖对比",
        "borrowed_films": ["倩女幽魂", "蜀山传"],
    },
    {
        "id": "eastern_fantasy",
        "label": "东方奇幻 / Eastern Fantasy",
        "visual_key": "奇幻",
        "temperament": "精致",
        "global_style": "视觉基调=奇幻｜气质=精致｜影像质感=神魔尺度与礼器纹样，奇观落在可核销材质上｜落点=神兽鳞甲、殿阙异观、符箓光、巨物尺度参照",
        "lighting": "电影光，体积光 / Cinematic, Volumetric",
        "tone": "高饱和，高对比 / Vibrant, High Contrast",
        "color_spectrum": "冷暖对比",
        "borrowed_films": ["哪吒之魔童降世", "大闹天宫"],
    },
    {
        "id": "western_medieval",
        "label": "西洋中世纪 / Western Medieval",
        "visual_key": "古典/古装",
        "temperament": "粗粝",
        "global_style": "视觉基调=古典/古装｜气质=粗粝｜影像质感=石堡泥路与锁子甲，火把烟炱压过童话亮色｜落点=城垛、纹章旗、铁器磨损、大厅梁架",
        "lighting": "低调光，硬光 / Low Key, Hard Light",
        "tone": "暗调，粗粝感 / Dark / Moody, Gritty",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["角斗士", "指环王"],
    },
    {
        "id": "western_court",
        "label": "西洋宫廷 / Western Court",
        "visual_key": "古典/古装",
        "temperament": "奢华",
        "global_style": "视觉基调=古典/古装｜气质=奢华｜影像质感=巴洛克金饰与缎面层叠，烛火与镜廊纵深｜落点=吊灯水晶、锦缎墙、宫廷假发、大理石地面",
        "lighting": "伦勃朗光，体积光 / Rembrandt, Volumetric",
        "tone": "暖色调 / Warm",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["绝代艳后", "绝代王后"],
    },
    {
        "id": "western_frontier",
        "label": "西部拓荒 / Western Frontier",
        "visual_key": "乡野",
        "temperament": "粗粝",
        "global_style": "视觉基调=乡野｜气质=粗粝｜影像质感=沙金日光与木板镇街，尘土与皮革耐磨｜落点=宽檐帽影、马具、风干木纹、地平线负空间",
        "lighting": "硬光，黄金时刻 / Hard Light, Golden Hour",
        "tone": "暖色调 / Warm",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["荒野大镖客", "复仇"],
    },
    {
        "id": "cyberpunk",
        "label": "赛博朋克 / Cyberpunk",
        "visual_key": "赛博",
        "temperament": "粗粝",
        "global_style": "视觉基调=赛博｜气质=粗粝｜影像质感=湿沥青夜雨与霓虹层叠，高楼峡谷压人｜落点=电青招牌、蒸汽排口、机能服、全息界面反光",
        "lighting": "霓虹赛博光 / Neon / Cyber",
        "tone": "高对比 / High Contrast",
        "color_spectrum": "冷暖对比",
        "borrowed_films": ["银翼杀手2049", "攻壳机动队"],
    },
    {
        "id": "near_future_tech",
        "label": "近未来科技 / Near-Future Tech",
        "visual_key": "近未来",
        "temperament": "精致",
        "global_style": "视觉基调=近未来｜气质=精致｜影像质感=克制科幻，白瓷与拉丝金属多于霓虹｜落点=无缝面板、柔和界面光、干净实验室、城市天际线微未来",
        "lighting": "柔光，棚拍光 / Soft Light, Studio Light",
        "tone": "冷色调 / Cool",
        "color_spectrum": "冷调主导",
        "borrowed_films": ["她", "降临"],
    },
    {
        "id": "space_opera",
        "label": "太空歌剧 / Space Opera",
        "visual_key": "近未来",
        "temperament": "奢华",
        "global_style": "视觉基调=近未来｜气质=奢华｜影像质感=舰桥尺度与星海纵深，舱内实用光与舷窗外星体｜落点=舰体蒙皮、舷窗星光、制服徽识、零重力系绳",
        "lighting": "电影光，轮廓光，体积光 / Cinematic, Rim Light, Volumetric",
        "tone": "冷色调 / Cool",
        "color_spectrum": "冷暖对比",
        "borrowed_films": ["星际穿越", "沙丘"],
    },
    {
        "id": "steampunk",
        "label": "蒸汽朋克 / Steampunk",
        "visual_key": "工业",
        "temperament": "精致",
        "global_style": "视觉基调=工业｜气质=精致｜影像质感=黄铜齿轮与蒸汽阀，维多利亚裁剪叠机械｜落点=压力表、铆接锅炉、护目镜、暖雾蒸汽",
        "lighting": "黄金时刻，体积光 / Golden Hour, Volumetric",
        "tone": "暖色调 / Warm",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["地狱男爵", "时光机器"],
    },
    {
        "id": "industrial_wasteland",
        "label": "工业废土 / Industrial Wasteland",
        "visual_key": "工业",
        "temperament": "粗粝",
        "global_style": "视觉基调=工业｜气质=粗粝｜影像质感=锈蚀厂房与钠灯，混凝土与油污克制可读｜落点=管道、铁网、地面积水、工作灯锥光",
        "lighting": "硬光，低调光 / Hard Light, Low Key",
        "tone": "暗调，粗粝感 / Dark / Moody, Gritty",
        "color_spectrum": "冷调主导",
        "borrowed_films": ["七宗罪", "老无所依"],
    },
    {
        "id": "post_apocalyptic",
        "label": "后启示录 / Post-Apocalyptic",
        "visual_key": "工业",
        "temperament": "粗粝",
        "global_style": "视觉基调=工业｜气质=粗粝｜影像质感=沙尘天光与废墟剪影，存活痕迹压过堆破烂｜落点=褪色漆面、改装载具、滤尘天空、稀少绿意",
        "lighting": "硬光，自然光 / Hard Light, Natural Light",
        "tone": "去饱和 / Desaturated",
        "color_spectrum": "同温层次",
        "borrowed_films": ["疯狂的麦克斯：狂暴之路", "末日危城"],
    },
    {
        "id": "rural_folk",
        "label": "乡野民俗 / Rural Folk",
        "visual_key": "乡野",
        "temperament": "民俗",
        "global_style": "视觉基调=乡野｜气质=民俗｜影像质感=田埂天光与土墙织布，节气可见｜落点=泥路、晒场、灶火、土布与木器包浆",
        "lighting": "自然光，黄金时刻 / Natural Light, Golden Hour",
        "tone": "暖色调 / Warm",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["黄土地", "秋菊打官司"],
    },
    {
        "id": "film_noir",
        "label": "黑色电影 / Film Noir",
        "visual_key": "当代",
        "temperament": "粗粝",
        "global_style": "视觉基调=当代｜气质=粗粝｜影像质感=硬阴影与湿街反光，脸半没入暗部仍可读｜落点=百叶窗影、雨夜沥青、烟与轮廓光、低饱和皮肤",
        "lighting": "低调光，分割光 / Low Key, Split Light",
        "tone": "暗调氛围 / Dark / Moody",
        "color_spectrum": "冷调主导",
        "borrowed_films": ["七宗罪", "唐人街"],
    },
    {
        "id": "mystery_thriller",
        "label": "悬疑惊悚 / Mystery Thriller",
        "visual_key": "当代",
        "temperament": "精致",
        "global_style": "视觉基调=当代｜气质=精致｜影像质感=冷青压迫与负空间，信息藏在暗层｜落点=走廊纵深、实用灯孤岛、玻璃倒映、克制手持",
        "lighting": "低调光，轮廓光 / Low Key, Rim Light",
        "tone": "冷色调 / Cool",
        "color_spectrum": "冷调主导",
        "borrowed_films": ["消失的爱人", "囚徒"],
    },
    {
        "id": "gothic_horror",
        "label": "哥特恐怖 / Gothic Horror",
        "visual_key": "复古",
        "temperament": "粗粝",
        "global_style": "视觉基调=复古｜气质=粗粝｜影像质感=石廊烛火与深暗丝绒，恐怖压暗仍须动机光可读｜落点=尖拱、锈铁栏、雾廊、孤烛半影",
        "lighting": "低调光，体积光 / Low Key, Volumetric",
        "tone": "暗调，粗粝感 / Dark / Moody, Gritty",
        "color_spectrum": "冷调主导",
        "borrowed_films": ["闪灵", "猩红山峰"],
    },
    {
        "id": "modern_warfare",
        "label": "现代战争 / Modern Warfare",
        "visual_key": "现代",
        "temperament": "粗粝",
        "global_style": "视觉基调=现代｜气质=粗粝｜影像质感=战术尘土与军绿装备，日光硬切或夜视克制｜落点=多面军旗、防弹插板、扬尘、曳光与掩体阴影",
        "lighting": "硬光，自然光 / Hard Light, Natural Light",
        "tone": "去饱和 / Desaturated",
        "color_spectrum": "同温层次",
        "borrowed_films": ["拯救大兵瑞恩", "黑鹰坠落"],
    },
    {
        "id": "documentary_realism",
        "label": "纪录片纪实 / Documentary Realism",
        "visual_key": "当代",
        "temperament": "无",
        "global_style": "视觉基调=当代｜气质=无｜影像质感=观察式现场光，少修饰、纹理保留｜落点=现有灯具、环境声画同步感、少人为布光痕迹",
        "lighting": "自然光 / Natural Light",
        "tone": "中性色调 / Neutral",
        "color_spectrum": "同温层次",
        "borrowed_films": ["地球之盐", "华氏911"],
    },
    {
        "id": "minimal_contemporary",
        "label": "极简当代 / Minimal Contemporary",
        "visual_key": "当代",
        "temperament": "极简",
        "global_style": "视觉基调=当代｜气质=极简｜影像质感=大面积留白与几何墙面，少陈设仍可读｜落点=单色墙、一条光带、一件家具锚、负空间",
        "lighting": "柔光，窗光 / Soft Light, Window Light",
        "tone": "低饱和色彩 / Muted Tones",
        "color_spectrum": "同温层次",
        "borrowed_films": ["完美日子", "花样年华"],
    },
    {
        "id": "luxury_metropolis",
        "label": "奢华都会 / Luxury Metropolis",
        "visual_key": "当代",
        "temperament": "奢华",
        "global_style": "视觉基调=当代｜气质=奢华｜影像质感=酒店大堂与夜景天际，石材金属玻璃高完成度｜落点=落地窗夜景、鎏金点缀、大理石倒影、定制灯具",
        "lighting": "电影光效 / Cinematic",
        "tone": "高饱和 / Vibrant",
        "color_spectrum": "冷暖对比",
        "borrowed_films": ["了不起的盖茨比", "华尔街之狼"],
    },
    {
        "id": "romance_gloss",
        "label": "浪漫爱情 / Romance Gloss",
        "visual_key": "当代",
        "temperament": "精致",
        "global_style": "视觉基调=当代｜气质=精致｜影像质感=肤色友好与柔金轮廓，雨雾与窗纱作气氛｜落点=暖窗、花材、织物层、眼神光可读",
        "lighting": "黄金时刻，柔光 / Golden Hour, Soft Light",
        "tone": "肤色优化，梦幻感 / Skin Tone Optimized, Dreamy",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["爱在黎明破晓前", "爱乐之城"],
    },
    {
        "id": "campus_youth",
        "label": "校园青春 / Campus Youth",
        "visual_key": "当代",
        "temperament": "都市",
        "global_style": "视觉基调=当代｜气质=都市｜影像质感=教室天光与操场尘金，年轻肤色与校服色块｜落点=课桌行列、走廊窗、操场线、书包与球网",
        "lighting": "自然光，窗光 / Natural Light, Window Light",
        "tone": "暖色调 / Warm",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["那些年，我们一起追的女孩", "请以你的名字呼唤我"],
    },
    {
        "id": "mythic_epic",
        "label": "神话史诗 / Mythic Epic",
        "visual_key": "奇幻",
        "temperament": "奢华",
        "global_style": "视觉基调=奇幻｜气质=奢华｜影像质感=神殿尺度与天象，金石与云海分层｜落点=巨柱、祭火、神器辉光、人神体量差",
        "lighting": "体积光，黄金时刻 / Volumetric, Golden Hour",
        "tone": "高饱和，高对比 / Vibrant, High Contrast",
        "color_spectrum": "冷暖对比",
        "borrowed_films": ["诸神之战", "天国王朝"],
    },
    {
        "id": "ink_wash",
        "label": "水墨写意 / Ink-Wash Classical",
        "visual_key": "古典/古装",
        "temperament": "极简",
        "global_style": "视觉基调=古典/古装｜气质=极简｜影像质感=留白与墨晕层次，山石树木可检索笔势｜落点=宣纸底、淡墨远山、一点朱红印、少堆彩",
        "lighting": "柔光 / Soft Light",
        "tone": "去饱和 / Desaturated",
        "color_spectrum": "同温层次",
        "borrowed_films": ["山水情", "侠隐"],
    },
    {
        "id": "ghibli_pastoral",
        "label": "吉卜力田园 / Ghibli Pastoral",
        "visual_key": "乡野",
        "temperament": "精致",
        "global_style": "视觉基调=乡野｜气质=精致｜影像质感=手绘田园空气透视，暖绿与天空层次｜落点=风吹草、云团、木屋炊烟、生活器物圆润",
        "lighting": "自然光，黄金时刻 / Natural Light, Golden Hour",
        "tone": "暖色调 / Warm",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["龙猫", "哈尔的移动城堡"],
    },
    {
        "id": "disney_fantasy",
        "label": "迪士尼奇幻 / Disney Fantasy",
        "visual_key": "奇幻",
        "temperament": "精致",
        "global_style": "视觉基调=奇幻｜气质=精致｜影像质感=舞台化清晰造型与高可读色彩，奇观仍落地材质｜落点=角色剪影、城堡天际、魔法点缀、歌曲场面光",
        "lighting": "高调光，电影光效 / High Key, Cinematic",
        "tone": "高饱和 / Vibrant",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["冰雪奇缘", "狮子王"],
    },
    {
        "id": "transmigration",
        "label": "穿越 / Transmigration",
        "visual_key": "当代",
        "temperament": "精致",
        "global_style": "视觉基调=当代｜气质=精致｜影像质感=今世与前世两套世界视觉可对读，穿越切口用光色/材质差而不靠字幕说明｜落点=现代日常锚、古装或异世对照、门阈/镜面/时间信物",
        "lighting": "窗光，黄金时刻 / Window Light, Golden Hour",
        "tone": "中性，高对比 / Neutral, High Contrast",
        "color_spectrum": "冷暖对比",
        "borrowed_films": ["夏洛特烦恼", "前世今生"],
    },
    {
        "id": "comedy_light",
        "label": "喜剧轻快 / Comedy / Light",
        "visual_key": "当代",
        "temperament": "都市",
        "global_style": "视觉基调=当代｜气质=都市｜影像质感=明亮可读、少压暗，笑点靠表演与空间错位而非脏乱堆料｜落点=干净室内、软彩点缀、窗光明快、人物轮廓清晰",
        "lighting": "高调光，自然光 / High Key, Natural Light",
        "tone": "暖色调 / Warm",
        "color_spectrum": "暖调主导",
        "borrowed_films": ["疯狂的石头", "两杆大烟枪"],
    },
]

_LABEL_SET = {str(item.get("label") or "").strip() for item in STYLE_MODE_CATALOG}
_ID_MAP = {str(item.get("id") or "").strip(): item for item in STYLE_MODE_CATALOG}
_LABEL_MAP = {str(item.get("label") or "").strip(): item for item in STYLE_MODE_CATALOG}
_ZH_MAP = {str(item.get("label") or "").split(" / ")[0].strip(): item for item in STYLE_MODE_CATALOG}

_LEGACY_MAP = {
    "Cyberpunk": "赛博朋克 / Cyberpunk",
    "Steampunk": "蒸汽朋克 / Steampunk",
    "Film Noir": "黑色电影 / Film Noir",
    "Gothic": "哥特恐怖 / Gothic Horror",
    "Ghibli Style": "吉卜力田园 / Ghibli Pastoral",
    "Disney Style": "迪士尼奇幻 / Disney Fantasy",
    "赛博朋克": "赛博朋克 / Cyberpunk",
    "蒸汽朋克": "蒸汽朋克 / Steampunk",
    "黑色电影": "黑色电影 / Film Noir",
    "哥特风格": "哥特恐怖 / Gothic Horror",
    "吉卜力风格": "吉卜力田园 / Ghibli Pastoral",
    "迪士尼风格": "迪士尼奇幻 / Disney Fantasy",
    "古装战争": "古装战争 / Ancient War",
    "未来科技": "近未来科技 / Near-Future Tech",
    "仙侠": "仙侠修真 / Xianxia Cultivation",
    "武侠": "武侠江湖 / Wuxia Jianghu",
    "都市情感 / Urban Romance": "当代都市 / Contemporary Urban",
    "都市情感": "当代都市 / Contemporary Urban",
    "Urban Romance": "当代都市 / Contemporary Urban",
    "现代职场 / Modern Workplace": "当代都市 / Contemporary Urban",
    "现代职场": "当代都市 / Contemporary Urban",
    "Modern Workplace": "当代都市 / Contemporary Urban",
    "现实主义 / Realism": "当代都市 / Contemporary Urban",
    "现实主义": "当代都市 / Contemporary Urban",
    "Realism": "当代都市 / Contemporary Urban",
    "剧情 / Drama": "当代都市 / Contemporary Urban",
    "剧情": "当代都市 / Contemporary Urban",
    "Drama": "当代都市 / Contemporary Urban",
    "短剧快节奏 / Short Drama": "当代都市 / Contemporary Urban",
    "短剧快节奏": "当代都市 / Contemporary Urban",
    "Short Drama": "当代都市 / Contemporary Urban",
    "通用连续剧 / General Series": "当代都市 / Contemporary Urban",
    "通用连续剧": "当代都市 / Contemporary Urban",
    "General Series": "当代都市 / Contemporary Urban",
    "都市轻喜剧 / Urban Light Comedy": "喜剧轻快 / Comedy / Light",
    "都市轻喜剧": "喜剧轻快 / Comedy / Light",
    "Urban Light Comedy": "喜剧轻快 / Comedy / Light",
    "喜剧 / Comedy": "喜剧轻快 / Comedy / Light",
    "喜剧": "喜剧轻快 / Comedy / Light",
    "Comedy": "喜剧轻快 / Comedy / Light",
    "爱情情感 / Romance / Emotional": "浪漫爱情 / Romance Gloss",
    "爱情情感": "浪漫爱情 / Romance Gloss",
    "情感治愈 / Emotional Healing Drama": "浪漫爱情 / Romance Gloss",
    "情感治愈": "浪漫爱情 / Romance Gloss",
    "浪漫爱情 / Romance": "浪漫爱情 / Romance Gloss",
    "Romance": "浪漫爱情 / Romance Gloss",
    "科幻冒险 / Sci-Fi Adventure": "近未来科技 / Near-Future Tech",
    "科幻冒险": "近未来科技 / Near-Future Tech",
    "Sci-Fi Adventure": "近未来科技 / Near-Future Tech",
    "悬疑惊悚 / Mystery / Thriller": "悬疑惊悚 / Mystery Thriller",
    "Mystery / Thriller": "悬疑惊悚 / Mystery Thriller",
    "古装武侠 / Period / Wuxia": "武侠江湖 / Wuxia Jianghu",
    "古装武侠": "武侠江湖 / Wuxia Jianghu",
    "Period / Wuxia": "武侠江湖 / Wuxia Jianghu",
    "仙侠修真 / Xianxia": "仙侠修真 / Xianxia Cultivation",
    "仙侠奇幻 / Xianxia / Fantasy": "仙侠修真 / Xianxia Cultivation",
    "仙侠奇幻": "仙侠修真 / Xianxia Cultivation",
    "Xianxia": "仙侠修真 / Xianxia Cultivation",
    "青春成长 / Youth Coming-of-Age": "校园青春 / Campus Youth",
    "青春成长": "校园青春 / Campus Youth",
    "Youth Coming-of-Age": "校园青春 / Campus Youth",
    "校园青春 / High School / Youth": "校园青春 / Campus Youth",
    "High School / Youth": "校园青春 / Campus Youth",
    "奇幻史诗 / Fantasy Epic": "神话史诗 / Mythic Epic",
    "奇幻史诗": "神话史诗 / Mythic Epic",
    "Fantasy Epic": "神话史诗 / Mythic Epic",
    "恐怖 / Horror": "哥特恐怖 / Gothic Horror",
    "恐怖": "哥特恐怖 / Gothic Horror",
    "Horror": "哥特恐怖 / Gothic Horror",
    "历史 / Historical": "年代复古 / Period Retro",
    "历史": "年代复古 / Period Retro",
    "Historical": "年代复古 / Period Retro",
    "穿越 / Transmigration": "穿越 / Transmigration",
    "穿越": "穿越 / Transmigration",
    "Transmigration": "穿越 / Transmigration",
}


def normalize_style_mode(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw in _LABEL_SET:
        return raw
    if raw in _LEGACY_MAP:
        return _LEGACY_MAP[raw]
    if raw in _ID_MAP:
        return str(_ID_MAP[raw].get("label") or "")
    if raw in _ZH_MAP:
        return str(_ZH_MAP[raw].get("label") or "")
    return raw


def find_style_mode(value: Any) -> Optional[Dict[str, Any]]:
    normalized = normalize_style_mode(value)
    if not normalized:
        return None
    return _LABEL_MAP.get(normalized) or _ID_MAP.get(str(value or "").strip())


def format_style_mode_injection(value: Any) -> str:
    mode = find_style_mode(value)
    if not mode:
        return ""
    films = mode.get("borrowed_films") if isinstance(mode.get("borrowed_films"), list) else []
    lines = [
        f"Style Mode: {mode.get('label')}",
        f"Style Mode Id: {mode.get('id')}",
        f"Visual Key: {mode.get('visual_key')}",
        f"Temperament: {mode.get('temperament')}",
        f"Style Mode Spec: {mode.get('global_style')}",
    ]
    if mode.get("lighting"):
        lines.append(f"Style Mode Lighting: {mode.get('lighting')}")
    if mode.get("tone"):
        lines.append(f"Style Mode Tone: {mode.get('tone')}")
    if mode.get("color_spectrum"):
        lines.append(f"Style Mode Color Spectrum: {mode.get('color_spectrum')}")
    if films:
        lines.append("Style Mode Film Hints: " + ", ".join(str(f) for f in films if str(f).strip()))
    return "\n".join(lines)


def build_style_mode_prompt_table() -> str:
    rows = []
    for item in STYLE_MODE_CATALOG:
        rows.append(
            f"{item.get('label')}｜基调={item.get('visual_key')}｜气质={item.get('temperament')}｜{item.get('global_style')}"
        )
    return "\n".join(rows)


def style_mode_labels() -> List[str]:
    return [str(item.get("label") or "") for item in STYLE_MODE_CATALOG if item.get("label")]


def resolve_style_mode(*values: Any) -> str:
    for value in values:
        normalized = normalize_style_mode(value)
        if normalized:
            return normalized
    return ""


def apply_style_mode_defaults(current: Any, next_label: Any) -> Dict[str, Any]:
    prev = dict(current) if isinstance(current, dict) else {}
    mode = find_style_mode(next_label)
    raw = str(next_label or "").strip()
    if not mode:
        if raw:
            prev["base_positioning"] = raw
            prev["style_mode"] = raw
        return prev

    def _empty(key: str) -> bool:
        return not str(prev.get(key) or "").strip()

    label = str(mode.get("label") or raw)
    prev["base_positioning"] = label
    prev["style_mode"] = label
    if _empty("Global_Style") and mode.get("global_style"):
        prev["Global_Style"] = mode.get("global_style")
    if _empty("lighting") and mode.get("lighting"):
        prev["lighting"] = mode.get("lighting")
    if _empty("tone") and mode.get("tone"):
        prev["tone"] = mode.get("tone")
    return prev
