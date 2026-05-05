$content = Get-Content -Path 'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx' -Raw
$content = $content -replace "浠庢簮瀹炰綋鍚屾", "从源实体同步"
$content = $content -replace "鍘嗗彶璁板綍", "历史记录"
$content = $content -replace "瀹炰綋鍘嗗彶", "实体历史"
$content = $content -replace "鏆傛棤鍘嗗彶璁板綍", "暂无历史记录。"
$content = $content -replace "鏅€氬北浠\?", "普通快照"
$content = $content -replace "鎭㈠鎴愬姛", "恢复成功！"
$content = $content -replace "鎭㈠", "恢复版本"
$content = $content -replace "鍚屾鎴愬姛", "同步成功！"
$content = $content -replace "纭畾瑕佹仮澶嶃€\?", "确定要恢复吗？"
[IO.File]::WriteAllText('c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', $content, [Text.Encoding]::UTF8)
