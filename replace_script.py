import re
with open(r'c:\AS\AIStory\frontend\src\pages\ProjectList.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

if "import InputGroup from" not in text:
    text = text.replace("import Editor from './Editor';", "import Editor from './Editor';\nimport InputGroup from './editor/components/InputGroup';")

replacements = [
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'类型\', \'Type\'\)\}</label>\s*<select.*?value=\{newType\}.*?onChange=\{.*?setNewType.*?\}>.*?</select>', 
     r'<InputGroup label={t("类型", "Type")} value={newType} onChange={setNewType} list={PROJECT_EP_TYPE_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'国家地域\', \'Country/Region\'\)\}</label>\s*<select.*?value=\{newCountryRegion\}.*?onChange=\{.*?setNewCountryRegion.*?\}>.*?</select>',
     r'<InputGroup label={t("国家地域", "Country/Region")} value={newCountryRegion} onChange={setNewCountryRegion} list={PROJECT_EP_COUNTRY_REGION_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'语言\', \'Language\'\)\}</label>\s*<select.*?value=\{newLanguage\}.*?onChange=\{.*?setNewLanguage.*?\}>.*?</select>',
     r'<InputGroup label={t("语言", "Language")} value={newLanguage} onChange={setNewLanguage} list={PROJECT_EP_LANGUAGE_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'基础定位\', \'Base Positioning\'\)\}</label>\s*<select.*?value=\{newBasePositioning\}.*?onChange=\{.*?setNewBasePositioning.*?\}>.*?</select>',
     r'<InputGroup label={t("基础定位", "Base Positioning")} value={newBasePositioning} onChange={setNewBasePositioning} list={PROJECT_EP_BASE_POSITIONING_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'画幅比例\', \'Aspect Ratio\'\)\}</label>\s*<select.*?value=\{newAspectRatio\}.*?onChange=\{.*?setNewAspectRatio.*?\}>.*?</select>',
     r'<InputGroup label={t("画幅比例", "Aspect Ratio")} value={newAspectRatio} onChange={setNewAspectRatio} list={PROJECT_EP_RESOLUTION_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'年代\', \'Era\'\)\}</label>\s*<select.*?value=\{newEra\}.*?onChange=\{.*?setNewEra.*?\}>.*?</select>',
     r'<InputGroup label={t("年代", "Era")} value={newEra} onChange={setNewEra} list={PROJECT_SCENE_ANALYSIS_ERA_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'镜头偏好\', \'Lens Preference\'\)\}</label>\s*<select.*?value=\{newLensPreference\}.*?onChange=\{.*?setNewLensPreference.*?\}>.*?</select>',
     r'<InputGroup label={t("镜头偏好", "Lens Preference")} value={newLensPreference} onChange={setNewLensPreference} list={PROJECT_EP_LENS_PREFERENCE_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'播出安全等级\', \'Broadcast Safety Level\'\)\}</label>\s*<select.*?value=\{newBroadcastSafetyLevel\}.*?onChange=\{.*?setNewBroadcastSafetyLevel.*?\}>.*?</select>',
     r'<InputGroup label={t("播出安全等级", "Broadcast Safety Level")} value={newBroadcastSafetyLevel} onChange={setNewBroadcastSafetyLevel} list={PROJECT_SCENE_ANALYSIS_SAFETY_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'创作力\', \'Creativity\'\)\}</label>\s*<select.*?value=\{newCreativity\}.*?onChange=\{.*?setNewCreativity.*?\}>.*?</select>',
     r'<InputGroup label={t("创作力", "Creativity")} value={newCreativity} onChange={setNewCreativity} list={PROJECT_EP_CREATIVITY_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'图像尺寸\', \'Image Size\'\)\}</label>\s*<select.*?value=\{newImageSize\}.*?onChange=\{.*?setNewImageSize.*?\}>.*?</select>',
     r'<InputGroup label={t("图像尺寸", "Image Size")} value={newImageSize} onChange={setNewImageSize} list={PROJECT_CREATE_FALLBACK_IMAGE_SIZE_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white/70 mb-1\.5">\{t\(\'视频生成偏好\', \'Video Gen Preference\'\)\}</label>\s*<select.*?value=\{newVideoGenerationPreference\}.*?onChange=\{.*?setNewVideoGenerationPreference.*?\}>.*?</select>',
     r'<InputGroup label={t("视频生成偏好", "Video Gen Preference")} value={newVideoGenerationPreference} onChange={setNewVideoGenerationPreference} list={PROJECT_EP_VIDEO_GEN_PREFERENCE_OPTIONS} />'),
]

for pat, repl in replacements:
    match = re.search(pat, text, flags=re.DOTALL)
    if match:
        text = text[:match.start()] + repl + text[match.end():]
    else:
        print(f"Could not find match for {pat[:30]}")

with open(r'c:\AS\AIStory\frontend\src\pages\ProjectList.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
