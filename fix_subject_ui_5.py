import sys

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("t('Sync from Source Entity', 'Sync from Source Entity')", "t('从源实体同步', 'Sync from Source Entity')")
content = content.replace("t('View History', 'View History')", "t('历史记录', 'View History')")
content = content.replace("t('Entity History', 'Entity History')", "t('实体历史', 'Entity History')")
content = content.replace("t('Snapshot', 'Snapshot')", "t('普通快照', 'Snapshot')")
content = content.replace("t('Restore', 'Restore')", "t('恢复到此版本', 'Restore')")
content = content.replace("t('No history records found.', 'No history records found.')", "t('暂无历史记录。', 'No history records found.')")

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied to SubjectLibrary.jsx successfully!")
