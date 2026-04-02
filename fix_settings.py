import re

with open('frontend/src/pages/Settings.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

state_old = 'const [systemSettings, setSystemSettings] = useState([]);'
state_new = '''const [systemSettings, setSystemSettings] = useState([]);
    const [functionApiConfigs, setFunctionApiConfigs] = useState([]);'''
if 'functionApiConfigs' not in text:
    text = text.replace(state_old, state_new)

fetch_old = 'const [userRes, systemRes] = await Promise.all([fetchMe(), getSystemSettings()]);'
fetch_new = 'const [userRes, systemRes, funcConfigs] = await Promise.all([fetchMe(), getSystemSettings(), getFunctionApiConfigs().catch(()=>[])]);\n            setFunctionApiConfigs(Array.isArray(funcConfigs) ? funcConfigs : []);'
text = text.replace(fetch_old, fetch_new)

new_sec = '''
                        <div className="mt-8 rounded-xl border border-blue-400/30 bg-blue-500/10 p-4">
                            <h2 className="text-2xl font-extrabold tracking-wide text-blue-200">{t('功能专属 API 默认激活', 'Function-specific API Default Activation')}</h2>
                            <p className="text-xs text-blue-100/80 mt-1">{t('选择各功能的默认 API，将保存到你的本地用户设置中。', 'Select default API for each function to save to your local preferences.')}</p>
                        </div>
                        <div className="bg-black/20 p-4 sm:p-6 rounded-xl border border-blue-400/20 space-y-4 shadow-sm">
                            {functionApiConfigs.map(funcConfig => {
                                const funcName = funcConfig.function_name;
                                const apiList = funcConfig.api_settings || [];
                                const storageKey = 'func_api_' + funcName;
                                const currentVal = Number(localStorage.getItem(storageKey)) || '';
                                
                                return (
                                    <div key={funcName} className="flex flex-col md:flex-row md:items-center justify-between p-3 bg-white/5 border border-white/10 rounded-lg gap-2">
                                        <div className="text-sm font-medium text-white/90">{funcName}</div>
                                        <select
                                            value={currentVal || ''}
                                            onChange={(e) => {
                                                const val = e.target.value;
                                                localStorage.setItem(storageKey, val);
                                                setFunctionApiConfigs([...functionApiConfigs]); // trigger re-render
                                            }}
                                            className="bg-[#111114] border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50 min-w-[200px]"
                                        >
                                            <option value="">-- {t('系统默认', 'System Default')} --</option>
                                            {apiList.map((api, idx) => {
                                                let label = api.alias ? api.alias : ('API ID: ' + api.system_api_id);
                                                if (api.applicable_languages && api.applicable_languages.length > 0) {
                                                    label += ' (' + api.applicable_languages.join(', ') + ')';
                                                }
                                                return (
                                                    <option key={idx} value={api.system_api_id}>
                                                        {label}
                                                    </option>
                                                );
                                            })}
                                        </select>
                                    </div>
                                );
                            })}
                            {functionApiConfigs.length === 0 && <div className="text-sm text-gray-500">{t('暂无功能 API 配置', 'No function API configs available')}</div>}
                        </div>
                    </div>
                </div>
            ) : null}'''

# Find the LAST occurrence of ') : null}'
if 'Function-specific API Default' not in text:
    last_idx = text.rfind(') : null}')
    if last_idx != -1:
        text = text[:last_idx-16] + new_sec + text[last_idx+9:]
        print('Patched successfully!')
    else:
        print('Could not find ) : null}')

with open('frontend/src/pages/Settings.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
