import re

def repl_subj_lib():
    with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
        content = f.read()

    content = content.replace("fetchAssets,", "fetchAssets,\n    deleteAsset,")

    old_fetch = r"""    const fetchSubjectGenerationHistory = useCallback\(async \(entity\) => \{.*?setSubjectGenerationHistoryLoading\(false\);\s*\}\s*\}, \[getGenerationJobPool, normalizeSubjectGenerationHistory, onLog, projectId\]\);"""
    new_fetch = """    const fetchSubjectGenerationHistory = useCallback(async (entity) => {
        const stableEntityId = String(entity?.id || entity || '').trim();
        if (!stableEntityId) {
            setSubjectGenerationHistory([]);
            return;
        }

        setSubjectGenerationHistoryLoading(true);
        try {
            const data = await fetchAssets();
            const filtered = data.filter((item) => {
                const meta = item?.meta_info && typeof item.meta_info === 'object' ? item.meta_info : {};
                if (item.projectId && String(projectId || '').trim() && item.projectId !== String(projectId || '').trim()) {
                    // return false; 
                }
                if (String(meta?.entity_id || '').trim() !== stableEntityId) return false;
                if (String(item.type).toLowerCase() !== 'image') return false;
                return true;
            }).map((item) => {
                const meta = item?.meta_info && typeof item.meta_info === 'object' ? item.meta_info : {};
                return {
                    id: item.id,
                    job_id: item.id,
                    status: 'completed',
                    resultUrl: item.url,
                    displayLabel: item.remark || t('主体生图', 'Subject Image Generation'),
                    createdAtMs: Date.parse(item.created_at || '') || 0,
                    kind: 'asset'
                };
            }).sort((a, b) => (b.createdAtMs || 0) - (a.createdAtMs || 0));
            setSubjectGenerationHistory(filtered.slice(0, 12));
        } catch (e) {
            onLog?.(`Failed to load subject generation history: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
            setSubjectGenerationHistory([]);
        } finally {
            setSubjectGenerationHistoryLoading(false);
        }
    }, [onLog, t, projectId]);"""
    
    if re.search(old_fetch, content, flags=re.DOTALL):
        content = re.sub(old_fetch, new_fetch, content, flags=re.DOTALL)
        print("Updated fetchSubjectGenerationHistory")
    else:
        print("Failed to find fetchSubjectGenerationHistory")

    old_delete = r"""    const handleDeleteSubjectGenerationHistoryItem = useCallback\(async \(item\) => \{
        const kind = String\(item\?\.kind \|\| ''\)\.trim\(\);
        const jobId = String\(item\?\.job_id \|\| ''\)\.trim\(\);.*?setSubjectGenerationHistoryDeletingId\(''\);\s*\}\s*\}, \[deleteGenerationJob, fetchSubjectGenerationHistory, onLog, selectedEntity, t\]\);"""
    new_delete = """    const handleDeleteSubjectGenerationHistoryItem = useCallback(async (item) => {
        const assetId = String(item?.id || '').trim();
        if (!assetId || !selectedEntity?.id) return;

        setSubjectGenerationHistoryDeletingId(assetId);
        try {
            await deleteAsset(assetId);
            await fetchSubjectGenerationHistory(selectedEntity);
            onLog?.(t('主体历史图片已删除。', 'Subject history image deleted.'), 'warning');
        } catch (e) {
            onLog?.(t('删除历史图片失败：', 'Failed to delete subject history image: ') + (e?.response?.data?.detail || e?.message || 'unknown error'), 'error');
        } finally {
            setSubjectGenerationHistoryDeletingId('');
        }
    }, [fetchSubjectGenerationHistory, onLog, selectedEntity, t]);"""
    
    if re.search(old_delete, content, flags=re.DOTALL):
        content = re.sub(old_delete, new_delete, content, flags=re.DOTALL)
        print("Updated handleDeleteSubjectGenerationHistoryItem")
    else:
        print("Failed to find handleDeleteSubjectGenerationHistoryItem")

    with open('frontend/src/pages/editor/components/SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
        f.write(content)

def repl_shots_view():
    with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
        content = f.read()

    content = content.replace("fetchAssets,", "fetchAssets,\n    deleteAsset,")

    old_fetch = r"""    const fetchShotGenerationHistory = useCallback\(async \(shot\) => \{.*?setShotGenerationHistoryLoading\(false\);\s*\}\s*\}, \[getGenerationJobPool, normalizeScopedGenerationHistory, onLog, projectId\]\);"""
    new_fetch = """    const fetchShotGenerationHistory = useCallback(async (shot) => {
        const stableShotId = String(shot?.id || shot || '').trim();
        if (!stableShotId) {
            setShotGenerationHistory([]);
            return;
        }

        setShotGenerationHistoryLoading(true);
        try {
            const data = await fetchAssets();
            const filtered = data.filter((item) => {
                const meta = item?.meta_info && typeof item.meta_info === 'object' ? item.meta_info : {};
                if (String(meta?.shot_id || '').trim() !== stableShotId) return false;
                return true;
            }).map((item) => {
                let displayLabel = item.remark;
                if (!displayLabel) {
                    const type = String(item.type).toLowerCase();
                    if (type === 'video') displayLabel = t('视频生成', 'Video Generation');
                    else if (type === 'audio') displayLabel = t('音频生成', 'Audio Generation');
                    else displayLabel = t('生图 / 拓展', 'Image Generation');
                }
                return {
                    id: item.id,
                    job_id: item.id,
                    status: 'completed',
                    resultUrl: item.url,
                    mediaKind: String(item.type).toLowerCase(),
                    displayLabel: displayLabel,
                    createdAtMs: Date.parse(item.created_at || '') || 0,
                    kind: 'asset'
                };
            }).sort((a, b) => (b.createdAtMs || 0) - (a.createdAtMs || 0));
            setShotGenerationHistory(filtered.slice(0, 16));
        } catch (e) {
            onLog?.(`Failed to load shot generation history: ${e?.response?.data?.detail || e?.message || 'unknown error'}`, 'error');
            setShotGenerationHistory([]);
        } finally {
            setShotGenerationHistoryLoading(false);
        }
    }, [onLog, t]);"""
    
    if re.search(old_fetch, content, flags=re.DOTALL):
        content = re.sub(old_fetch, new_fetch, content, flags=re.DOTALL)
        print("Updated fetchShotGenerationHistory")
    else:
        print("Failed to find fetchShotGenerationHistory")

    old_delete = r"""    const handleDeleteShotGenerationHistoryItem = useCallback\(async \(item\) => \{
        const kind = String\(item\?\.kind \|\| ''\)\.trim\(\);
        const jobId = String\(item\?\.job_id \|\| ''\)\.trim\(\);.*?setShotGenerationHistoryDeletingId\(''\);\s*\}\s*\}, \[deleteGenerationJob, editingShot, fetchShotGenerationHistory, onLog, t\]\);"""
    new_delete = """    const handleDeleteShotGenerationHistoryItem = useCallback(async (item) => {
        const assetId = String(item?.id || '').trim();
        if (!assetId || !editingShot?.id) return;

        setShotGenerationHistoryDeletingId(assetId);
        try {
            await deleteAsset(assetId);
            await fetchShotGenerationHistory(editingShot);
            onLog?.(t('镜头历史资产已删除。', 'Shot history asset deleted.'), 'warning');
        } catch (e) {
            onLog?.(t('删除历史资产失败：', 'Failed to delete shot history asset: ') + (e?.response?.data?.detail || e?.message || 'unknown error'), 'error');
        } finally {
            setShotGenerationHistoryDeletingId('');
        }
    }, [editingShot, fetchShotGenerationHistory, onLog, t]);"""
    
    if re.search(old_delete, content, flags=re.DOTALL):
        content = re.sub(old_delete, new_delete, content, flags=re.DOTALL)
        print("Updated handleDeleteShotGenerationHistoryItem")
    else:
        print("Failed to find handleDeleteShotGenerationHistoryItem")

    with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
        f.write(content)

repl_subj_lib()
repl_shots_view()
