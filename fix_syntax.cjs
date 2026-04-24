const fs = require('fs');
const p = 'C:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(p, 'utf8');

content = content.replace(
`                            </table>
        </div>
        <div className="flex gap-4 h-1/3 min-h-[250px] shrink-0 border-t border-white/10 pt-2 overflow-hidden">`,
`                            </table>
                        </div>
                    )}
                </div>
                <div className="flex gap-4 h-1/3 min-h-[250px] shrink-0 border-t border-white/10 pt-2 overflow-hidden">`
);

fs.writeFileSync(p, content);
console.log('Fixed syntax error!');