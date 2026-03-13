$ErrorActionPreference='Stop'

$src = 'C:\storyboard\AIStory\_kie_all_enum_values_catalog.csv'
if(!(Test-Path $src)){ throw 'missing all enum values catalog' }

$rows = Import-Csv $src

function Is-InputFieldPath([string]$fp){
  if([string]::IsNullOrWhiteSpace($fp)){ return $false }
  $f = $fp.Trim()

  if($f -match '^ApiResponse'){ return $false }
  if($f -match '^paths\.post\.callbacks\.'){ return $false }
  if($f -eq 'paths.post.code'){ return $false }

  if($f -match '^paths\.post\.input\.') { return $true }

  # Direct request-body fields that are not under input.
  if($f -in @(
    'paths.post.model',
    'paths.post.reasoning_effort',
    'paths.post.aspectRatio',
    'paths.post.outputFormat',
    'paths.post.size',
    'paths.post.safetyTolerance',
    'paths.post.fallbackModel'
  )) { return $true }

  # Chat/tool schemas used by request payload.
  if($f -match '^Message\.') { return $true }
  if($f -match '^Tool\.') { return $true }

  return $false
}

$filtered = $rows | Where-Object { Is-InputFieldPath([string]$_.field_path) }
$filtered = $filtered | Sort-Object field_path,title,url -Unique

$outCsv = 'C:\storyboard\AIStory\_kie_input_enum_values_catalog.csv'
$outMd = 'C:\storyboard\AIStory\_kie_input_enum_values_catalog.md'

$filtered | Export-Csv -Path $outCsv -NoTypeInformation -Encoding UTF8

$lines=@()
$lines+='# KIE Input Enum Values Catalog'
$lines+="Generated at: $(Get-Date -Format s)"
$lines+="Rows: $($filtered.Count)"
$lines+=''

$g=$filtered|Group-Object field_path|Sort-Object Count -Descending
$lines+="Unique input field paths: $($g.Count)"
$lines+='Top input field paths by page count:'
foreach($x in ($g|Select-Object -First 25)){
  $lines += "- $($x.Name): $($x.Count)"
}

$lines+=''
$lines+='| field_path | model page | value_count | enum_values |'
$lines+='|---|---|---|---|'
foreach($r in $filtered){
  $vals=@($r.field_path,$r.title,$r.value_count,$r.enum_values)
  $vals=$vals|ForEach-Object{([string]$_).Replace('|','/').Trim()}
  $lines += "| $($vals[0]) | $($vals[1]) | $($vals[2]) | $($vals[3]) |"
}

Set-Content -Path $outMd -Value $lines -Encoding UTF8

Write-Output "Generated: $outCsv"
Write-Output "Generated: $outMd"
Write-Output "Rows: $($filtered.Count)"
Write-Output "Unique input field paths: $($g.Count)"
$g|Select-Object -First 15|ForEach-Object{ Write-Output ("- {0}: {1}" -f $_.Name,$_.Count) }
