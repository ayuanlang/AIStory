import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, FileText, Film, Home, Image as ImageIcon, Loader2, Settings as SettingsIcon, Sparkles, Users } from 'lucide-react';
import FunctionApiSelector from '../components/FunctionApiSelector';
import { useFunctionApis } from '../components/useFunctionApis';
import { confirmUiMessage } from '../lib/uiMessage';
import { lazyWithChunkReload } from '../lib/lazyWithChunkReload';
import { getUiLang, tUI } from '../lib/uiLang';
import {
    ensurePromoProjectScript,
    fetchMe,
    fetchPromoProject,
    generatePromoProjectScript,
    updatePromoProject,
} from '../services/api';
import { formatProviderModelEndpointError } from './editor/editorConfig';
import PromoPlanner from './editor/components/PromoPlanner';
import { writePromoCatalogFocus } from './PromoCatalogManager';

const Editor = lazyWithChunkReload(() => import('./Editor'));

const PRODUCTION_TABS = new Set(['script', 'subjects', 'shots', 'scenes', 'overview']);

const PromoEditor = ({
    projectId,
    initialProject,
    onClose,
    onOpenCatalog,
    readOnly = false,
}) => {
    const functionApiConfigs = useFunctionApis();
    const params = useParams();
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const id = projectId || params.id;
    const cached = initialProject && String(initialProject.id) === String(id) ? initialProject : null;
    const [project, setProject] = useState(cached || null);
    const [isInitializing, setIsInitializing] = useState(!cached);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isGeneratingScript, setIsGeneratingScript] = useState(false);
    const [isEnsuringStory, setIsEnsuringStory] = useState(false);
    const [titleDraft, setTitleDraft] = useState(cached?.title || '');
    const [selectedScriptAnalysisApiId, setSelectedScriptAnalysisApiId] = useState(() => (
        Number(localStorage.getItem('func_api_script_analysis') || 0) || null
    ));
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const isReadOnlyView = Boolean(readOnly || initialProject?.is_temp_view || project?.is_temp_view);
    const urlTab = String(searchParams.get('tab') || '');
    const [hostView, setHostView] = useState(() => (
        PRODUCTION_TABS.has(urlTab) ? urlTab : 'planner'
    ));
    const activeTab = PRODUCTION_TABS.has(hostView) ? hostView : 'planner';
    const linkedStoryId = Number(project?.linked_story_project_id || 0) || 0;

    useEffect(() => {
        const next = PRODUCTION_TABS.has(urlTab) ? urlTab : 'planner';
        setHostView((prev) => (prev === next ? prev : next));
    }, [urlTab]);

    const setActiveTab = useCallback((tab) => {
        const next = PRODUCTION_TABS.has(tab) ? tab : 'planner';
        setHostView(next);
        setSearchParams((prev) => {
            const params = new URLSearchParams(prev);
            if (next !== 'planner') params.set('tab', next);
            else params.delete('tab');
            return params;
        }, { replace: true });
    }, [setSearchParams]);

    const loadProject = useCallback(async () => {
        if (!id) return;
        try {
            const [row] = await Promise.all([
                fetchPromoProject(id),
                fetchMe().catch(() => null),
            ]);
            if (row) {
                setProject(row);
                setTitleDraft(row.title || '');
            }
        } catch (error) {
            console.error('Failed to load promo project', error);
        } finally {
            setIsInitializing(false);
        }
    }, [id]);

    useEffect(() => {
        loadProject();
    }, [loadProject]);

    useEffect(() => {
        if (!id || activeTab === 'planner') return;
        let cancelled = false;
        const shouldBlock = !Number(project?.linked_story_project_id || 0);
        if (shouldBlock) setIsEnsuringStory(true);
        ensurePromoProjectScript(id)
            .then((row) => {
                if (cancelled || !row) return;
                setProject((prev) => ({ ...(prev || {}), ...(row || {}) }));
            })
            .catch((error) => {
                console.error('Failed to ensure promo story workspace', error);
            })
            .finally(() => {
                if (!cancelled && shouldBlock) setIsEnsuringStory(false);
            });
        return () => {
            cancelled = true;
        };
    }, [activeTab, id, project?.linked_story_project_id]);

    const buildScriptAnalysisApiPayload = useCallback((payload = {}) => ({
        ...payload,
        function_name: 'script_analysis',
        system_api_id: Number(selectedScriptAnalysisApiId || 0) || null,
    }), [selectedScriptAnalysisApiId]);

    const handlePlannerInfo = useCallback((updater) => {
        setProject((prev) => {
            const nextInfo = typeof updater === 'function' ? updater(prev || {}) : updater;
            return { ...(prev || {}), ...(nextInfo || {}) };
        });
    }, []);

    const handleClose = () => {
        if (typeof onClose === 'function') {
            onClose();
            return;
        }
        navigate('/projects');
    };

    const handleTitleBlur = async () => {
        if (isReadOnlyView || !id) return;
        const nextTitle = String(titleDraft || '').trim();
        if (!nextTitle || nextTitle === (project?.title || '')) return;
        try {
            const updated = await updatePromoProject(id, { title: nextTitle });
            setProject(updated);
            setTitleDraft(updated?.title || nextTitle);
        } catch (error) {
            console.error('Failed to update promo title', error);
            setTitleDraft(project?.title || '');
        }
    };

    const handleGenerateActualScript = async ({ result } = {}) => {
        if (!id || isReadOnlyView) return;
        if (project?.has_script) {
            const ok = await confirmUiMessage(
                t('将覆盖剧本页已有成片脚本，是否继续？', 'This will overwrite the existing script page. Continue?'),
            );
            if (!ok) return;
        }
        setIsGeneratingScript(true);
        try {
            const row = await generatePromoProjectScript(id, buildScriptAnalysisApiPayload({
                promo_planner_result: result || project?.promo_planner_result || {},
                overwrite_existing: true,
            }));
            setProject(row);
            setActiveTab('script');
        } catch (error) {
            console.error(error);
            alert(`${t('生成实际脚本失败', 'Failed to generate script')}:\n${formatProviderModelEndpointError(error)}`);
        } finally {
            setIsGeneratingScript(false);
        }
    };

    const openCatalog = onOpenCatalog || ((focus) => {
        writePromoCatalogFocus({
            ...focus,
            key: Date.now(),
            returnPath: `/promo/${id}`,
            returnProjectId: id,
        });
        navigate('/projects');
    });

    const plannerTabs = [
        { id: 'planner', label: t('策划方案', 'Planner'), icon: Sparkles },
        { id: 'script', label: t('剧本', 'Script'), icon: FileText },
        { id: 'subjects', label: t('资产', 'Assets'), icon: Users },
        { id: 'shots', label: t('分镜', 'Shots'), icon: Film },
        { id: 'scenes', label: t('场景统计', 'Scenes'), icon: ImageIcon },
    ];

    if (!isInitializing && project && activeTab !== 'planner' && linkedStoryId) {
        return (
            <React.Suspense fallback={(
                <div className="flex h-screen items-center justify-center bg-background text-muted-foreground">
                    <Loader2 className="h-8 w-8 text-primary animate-spin mr-3" />
                    {t('加载剧本工作区...', 'Loading script workspace...')}
                </div>
            )}>
                <Editor
                    projectId={linkedStoryId}
                    initialActiveTab={activeTab}
                    readOnly={isReadOnlyView}
                    onClose={handleClose}
                    promoHost={{
                        promoProjectId: id,
                        promoTitle: titleDraft || project.title,
                        onOpenPlanner: () => setActiveTab('planner'),
                    }}
                />
            </React.Suspense>
        );
    }

    return (
        <div className="flex h-screen bg-background text-foreground font-sans overflow-hidden flex-col">
            <div className="h-14 shrink-0 border-b border-white/10 bg-card/40 px-3 sm:px-5 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                    <button
                        type="button"
                        onClick={() => navigate('/')}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5 shrink-0"
                        title={t('网站首页', 'Website Home')}
                    >
                        <Home className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">{t('网站首页', 'Home')}</span>
                    </button>
                    <button
                        type="button"
                        onClick={handleClose}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5 shrink-0"
                        title={t('返回项目列表', 'Back to Projects')}
                    >
                        <ArrowLeft className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">{t('返回项目', 'Back to Projects')}</span>
                    </button>
                    <div className="min-w-0 flex-1">
                        <div className="text-[10px] uppercase tracking-[0.18em] text-primary/80 font-semibold">
                            {t('商业宣传片', 'Commercial Promo')}
                        </div>
                        <input
                            className="w-full bg-transparent text-sm sm:text-base font-semibold text-white outline-none truncate disabled:opacity-70"
                            value={titleDraft}
                            onChange={(e) => setTitleDraft(e.target.value)}
                            onBlur={handleTitleBlur}
                            disabled={isReadOnlyView}
                            placeholder={t('宣传片项目标题', 'Promo project title')}
                        />
                    </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <FunctionApiSelector
                        functionName="script_analysis"
                        configs={functionApiConfigs}
                        label={t('剧本分析 API', 'Script Analysis API')}
                        value={selectedScriptAnalysisApiId}
                        onChange={setSelectedScriptAnalysisApiId}
                        className="hidden sm:flex"
                    />
                    <button
                        type="button"
                        onClick={() => {
                            const returnTo = encodeURIComponent(`${window.location.pathname}${window.location.search}${window.location.hash}`);
                            window.location.assign(`/settings?return_to=${returnTo}`);
                        }}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors"
                        title={t('设置', 'Settings')}
                    >
                        <SettingsIcon className="w-4 h-4" />
                    </button>
                </div>
            </div>

            <div className="h-11 shrink-0 border-b border-white/10 px-3 sm:px-5 flex items-center gap-2 overflow-x-auto">
                {plannerTabs.map((item) => {
                    const Icon = item.icon;
                    const isActive = activeTab === item.id;
                    return (
                        <button
                            key={item.id}
                            type="button"
                            onClick={() => setActiveTab(item.id)}
                            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 shrink-0 ${isActive ? 'bg-white/10 text-white' : 'text-muted-foreground hover:text-white'}`}
                        >
                            <Icon className="w-3.5 h-3.5" />
                            {item.label}
                            {item.id === 'script' && project?.has_script ? <span className="w-1.5 h-1.5 rounded-full bg-primary" /> : null}
                        </button>
                    );
                })}
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar">
                {isInitializing || !project || isEnsuringStory ? (
                    <div className="flex flex-col items-center justify-center h-[50vh] text-muted-foreground">
                        <Loader2 className="h-8 w-8 text-primary opacity-80 animate-spin mb-4" />
                        {isEnsuringStory ? t('正在打开剧本工作区...', 'Opening script workspace...') : t('加载中...', 'Loading...')}
                    </div>
                ) : (
                    <div className="max-w-6xl mx-auto p-4 sm:p-6 lg:p-8">
                        <div className="sm:hidden mb-4">
                            <FunctionApiSelector
                                functionName="script_analysis"
                                configs={functionApiConfigs}
                                label={t('剧本分析 API', 'Script Analysis API')}
                                value={selectedScriptAnalysisApiId}
                                onChange={setSelectedScriptAnalysisApiId}
                            />
                        </div>
                        <PromoPlanner
                            standalone
                            projectId={id}
                            t={t}
                            project={project}
                            onOpenCatalog={openCatalog}
                            info={project}
                            setInfo={handlePlannerInfo}
                            setProject={setProject}
                            onProjectUpdate={loadProject}
                            buildScriptAnalysisApiPayload={buildScriptAnalysisApiPayload}
                            isGenerating={isGenerating}
                            setIsGenerating={setIsGenerating}
                            onGenerateActualScript={handleGenerateActualScript}
                            isGeneratingScript={isGeneratingScript}
                            hasScript={Boolean(project?.has_script)}
                            onOpenScriptTab={() => setActiveTab('script')}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

export default PromoEditor;
