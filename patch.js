const fs = require('fs');
let code = fs.readFileSync('frontend/src/components/AssetsLibrary.jsx', 'utf8');

const stateHooks = `
    const [assets, setAssets] = useState([]);
    const [isSourceIds, setIsSourceIds] = useState(new Set());
    const [isDependentIds, setIsDependentIds] = useState(new Set());
`;
code = code.replace('const [assets, setAssets] = useState([]);', stateHooks);

const oldTryCatch = `        try {
            const data = await fetchAssets();
            // Ensure meta_info is always an object
            const cleanData = data.map(a => {
                let meta = a.meta_info;
                if (typeof meta === 'string') {
                    try { meta = JSON.parse(meta); } catch (e) { meta = {}; }
                }
                return { ...a, meta_info: meta || {} };
            });
            setAssets(cleanData);
            addLog(\`Loaded \${cleanData.length} assets from library.\`);`;

const newTryCatch = `        try {
            const data = await fetchAssets();
            const cleanData = data.map(a => {
                let meta = a.meta_info;
                if (typeof meta === 'string') {
                    try { meta = JSON.parse(meta); } catch (e) { meta = {}; }
                }
                return { ...a, meta_info: meta || {} };
            });
            setAssets(cleanData);
            
            try {
                const depPayload = await fetchUnreferencedAssetIds();
                const sourceIds = (depPayload?.is_source_ids || []).map(id => Number(id));
                const dependentIds = (depPayload?.is_dependent_ids || []).map(id => Number(id));
                setIsSourceIds(new Set(sourceIds));
                setIsDependentIds(new Set(dependentIds));
            } catch(e) { console.warn('dep load failed', e); }

            addLog(\`Loaded \${cleanData.length} assets from library.\`);`;

code = code.replace(oldTryCatch, newTryCatch);

const oldItem = `<AssetItem 
                                        key={item.id}
                                        asset={item}
                                        onClick={handleAssetClick}
                                        onDelete={handleDelete}
                                        isManageMode={isManageMode}
                                        isSelected={selectedIds.has(item.id)}
                                        onToggleSelect={handleToggleSelect}
                                        onReportError={() => addLog('Removed broken legacy image.')}
                                        t={t}
                                    />`;
const newItem = `<AssetItem 
                                        key={item.id}
                                        asset={item}
                                        onClick={handleAssetClick}
                                        onDelete={handleDelete}
                                        isManageMode={isManageMode}
                                        isSelected={selectedIds.has(item.id)}
                                        onToggleSelect={handleToggleSelect}
                                        onReportError={() => addLog('Removed broken legacy image.')}
                                        t={t}
                                        isSource={isSourceIds.has(item.id)}
                                        isDependent={isDependentIds.has(item.id)}
                                    />`;
code = code.replace(oldItem, newItem);

code = code.replace(
    'const AssetItem = React.memo(({ asset, onClick, onDelete, isManageMode, isSelected, onToggleSelect, onReportError, t }) => {',
    'const AssetItem = React.memo(({ asset, onClick, onDelete, isManageMode, isSelected, onToggleSelect, onReportError, t, isSource, isDependent }) => {'
);

const uiAnchor = `<div className="absolute top-2 right-2 flex flex-col gap-2 z-10">`;
const badgesHtml = `
            <div className="absolute top-2 left-2 flex flex-col gap-1 z-10">
                {isSource && (
                    <div className="px-2 py-1 rounded bg-green-500/80 text-white text-[10px] font-bold shadow-sm" title="Source (Depended upon)">
                        SRC
                    </div>
                )}
                {isDependent && (
                    <div className="px-2 py-1 rounded bg-purple-500/80 text-white text-[10px] font-bold shadow-sm" title="Derived (Depends on others)">
                        DER
                    </div>
                )}
            </div>

            <div className="absolute top-2 right-2 flex flex-col gap-2 z-10">`;

code = code.replace(uiAnchor, badgesHtml);

fs.writeFileSync('frontend/src/components/AssetsLibrary.jsx', code);
console.log('Patch complete.');
