import React, { useState, useEffect, useRef } from 'react';
import { fetchScenes, fetchShots, api } from '../services/api';
import { Loader2, Play, Plus, Trash2, Film, Save, Clock, Scissors, ChevronRight, GripVertical, Download } from 'lucide-react';

const VideoStudio = ({ activeEpisode, projectId, onLog }) => {
    const [scenes, setScenes] = useState([]);
    const [shots, setShots] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedSceneId, setSelectedSceneId] = useState('all');
    
    // Playlist State
    const [playlist, setPlaylist] = useState([]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [previewUrl, setPreviewUrl] = useState(null);

    useEffect(() => {
        loadData();
    }, [activeEpisode]);

    const loadData = async () => {
        if (!activeEpisode) return;
        setLoading(true);
        try {
            const scenesData = await fetchScenes(activeEpisode.id);
            setScenes(scenesData);

            // Fetch shots for all scenes in parallel
            const shotsPromises = scenesData.map(scene => fetchShots(scene.id));
            const shotsArrays = await Promise.all(shotsPromises);
            
            // Flatten and filter for videos
            const allShots = shotsArrays.flat().filter(s => s.video_url);
            setShots(allShots);
        } catch (error) {
            console.error(error);
            onLog("Failed to load video assets", "error");
        } finally {
            setLoading(false);
        }
    };

    const addToPlaylist = (shot) => {
        const newItem = {
            id: Date.now() + Math.random().toString(), // Helper ID for list mapping
            shotId: shot.id,
            url: shot.video_url,
            thumbnail: shot.image_url, // Assuming shot has image_url as thumbnail
            shotNumber: shot.shot_number,
            description: shot.description,
            speed: 1.0,
            trimStart: 0,
            trimEnd: 0, // 0 means no trim from end
            originalDuration: shot.duration || 4.0 // Default 4s if unknown
        };
        setPlaylist([...playlist, newItem]);
    };

    const updatePlaylistItem = (id, changes) => {
        setPlaylist(prev => prev.map(item => item.id === id ? { ...item, ...changes } : item));
    };

    const removeFromPlaylist = (id) => {
        setPlaylist(prev => prev.filter(item => item.id !== id));
    };

    const moveItem = (index, direction) => {
        const newPlaylist = [...playlist];
        if (direction === 'up' && index > 0) {
            [newPlaylist[index], newPlaylist[index - 1]] = [newPlaylist[index - 1], newPlaylist[index]];
        }
        if (direction === 'down' && index < newPlaylist.length - 1) {
            [newPlaylist[index], newPlaylist[index + 1]] = [newPlaylist[index + 1], newPlaylist[index]];
        }
        setPlaylist(newPlaylist);
    };

    const handleGenerateMontage = async () => {
        if (playlist.length === 0) return;
        
        setIsGenerating(true);
        setPreviewUrl(null);
        
        try {
            // We'll add this endpoint to api.js later, calling it directly for now or via helper
            const response = await api.post(`/projects/${projectId}/montage`, {
                items: playlist.map(item => ({
                    url: item.url,
                    speed: parseFloat(item.speed),
                    trim_start: parseFloat(item.trimStart),
                    trim_end: parseFloat(item.trimEnd)
                }))
            });
            
            if (response.data.url) {
                setPreviewUrl(response.data.url);
                onLog("Montage generated successfully!", "success");
            }
        } catch (error) {
            console.error(error);
            onLog("Failed to generate montage: " + (error.response?.data?.detail || error.message), "error");
        } finally {
            setIsGenerating(false);
        }
    };

    const filteredShots = selectedSceneId === 'all' 
        ? shots 
        : shots.filter(s => s.scene_id === selectedSceneId);

    // Calculate total estimated duration
    const totalDuration = playlist.reduce((acc, item) => {
        const effectiveDuration = (item.originalDuration - item.trimStart - item.trimEnd) / item.speed;
        return acc + (effectiveDuration > 0 ? effectiveDuration : 0);
    }, 0);

    return (
        <div className="h-full flex flex-col md:flex-row gap-4 p-4 text-gray-100 overflow-hidden">
            {/* Left Panel: Library */}
            <div className="w-full md:w-1/3 flex flex-col bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
                <div className="p-4 border-b border-gray-700 flex justify-between items-center bg-gray-800">
                    <h2 className="font-semibold flex items-center gap-2">
                        <Film size={18} /> Library
                    </h2>
                    <select 
                        className="bg-gray-700 border-none rounded px-2 py-1 text-sm outline-none focus:ring-1 focus:ring-blue-500"
                        value={selectedSceneId}
                        onChange={(e) => setSelectedSceneId(e.target.value)}
                    >
                        <option value="all">All Scenes</option>
                        {scenes.map(s => (
                            <option key={s.id} value={s.id}>Scene {s.scene_number}</option>
                        ))}
                    </select>
                </div>
                
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {loading ? (
                        <div className="flex justify-center p-8"><Loader2 className="animate-spin" /></div>
                    ) : filteredShots.length === 0 ? (
                        <div className="text-gray-500 text-center p-4">No videos found. Generate some shots first!</div>
                    ) : (
                        filteredShots.map(shot => (
                            <div key={shot.id} className="group relative bg-gray-800 rounded border border-gray-700 hover:border-blue-500 transition-colors cursor-pointer overflow-hidden p-2 flex gap-3 items-center" onClick={() => addToPlaylist(shot)}>
                                <div className="w-20 h-12 bg-black rounded overflow-hidden flex-shrink-0 relative">
                                    {shot.image_url ? (
                                        <img src={shot.image_url} alt="" className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center bg-gray-700"><Film size={12}/></div>
                                    )}
                                    <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <Plus className="text-white" size={20} />
                                    </div>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium truncate">Shot {shot.shot_number}</div>
                                    <div className="text-xs text-gray-400 truncate">{shot.description}</div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Right Panel: Timeline / Editor */}
            <div className="flex-1 flex flex-col bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
                <div className="p-4 border-b border-gray-700 flex justify-between items-center bg-gray-800">
                    <h2 className="font-semibold flex items-center gap-2">
                        <Scissors size={18} /> Montage ({playlist.length} clips)
                    </h2>
                    <div className="text-sm text-gray-400 flex items-center gap-2">
                        <Clock size={14} /> Only Est: {totalDuration.toFixed(1)}s
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-950/50">
                    {playlist.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-gray-500 border-2 border-dashed border-gray-800 rounded-lg">
                            <Film size={48} className="mb-4 opacity-20" />
                            <p>Drag clips here or click + from Library</p>
                        </div>
                    ) : (
                        playlist.map((item, index) => (
                            <div key={item.id} className="bg-gray-800 p-3 rounded border border-gray-700 flex flex-col gap-3 group">
                                <div className="flex items-start gap-4">
                                    <div className="flex flex-col gap-1 items-center justify-center pt-2">
                                        <button onClick={() => moveItem(index, 'up')} disabled={index === 0} className="p-1 hover:bg-gray-700 rounded disabled:opacity-20"><ChevronRight className="-rotate-90" size={14} /></button>
                                        <span className="text-xs text-gray-500 font-mono">{index + 1}</span>
                                        <button onClick={() => moveItem(index, 'down')} disabled={index === playlist.length - 1} className="p-1 hover:bg-gray-700 rounded disabled:opacity-20"><ChevronRight className="rotate-90" size={14} /></button>
                                    </div>

                                    {/* Thumbnail Preview */}
                                    <div className="w-32 h-20 bg-black rounded overflow-hidden flex-shrink-0 relative">
                                        {item.thumbnail && <img src={item.thumbnail} className="w-full h-full object-cover opacity-50" />}
                                        <div className="absolute inset-0 flex items-center justify-center">
                                            <span className="text-xs font-mono bg-black/50 px-1 rounded text-white">Shot {item.shotNumber}</span>
                                        </div>
                                    </div>

                                    {/* Controls */}
                                    <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-4">
                                        <div className="flex flex-col gap-1">
                                            <label className="text-xs text-gray-400">Speed</label>
                                            <select 
                                                className="bg-gray-700 border-none rounded px-2 py-1 text-xs"
                                                value={item.speed}
                                                onChange={(e) => updatePlaylistItem(item.id, { speed: e.target.value })}
                                            >
                                                <option value="0.5">0.5x (Slow)</option>
                                                <option value="1.0">1.0x (Normal)</option>
                                                <option value="1.5">1.5x (Fast)</option>
                                                <option value="2.0">2.0x (2x Fast)</option>
                                            </select>
                                        </div>

                                        <div className="flex flex-col gap-1">
                                            <label className="text-xs text-gray-400">Trim Start (s)</label>
                                            <input 
                                                type="number" step="0.1" min="0"
                                                className="bg-gray-700 border-none rounded px-2 py-1 text-xs w-full"
                                                value={item.trimStart}
                                                onChange={(e) => updatePlaylistItem(item.id, { trimStart: parseFloat(e.target.value) || 0 })}
                                            />
                                        </div>

                                        <div className="flex flex-col gap-1">
                                            <label className="text-xs text-gray-400">Trim End (s)</label>
                                            <input 
                                                type="number" step="0.1" min="0"
                                                className="bg-gray-700 border-none rounded px-2 py-1 text-xs w-full"
                                                value={item.trimEnd}
                                                onChange={(e) => updatePlaylistItem(item.id, { trimEnd: parseFloat(e.target.value) || 0 })}
                                            />
                                        </div>
                                        
                                        <div className="flex items-center justify-end">
                                            <button 
                                                onClick={() => removeFromPlaylist(item.id)}
                                                className="p-2 hover:bg-red-900/50 text-red-400 rounded transition-colors"
                                                title="Remove from montage"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>

                <div className="p-4 bg-gray-800 border-t border-gray-700 flex justify-between items-center">
                    <div className="flex items-center gap-4">
                        {previewUrl && (
                             <a href={previewUrl} target="_blank" download className="flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm">
                                <Download size={16} /> Download Montage
                             </a>
                        )}
                    </div>
                    
                    <button 
                        onClick={handleGenerateMontage}
                        disabled={playlist.length === 0 || isGenerating}
                        className="flex items-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        {isGenerating ? <Loader2 className="animate-spin" size={18} /> : <Film size={18} />}
                        {isGenerating ? 'Rendering...' : 'Render Montage'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default VideoStudio;
