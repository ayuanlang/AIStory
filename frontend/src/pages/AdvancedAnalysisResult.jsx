import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Copy, Download, Save, Upload, ArrowLeft, Loader2, Wand2 } from 'lucide-react';
import { fetchEpisodes, fetchMe, updateEpisode } from '../services/api';

const DRAFT_KEY = 'advanced_ai_analysis_draft';

const AdvancedAnalysisResult = () => {
    const { id: projectId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const [searchParams] = useSearchParams();

    const episodeId = useMemo(() => {
        const fromQuery = searchParams.get('episodeId');
        const fromState = location.state?.episodeId;
        const raw = fromQuery || fromState;
        return raw ? Number(raw) : null;
    }, [location.state, searchParams]);

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [importing, setImporting] = useState(false);

    const [episodeTitle, setEpisodeTitle] = useState('');
    const [episodeInfo, setEpisodeInfo] = useState({});

    const [systemPrompt, setSystemPrompt] = useState(location.state?.systemPrompt || '');
    const [userPrompt, setUserPrompt] = useState(location.state?.userPrompt || '');
    const [resultText, setResultText] = useState(location.state?.analysisResult || '');

    useEffect(() => {
        let alive = true;

        const load = async () => {
            try {
                setLoading(true);

                const me = await fetchMe();
                if (!me?.is_superuser) {
                    alert('Not authorized. Superuser only.');
                    navigate(`/editor/${projectId}`);
                    return;
                }

                if (!episodeId) {
                    alert('Missing episodeId.');
                    navigate(`/editor/${projectId}`);
                    return;
                }

                const episodes = await fetchEpisodes(projectId);
                const episode = episodes.find(e => e.id === episodeId);
                if (!episode) {
                    alert('Episode not found.');
                    navigate(`/editor/${projectId}`);
                    return;
                }

                if (!alive) return;

                setEpisodeTitle(episode.title || '');
                const info = episode.episode_info || {};
                setEpisodeInfo(info);

                // If we landed here without navigation state (reload), try to restore from saved draft.
                const draft = info?.[DRAFT_KEY];
                if (!location.state?.analysisResult && draft?.resultText && !resultText) {
                    setSystemPrompt(draft.systemPrompt || '');
                    setUserPrompt(draft.userPrompt || '');
                    setResultText(draft.resultText || '');
                }
            } catch (e) {
                console.error(e);
                alert(`Failed to load analysis result page: ${e.message}`);
                navigate(`/editor/${projectId}`);
            } finally {
                if (alive) setLoading(false);
            }
        };

        load();
        return () => { alive = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [episodeId, projectId]);

    const copyResult = async () => {
        if (!resultText) return;
        await navigator.clipboard.writeText(resultText);
        alert('Result copied to clipboard.');
    };

    const downloadResult = () => {
        const blob = new Blob([resultText || ''], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `advanced_ai_analysis_episode_${episodeId || 'unknown'}.md`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const saveDraft = async () => {
        if (!episodeId) return;
        setSaving(true);
        try {
            const nextInfo = {
                ...(episodeInfo || {}),
                [DRAFT_KEY]: {
                    systemPrompt: systemPrompt || '',
                    userPrompt: userPrompt || '',
                    resultText: resultText || '',
                    updatedAt: new Date().toISOString(),
                },
            };
            const updated = await updateEpisode(episodeId, { episode_info: nextInfo });
            setEpisodeInfo(updated.episode_info || nextInfo);
            alert('Draft saved.');
        } catch (e) {
            console.error(e);
            alert(`Save failed: ${e.response?.data?.detail || e.message}`);
        } finally {
            setSaving(false);
        }
    };

    const importToScript = async () => {
        if (!episodeId) return;
        if (!confirm('Import will overwrite the episode script_content with this result. Continue?')) return;

        setImporting(true);
        try {
            await updateEpisode(episodeId, { script_content: resultText || '' });
            alert('Imported into episode script.');
            navigate(`/editor/${projectId}`);
        } catch (e) {
            console.error(e);
            alert(`Import failed: ${e.response?.data?.detail || e.message}`);
        } finally {
            setImporting(false);
        }
    };

    if (loading) {
        return (
            <div className="p-8 text-muted-foreground flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading...
            </div>
        );
    }

    return (
        <div className="p-4 sm:p-8 h-full flex flex-col w-full max-w-full overflow-hidden">
            <div className="flex items-start sm:items-center justify-between gap-4 mb-6 shrink-0">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => navigate(`/editor/${projectId}`)}
                        className="p-2 bg-white/5 hover:bg-white/10 rounded-lg border border-white/10 transition-colors"
                        title="Back to Editor"
                    >
                        <ArrowLeft className="w-4 h-4" />
                    </button>
                    <div>
                        <div className="text-xs text-muted-foreground">Advanced AI Analysis (Superuser)</div>
                        <h1 className="text-xl font-bold">Result — {episodeTitle || `Episode ${episodeId}`}</h1>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={copyResult}
                        disabled={!resultText}
                        className="flex items-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/10 rounded-lg font-medium transition-colors text-white border border-white/10 disabled:opacity-50"
                    >
                        <Copy className="w-4 h-4" /> Copy
                    </button>
                    <button
                        onClick={downloadResult}
                        disabled={!resultText}
                        className="flex items-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/10 rounded-lg font-medium transition-colors text-white border border-white/10 disabled:opacity-50"
                    >
                        <Download className="w-4 h-4" /> Download
                    </button>
                    <button
                        onClick={saveDraft}
                        disabled={saving}
                        className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg font-bold transition-colors text-white disabled:opacity-50"
                    >
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Save
                    </button>
                    <button
                        onClick={importToScript}
                        disabled={importing}
                        className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-bold transition-colors disabled:opacity-50"
                    >
                        {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                        Import
                    </button>
                </div>
            </div>

            <div className="flex-1 grid grid-cols-1 gap-4 overflow-hidden">
                <div className="bg-black/30 border border-white/10 rounded-xl overflow-hidden flex flex-col">
                    <div className="px-4 py-3 border-b border-white/10 bg-white/5 flex items-center justify-between">
                        <div className="text-sm font-bold flex items-center gap-2">
                            <Wand2 className="w-4 h-4 text-purple-500" />
                            Analysis Result (Editable)
                        </div>
                        <div className="text-xs text-muted-foreground">Edit → Save (draft) → Import</div>
                    </div>
                    <textarea
                        className="flex-1 bg-black/40 p-4 text-xs text-white font-mono focus:outline-none resize-none custom-scrollbar"
                        value={resultText}
                        onChange={(e) => setResultText(e.target.value)}
                        spellCheck={false}
                        placeholder="Analysis result will appear here..."
                    />
                </div>

                {/* Keep prompts available for reference/edit, but collapsed into a simple block to avoid extra UX */}
                <div className="bg-black/20 border border-white/10 rounded-xl overflow-hidden">
                    <div className="px-4 py-3 border-b border-white/10 bg-white/5 text-sm font-bold">Prompt Reference</div>
                    <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="flex flex-col">
                            <div className="text-xs font-bold text-muted-foreground mb-2">System Prompt</div>
                            <textarea
                                className="h-40 bg-black/40 border border-white/10 rounded-lg p-3 text-xs text-white/90 font-mono focus:outline-none focus:border-purple-500/50 resize-none custom-scrollbar"
                                value={systemPrompt}
                                onChange={(e) => setSystemPrompt(e.target.value)}
                                spellCheck={false}
                            />
                        </div>
                        <div className="flex flex-col">
                            <div className="text-xs font-bold text-muted-foreground mb-2">User Input</div>
                            <textarea
                                className="h-40 bg-black/40 border border-white/10 rounded-lg p-3 text-xs text-white/90 font-mono focus:outline-none focus:border-purple-500/50 resize-none custom-scrollbar"
                                value={userPrompt}
                                onChange={(e) => setUserPrompt(e.target.value)}
                                spellCheck={false}
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AdvancedAnalysisResult;
