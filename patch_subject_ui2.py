with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_str = '''                            {entity.image_url ? (
                                <SafeImage'''

new_str = '''                            {(() => {
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
                            {entity.image_url ? (
                                <SafeImage'''

if old_str in content:
    content = content.replace(old_str, new_str)
    with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Patched successfully')
else:
    print('Pattern not found')
