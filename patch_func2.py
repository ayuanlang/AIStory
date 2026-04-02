import re

content = open('frontend/src/components/FunctionApiConfigTab.jsx', 'r', encoding='utf-8').read()

# Update handleSave map
replacement = '''            const items = configs[funcName].map(item => {
                let langs = item.applicable_languages;
                if (typeof langs === 'string') {
                    langs = langs.split(',').map(s => s.trim()).filter(Boolean);
                }
                return {
                    system_api_id: parseInt(item.system_api_id, 10),
                    priority: parseInt(item.priority, 10) || 0,
                    is_fallback: Boolean(item.is_fallback),
                    alias: item.alias || null,
                    applicable_languages: langs && langs.length > 0 ? langs : null,
                    explicit_selection: Boolean(item.explicit_selection),
                    strict_provider: Boolean(item.strict_provider)
                };
            }).filter(item => !isNaN(item.system_api_id));'''

content = re.sub(
    r'const items = configs\[funcName\]\.map\(item => \(\{(.*?)\}\)\)\.filter\(item => !isNaN\(item\.system_api_id\)\);',
    replacement,
    content,
    flags=re.DOTALL
)

# Update UI
lang_input = '''
                                            <div className="flex-1 mt-2 md:mt-0">
                                                <input
                                                    type="text"
                                                    value={Array.isArray(item.applicable_languages) ? item.applicable_languages.join(', ') : (item.applicable_languages || '')}
                                                    onChange={(e) => handleChangeParams(funcName, originalIndex, 'applicable_languages', e.target.value)}
                                                    className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50"
                                                    placeholder="适用语言 (逗号分隔，留空适用全部)"
                                                />
                                            </div>
'''
if '适用语言' not in content:
    content = content.replace(
        'placeholder="填写别名 (用于下拉框和Settings显示)"\n                                                />\n                                            </div>',
        'placeholder="填写别名 (用于下拉框和Settings显示)"\n                                                />\n                                            </div>\n' + lang_input
    )

with open('frontend/src/components/FunctionApiConfigTab.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
