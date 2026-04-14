import re

with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to insert the warning icon inside the entity thumbnail. 
# Look for {entity.image_url ? ( around line 3541
search_pattern = r"(\{entity\.image_url \?\s*\(\s*<SafeImage)"

replacement = r'''{(() => {
                                let isOssTemp = false;
                                try {
                                    const attrs = entity.custom_attributes ? (typeof entity.custom_attributes === 'string' ? JSON.parse(entity.custom_attributes) : entity.custom_attributes) : {};
                                    if (attrs && attrs.oss_uploaded_success === false) {
                                        isOssTemp = true;
                                    }
                                } catch(e) {}
                                if (!isOssTemp && entity.image_url && isEphemeralProviderMediaUrl(entity.image_url)) {
                                    isOssTemp = true;
                                }
                                return isOssTemp ? (
                                    <div 
                                        className="absolute top-2 left-2 z-30 inline-flex items-center gap-1 rounded bg-amber-500/90 text-amber-950 px-1.5 py-0.5 text-[10px] font-bold shadow" 
                                        title={t('图片未持久化到OSS，目前为临时地址。', 'Image not yet persisted to OSS, using temporary link.')}
                                    >
                                        <AlertTriangle size={12} />
                                        <span>{t('临时图片', 'Temp')}</span>
                                    </div>
                                ) : null;
                            })()}
                            \1'''
content = re.sub(search_pattern, replacement, content)

with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Subject UI patched')
