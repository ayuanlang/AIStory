const fs = require('fs');
const p = 'C:/AS/AIStory/frontend/src/pages/editor/components/ShotsView.jsx';
let content = fs.readFileSync(p, 'utf8');

const regex1 = /\{renderDetailActionButton\(\{\s*label:\s*t\('生成视频',\s*'Generate Video'\),\s*busyLabel:\s*t\('视频生成中\.\.\.',\s*'Generating Video\.\.\.'\)/;

const newStr1 = `{assetDetailModal.type === 'video' && (
                                                                        <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer select-none">
                                                                            <input 
                                                                                type="checkbox" 
                                                                                checked={isDraftMode}
                                                                                onChange={(e) => setIsDraftMode(e.target.checked)}
                                                                                className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
                                                                            />
                                                                            {t('草稿(480p)', 'Draft (480p)')}
                                                                        </label>
                                                                    )}
                                                                    {renderDetailActionButton({
                                                                        label: t('生成视频', 'Generate Video'),
                                                                        busyLabel: t('视频生成中...', 'Generating Video...')`;

if (regex1.test(content)) {
    content = content.replace(regex1, newStr1);
    console.log('Patched modal generate button');
} else {
    console.log('regex1 not matched');
}

const regex2 = /<option value="entity_refs">\{t\('实体参考图模式', 'Entity Refs Mode'\)\}<\/option>\s*<\/select>\s*<button \s*onClick=\{\(\) => generateAssetWithLang\('video'\)\}/;
const newStr2 = `<option value="entity_refs">{t('实体参考图模式', 'Entity Refs Mode')}</option>
                                                </select>

                                                <label className="flex items-center gap-1 text-[10px] text-gray-300 hover:text-white cursor-pointer select-none ml-1 mr-1">
                                                    <input 
                                                        type="checkbox" 
                                                        className="hidden"
                                                        checked={isDraftMode}
                                                        onChange={(e) => setIsDraftMode(e.target.checked)}
                                                    />
                                                    <div className={\`w-2.5 h-2.5 rounded-sm border flex items-center justify-center transition-colors \${isDraftMode ? 'bg-primary border-primary' : 'border-white/30 hover:border-white/50 bg-black/20'}\`}>
                                                        {isDraftMode && <Check className="w-2 h-2 text-white" />}
                                                    </div>
                                                    <span className={isDraftMode ? 'text-primary font-medium' : 'text-gray-400 font-medium'}>{t('草稿', 'Draft')}</span>
                                                </label>

                                                <button 
                                                    onClick={() => generateAssetWithLang('video')}`;

if (regex2.test(content)) {
    content = content.replace(regex2, newStr2);
    console.log('Patched edit pane generate button');
} else {
    console.log('regex2 not matched');
}

fs.writeFileSync(p, content, 'utf8');
