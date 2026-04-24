import sys
import re

def modify():
    with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Imports
    if 'fetchGroups' not in text:
        text = text.replace(
            "import { getUiLang,", 
            "import { fetchGroups, createGroup } from '../services/api';\nimport { getUiLang,"
        )

    # 2. State definition
    state_code = '''
    const [userGroups, setUserGroups] = useState([]);
    const [groupName, setGroupName] = useState('');
    const [showCreateGroup, setShowCreateGroup] = useState(false);

    useEffect(() => {
        if (activeTab === 'groups') {
            fetchGroups().then(data => setUserGroups(data)).catch(console.error);
        }
    }, [activeTab]);

    const handleCreateGroup = async () => {
        if (!groupName) return;
        try {
            await createGroup({ name: groupName });
            setGroupName('');
            setShowCreateGroup(false);
            const data = await fetchGroups();
            setUserGroups(data);
        } catch (e) {
            console.error(e);
        }
    };
'''
    
    if 'const [userGroups, setUserGroups] = useState' not in text:
        text = text.replace(
            "const [activeTab, setActiveTab] = useState('general');",
            "const [activeTab, setActiveTab] = useState('general');\n" + state_code
        )

    # 3. UI Replacement
    
    ui_code = """) : activeTab === 'groups' ? (
                  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                      <section className="bg-black/20 p-4 sm:p-6 rounded-xl border border-white/10 space-y-4 shadow-sm">
                          <div className="flex items-center justify-between">
                              <h2 className="text-lg font-semibold flex items-center gap-2">
                                  <User className="w-5 h-5 text-primary" />
                                  {t('我的用户组', 'My User Groups')}
                              </h2>
                              <button
                                  onClick={() => setShowCreateGroup(!showCreateGroup)}
                                  className="px-3 py-1.5 bg-primary text-black font-bold text-sm rounded hover:bg-primary/90"
                              >
                                  + {t('创建新用户组', 'Create New Group')}
                              </button>
                          </div>
                          {showCreateGroup && (
                              <div className="flex items-center gap-2 mb-4">
                                  <input 
                                      type="text"
                                      placeholder={t('群组名称', 'Group Name')}
                                      className="w-64 px-4 py-2 bg-black/40 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:ring-1 focus:ring-primary focus:border-white/20 transition-all"
                                      value={groupName}
                                      onChange={(e) => setGroupName(e.target.value)}
                                  />
                                  <button onClick={handleCreateGroup} className="px-4 py-2 bg-primary text-black rounded font-medium text-sm">
                                      {t('保存', 'Save')}
                                  </button>
                              </div>
                          )}
                          <div className="rounded-lg border border-white/10 overflow-hidden bg-black/40">
                               <table className="w-full text-left border-collapse text-sm">
                                  <thead>
                                      <tr className="border-b border-white/10 text-muted-foreground">
                                          <th className="p-3">{t('组名', 'Group Name')}</th>
                                          <th className="p-3">{t('身份权限', 'Role / Level')}</th>
                                          <th className="p-3 text-right">{t('当前组积分', 'Group Credits')}</th>
                                      </tr>
                                  </thead>
                                  <tbody>
                                      {userGroups.map(g => (
                                          <tr key={g.group_id} className="border-b border-white/5 hover:bg-white/5">
                                              <td className="p-3 flex items-center gap-2">
                                                  {g.name}
                                                  {g.is_current && <span className="px-1.5 py-0.5 text-[10px] bg-green-500/20 text-green-400 rounded">{t('当前活跃', 'Current')}</span>}
                                              </td>
                                              <td className="p-3">
                                                  {g.permission_level === 2 ? t('管理员', 'Admin') : t('成员', 'Member')}
                                              </td>
                                              <td className="p-3 text-right font-medium text-primary">{g.credits}</td>
                                          </tr>
                                      ))}
                                      {userGroups.length === 0 && (
                                          <tr>
                                              <td colSpan={3} className="p-8 text-center text-muted-foreground">
                                                  {t('暂无群组', 'No Groups')}
                                              </td>
                                          </tr>
                                      )}
                                  </tbody>
                              </table>
                          </div>
                      </section>
                  </div>"""

    # It's safer to use regex to replace everything from ") : activeTab === 'groups' ? (" up to the next ") : null" block or similar closing
    # But since it's exactly the block we saw earlier, let's just find the indices.
    
    start_index = text.find(") : activeTab === 'groups' ? (")
    if start_index != -1:
        # find the end of this block which corresponds to the closing of the section
        # Look for "</section>\n                  </div>"
        end_pattern = "</section>\n                  </div>"
        end_index = text.find(end_pattern, start_index)
        
        if end_index != -1:
            end_index += len(end_pattern)
            text = text[:start_index] + ui_code + text[end_index:]
            print("UI Patched successfully")
        else:
            print("Could not find end of groups block")
    else:
        print("Could not find groups block")

    with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'w', encoding='utf-8') as f:
        f.write(text)

if __name__ == "__main__":
    modify()