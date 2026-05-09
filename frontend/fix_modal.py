import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Very aggressive replacement
import sys

start_idx = text.find('{showAiEntityCreateModal && (')
if start_idx == -1:
    print("Start not found")
    sys.exit()

end_idx = text.find('</AnimatePresence>', start_idx)

if end_idx == -1:
    print("End not found")
    sys.exit()
    
# go backwards to find the opening AnimatePresence
start_idx = text.rfind('<AnimatePresence>', 0, start_idx)

replacement = '''<AnimatePresence>
                {showAiEntityCreateModal && (
                    <AiEntityCreateDialog
                        isOpen={showAiEntityCreateModal}
                        onClose={() => setShowAiEntityCreateModal(false)}
                        onGenerateText={handleGenerateEntityFromText}
                        onGenerateImage={handleGenerateEntityFromImage}
                        onGenerateDerived={handleGenerateDerivedEntity}
                        entities={allEntities}
                        isGeneratingRow={isGeneratingRow}
                    />
                )}
            </AnimatePresence>'''

new_text = text[:start_idx] + replacement + text[end_idx + len('</AnimatePresence>'):]

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(new_text)
print("Replaced successfully via find/replace.")
