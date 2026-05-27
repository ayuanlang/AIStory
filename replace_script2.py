import re
with open(r'c:\AS\AIStory\frontend\src\pages\ProjectList.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

replacements = [
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'类型\', \'Type\'\)\}</label>\s*<select.*?value=\{newType\}.*?onChange=\{.*?setNewType.*?\}>.*?</select>', 
     r'<InputGroup label={t("类型", "Type")} value={newType} onChange={setNewType} list={projectCreateOptions.type} />'),
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'国家地域\', \'Country/Region\'\)\}</label>\s*<select.*?value=\{newCountryRegion\}.*?onChange=\{.*?setNewCountryRegion.*?\}>.*?</select>',
     r'<InputGroup label={t("国家地域", "Country/Region")} value={newCountryRegion} onChange={setNewCountryRegion} list={projectCreateOptions.country_region} />'),
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'语言\', \'Language\'\)\}</label>\s*<select.*?value=\{newLanguage\}.*?onChange=\{.*?setNewLanguage.*?\}>.*?</select>',
     r'<InputGroup label={t("语言", "Language")} value={newLanguage} onChange={setNewLanguage} list={projectCreateOptions.language} />'),
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'基础定位\', \'Base Positioning\'\)\}</label>\s*<select.*?value=\{newBasePositioning\}.*?onChange=\{.*?setNewBasePositioning.*?\}>.*?</select>',
     r'<InputGroup label={t("基础定位", "Base Positioning")} value={newBasePositioning} onChange={setNewBasePositioning} list={projectCreateOptions.base_positioning} />'),
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'画幅比例\', \'Aspect Ratio\'\)\}</label>\s*<select.*?value=\{newAspectRatio\}.*?onChange=\{.*?setNewAspectRatio.*?\}>.*?</select>',
     r'<InputGroup label={t("画幅比例", "Aspect Ratio")} value={newAspectRatio} onChange={setNewAspectRatio} list={projectCreateOptions.aspect_ratio || PROJECT_CREATE_FALLBACK_ASPECT_RATIO_OPTIONS} />'),
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'年代\', \'Era\'\)\}</label>\s*<select.*?value=\{newEra\}.*?onChange=\{.*?setNewEra.*?\}>.*?</select>',
     r'<InputGroup label={t("年代", "Era")} value={newEra} onChange={setNewEra} list={projectCreateOptions.era} />'),
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'镜头偏好\', \'Lens Preference\'\)\}</label>\s*<select.*?value=\{newLensPreference\}.*?onChange=\{.*?setNewLensPreference.*?\}>.*?</select>',
     r'<InputGroup label={t("镜头偏好", "Lens Preference")} value={newLensPreference} onChange={setNewLensPreference} list={projectCreateOptions.lens_preference} />'),
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'播出安全等级\', \'Broadcast Safety Level\'\)\}</label>\s*<select.*?value=\{newBroadcastSafetyLevel\}.*?onChange=\{.*?setNewBroadcastSafetyLevel.*?\}>.*?</select>',
     r'<InputGroup label={t("播出安全等级", "Broadcast Safety Level")} value={newBroadcastSafetyLevel} onChange={setNewBroadcastSafetyLevel} list={projectCreateOptions.broadcast_safety_level} />'),
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'创作力\', \'Creativity\'\)\}</label>\s*<select.*?value=\{newCreativity\}.*?onChange=\{.*?setNewCreativity.*?\}>.*?</select>',
     r'<InputGroup label={t("创作力", "Creativity")} value={newCreativity} onChange={setNewCreativity} list={projectCreateOptions.creativity} />'),
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'图像尺寸\', \'Image Size\'\)\}</label>\s*<select.*?value=\{newImageSize\}.*?onChange=\{.*?setNewImageSize.*?\}>.*?</select>',
     r'<InputGroup label={t("图像尺寸", "Image Size")} value={newImageSize} onChange={setNewImageSize} list={projectCreateOptions.image_size || PROJECT_CREATE_FALLBACK_IMAGE_SIZE_OPTIONS} />'),
    (r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\(\'视频生成偏好\', \'Video Gen Preference\'\)\}</label>\s*<select.*?value=\{newVideoGenerationPreference\}.*?onChange=\{.*?setNewVideoGenerationPreference.*?\}>.*?</select>',
     r'<InputGroup label={t("视频生成偏好", "Video Gen Preference")} value={newVideoGenerationPreference} onChange={setNewVideoGenerationPreference} list={projectCreateOptions.video_generation_preference} />'),
    # for the project settings modal
    (r'<label className="block text-sm font-medium text-white mb-2">\{t\(\'画幅比例\', \'Aspect Ratio\'\)\}</label>\s*<select.*?value=\{batchAspectRatio\}.*?onChange=\{.*?setBatchAspectRatio.*?\}>.*?</select>',
     r'<InputGroup label={t("画幅比例", "Aspect Ratio")} value={batchAspectRatio} onChange={setBatchAspectRatio} list={PROJECT_EP_RESOLUTION_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white mb-2">\{t\(\'质量等级\', \'Quality\'\)\}</label>\s*<select.*?value=\{batchQuality\}.*?onChange=\{.*?setBatchQuality.*?\}>.*?</select>',
     r'<InputGroup label={t("质量等级", "Quality")} value={batchQuality} onChange={setBatchQuality} list={[\'standard\', \'high\', \'ultra\']} />'),
    (r'<label className="block text-sm font-medium text-white mb-2">\{t\(\'类型\', \'Type\'\)\}</label>\s*<select.*?value=\{batchType\}.*?onChange=\{.*?setBatchType.*?\}>.*?</select>',
     r'<InputGroup label={t("类型", "Type")} value={batchType} onChange={setBatchType} list={PROJECT_EP_TYPE_OPTIONS} />'),
    (r'<label className="block text-sm font-medium text-white mb-2">\{t\(\'基础定位\', \'Base Positioning\'\)\}</label>\s*<select.*?value=\{batchBasePositioning\}.*?onChange=\{.*?setBatchBasePositioning.*?\}>.*?</select>',
     r'<InputGroup label={t("基础定位", "Base Positioning")} value={batchBasePositioning} onChange={setBatchBasePositioning} list={PROJECT_EP_BASE_POSITIONING_OPTIONS} />'),
]

for pat, repl in replacements:
    match = re.search(pat, text, flags=re.DOTALL)
    if match:
        text = text[:match.start()] + repl + text[match.end():]
    else:
        print(f"Could not find match for {pat[:90]}")

with open(r'c:\AS\AIStory\frontend\src\pages\ProjectList.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
