import sys

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("t('浠庢簮瀹炰綋鍚屾', 'Sync from Source Entity')", "t('从源实体同步', 'Sync from Source Entity')")
content = content.replace("t('鍘嗗彶璁板綍', 'View History')", "t('历史记录', 'View History')")
content = content.replace("t('瀹炰綋鍘嗗彶', 'Entity History')", "t('实体历史', 'Entity History')")
content = content.replace("t('鏆傛棤鍘嗗彶璁板綍', 'No history records found.')", "t('暂无历史记录。', 'No history records found.')")
content = content.replace("t('鏅€氬北浠?', 'Snapshot')", "t('普通快照', 'Snapshot')")
content = content.replace("t('鎭㈠', 'Restore')", "t('恢复到此版本', 'Restore')")
content = content.replace("t('鎭㈠鎴愬姛', 'Restored successfully!')", "t('恢复成功！', 'Restored successfully!')")
content = content.replace("t('鍚屾鎴愬姛', 'Synced successfully!')", "t('同步成功！', 'Synced successfully!')")
content = content.replace("t('纭畾瑕佹仮澶嶃€?', 'Are you sure you want to restore?')", "t('确定要恢复此历史版本吗？', 'Are you sure you want to restore?')")

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Translations fixed!")
