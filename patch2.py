import re

with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

start_str = ") : activeTab === 'groups' ? ("
end_str = "暂无群组', 'No Groups')}"
# Wait, let's just find "activeTab === 'groups' ? (" because it may not have ") : " before it in some versions...
# Let's search with regex
pattern = r"\) : activeTab === 'groups' \? \([\s\S]*?</table>\s*</div>\s*</section>\s*</div>"
match = re.search(pattern, text)
print("Match found:", bool(match))
if match:
    start, end = match.span()
    print("Replacing snippet of length", end - start)
    
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
                  
    with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'w', encoding='utf-8') as f:
        f.write(text[:start] + ui_code + text[end:])
    print("File saved")
else:
    print("Could not find the block, maybe the indentation is different?")
    # print out the surrounding text around 'Front-end management'
    idx = text.find("Frontend management")
    if idx != -1:
        print("Context:", text[idx-100:idx+400])
