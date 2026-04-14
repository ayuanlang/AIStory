with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_str = '''                                    <div className="absolute top-2 left-2 bg-black/60 px-2 py-1 rounded text-xs font-mono font-bold text-white border border-white/10 pointer-events-none">
                                        {shot.shot_id}
                                    </div>'''

new_str = '''                                    {(() => {
                                        let hasTemp = false;
                                        try {
                                            const tech = typeof shot.technical_notes === 'string' ? JSON.parse(shot.technical_notes) : (shot.technical_notes || {});
                                            if (shot.video_url && (tech.video_oss_uploaded === false || isEphemeralProviderMediaUrl(shot.video_url))) hasTemp = true;
                                            else if (!shot.video_url && shot.image_url && (tech.start_frame_oss_uploaded === false || isEphemeralProviderMediaUrl(shot.image_url))) hasTemp = true;
                                        } catch(e) {}
                                        return hasTemp ? (
                                            <div 
                                                className="absolute top-2 left-14 z-30 inline-flex items-center gap-1 rounded bg-amber-500/90 text-amber-950 px-1.5 py-0.5 text-[10px] font-bold shadow pointer-events-none" 
                                                title={t('素材未持久化到OSS，目前为临时地址', 'Media not yet persisted to OSS')}
                                            >
                                                <AlertTriangle size={12} />
                                                <span>{t('临时', 'Temp')}</span>
                                            </div>
                                        ) : null;
                                    })()}
                                    <div className="absolute top-2 left-2 bg-black/60 px-2 py-1 rounded text-xs font-mono font-bold text-white border border-white/10 pointer-events-none">
                                        {shot.shot_id}
                                    </div>'''

if old_str in content:
    content = content.replace(old_str, new_str)
    with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Patched successfully')
else:
    print('Pattern not found')
