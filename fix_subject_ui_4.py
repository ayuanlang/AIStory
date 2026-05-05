import sys
import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

print("Environment Details found?", 'Environment Details' in content)

ui = '''                                      {/* Sync & History Options */}
                                      <div className="pt-4 border-t border-white/10 flex items-center justify-between">
                                          {viewingEntity.existing_id ? (
                                              <button 
                                                  onClick={() => handleSyncFromOld(viewingEntity.id, viewingEntity.existing_id)}
                                                  className="px-3 py-1.5 text-xs font-medium bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 rounded border border-blue-500/30 transition-colors"
                                              >
                                                  {t('Sync from Source Entity', 'Sync from Source Entity')}
                                              </button>
                                          ) : (
                                              <div></div>
                                          )}
                                          <button 
                                              onClick={() => handleLoadHistory(viewingEntity.id)}
                                              className="px-3 py-1.5 text-xs font-medium bg-white/5 text-white/70 hover:bg-white/10 hover:text-white rounded border border-white/10 transition-colors"
                                          >
                                              {t('View History', 'View History')}
                                          </button>
                                      </div>
'''
if 'Sync & History Options' not in content:
    content = re.sub(r'(\s+)({\/\* Environment Details \*\/})', r'\1' + ui + r'\1\2', content)

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied to SubjectLibrary.jsx successfully!")
