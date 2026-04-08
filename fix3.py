import sys

file_path = 'C:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace("JSON.parse(editingShot.technical_notes or '{}')", "JSON.parse(editingShot.technical_notes || '{}')")
c = c.replace("if (onLog) onLog(f'Failed to apply generated media: {e.message}', 'error');", "if (onLog) onLog(`Failed to apply generated media: ${e.message}`, 'error');")
c = c.replace("if (onLog) onLog(`Failed to apply generated media: `, 'error');", "if (onLog) onLog(`Failed to apply generated media: ${e.message}`, 'error');")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(c)

print('Syntax fixed.')
