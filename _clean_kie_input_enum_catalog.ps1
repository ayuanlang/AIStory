$ErrorActionPreference='Stop'

$src = 'C:\storyboard\AIStory\_kie_input_enum_values_catalog.csv'
if(!(Test-Path $src)){ throw 'missing input enum catalog' }

$rows = Import-Csv $src

function Canonical-Field([string]$f){
  if([string]::IsNullOrWhiteSpace($f)){ return '' }
  $x = $f.Trim()
  switch ($x) {
    'paths.post.aspectRatio' { return 'paths.post.input.aspect_ratio' }
    'paths.post.outputFormat' { return 'paths.post.input.output_format' }
    'paths.post.size' { return 'paths.post.input.size' }
    'paths.post.safetyTolerance' { return 'paths.post.input.safety_tolerance' }
    default { return $x }
  }
}

function Keep-Field([string]$f){
  if($f -match '^paths\.post\.input\.') { return $true }
  if($f -in @('paths.post.model','paths.post.fallbackModel','paths.post.reasoning_effort')) { return $true }
  return $false
}

function Clean-Value([string]$field, [string]$value){
  $v = [string]$value
  if([string]::IsNullOrWhiteSpace($v)){ return '' }
  $v = $v.Trim()
  $v = $v -replace '^[\s''"]+|[\s''"]+$',''
  $v = $v -replace '\s+',' '

  switch -Regex ($field) {
    'aspect_ratio$' {
      $t = $v.ToLower()
      if($t -match '^\d{1,2}:\d{1,2}$' -or $t -in @('auto','portrait','landscape')){ return $t }
      return ''
    }
    '(^|\.)duration$|n_frames$|num_images$|upscale_factor$|acceleration$|rendering_speed$' {
      if($v -match '^(\d{1,2})(?:\s*(s|sec|secs|second|seconds))?$'){ return $Matches[1] }
      return ''
    }
    'resolution$|image_resolution$' {
      $t = $v.ToLower()
      if($t -match '^(\d{3,4}p|\d{1,2}k|\d{3,4}x\d{3,4})$'){ return $t }
      return ''
    }
    '(^|\.)size$|image_size$' {
      $t = $v.ToLower()
      if($t -match '^\d{1,2}:\d{1,2}$' -or $t -match '^\d{3,4}x\d{3,4}$'){ return $t }
      if($t -in @('auto','landscape','portrait','square')){ return $t }
      return ''
    }
    '(^|\.)mode$' {
      $t = $v.ToLower()
      if($t -in @('std','standard','pro','fast','turbo','master','quality','basic','high','normal','fun','spicy','storyboard','upscale')){ return $t }
      return ''
    }
    'quality$' {
      $t = $v.ToLower()
      if($t -in @('basic','standard','high','quality','fast','pro','turbo','medium')){ return $t }
      return ''
    }
    'style$' {
      return $v.ToUpper()
    }
    'output_format$' {
      $t = $v.ToLower()
      if($t -in @('jpg','jpeg','png','webp','bmp','gif','mp4','mov','webm','wav','mp3','flac','aac','url','b64_json')){ return $t }
      return ''
    }
    'reasoning_effort$' {
      $t = $v.ToLower()
      if($t -in @('low','medium','high')){ return $t }
      return ''
    }
    'voice$' {
      $t = $v.Trim()
      if($t.Length -ge 2 -and $t.Length -le 80){ return $t }
      return ''
    }
    'model$|fallbackModel$' {
      $t = $v.ToLower()
      if($t -match '^[a-z0-9][a-z0-9\-\./]{2,100}$'){
        if($t -notin @('assistant','user','system','tool','function','developer','text','type','string')){ return $t }
      }
      return ''
    }
    default {
      # Conservative fallback for unknown input fields.
      if($v.Length -le 120){ return $v }
      return ''
    }
  }
}

# aggregate by canonical field + page
$agg = @{}
foreach($r in $rows){
  $f = Canonical-Field ([string]$r.field_path)
  if(-not (Keep-Field $f)){ continue }

  $vals = @(([string]$r.enum_values -split ';') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  if($vals.Count -eq 0){ continue }

  $cleanVals = @()
  foreach($x in $vals){
    $cv = Clean-Value -field $f -value $x
    if($cv){ $cleanVals += $cv }
  }
  $cleanVals = $cleanVals | Sort-Object -Unique
  if($cleanVals.Count -eq 0){ continue }

  $k = "{0}|{1}|{2}" -f $f,([string]$r.title),([string]$r.url)
  if(-not $agg.ContainsKey($k)){
    $agg[$k] = [PSCustomObject]@{
      field_path = $f
      title = [string]$r.title
      url = [string]$r.url
      values = New-Object System.Collections.Generic.List[string]
    }
  }

  foreach($v in $cleanVals){
    if(-not $agg[$k].values.Contains($v)){ $agg[$k].values.Add($v) }
  }
}

$out = @()
foreach($kv in $agg.GetEnumerator()){
  $vals = @($kv.Value.values | Sort-Object -Unique)
  $out += [PSCustomObject]@{
    field_path = $kv.Value.field_path
    title = $kv.Value.title
    url = $kv.Value.url
    enum_values = ($vals -join '; ')
    value_count = $vals.Count
  }
}

$out = $out | Sort-Object field_path,title,url

$outCsv = 'C:\storyboard\AIStory\_kie_input_enum_values_catalog_purified.csv'
$outMd = 'C:\storyboard\AIStory\_kie_input_enum_values_catalog_purified.md'
$out | Export-Csv -Path $outCsv -NoTypeInformation -Encoding UTF8

$lines=@()
$lines+='# KIE Input Enum Values Catalog (Purified)'
$lines+="Generated at: $(Get-Date -Format s)"
$lines+="Rows: $($out.Count)"
$lines+=''
$g=$out|Group-Object field_path|Sort-Object Count -Descending
$lines+="Unique input field paths: $($g.Count)"
$lines+='Top input field paths by page count:'
foreach($x in ($g|Select-Object -First 30)){
  $lines += "- $($x.Name): $($x.Count)"
}
$lines+=''
$lines+='| field_path | model page | value_count | enum_values |'
$lines+='|---|---|---|---|'
foreach($r in $out){
  $vals=@($r.field_path,$r.title,$r.value_count,$r.enum_values)
  $vals=$vals|ForEach-Object{([string]$_).Replace('|','/').Trim()}
  $lines += "| $($vals[0]) | $($vals[1]) | $($vals[2]) | $($vals[3]) |"
}
Set-Content -Path $outMd -Value $lines -Encoding UTF8

Write-Output "Generated: $outCsv"
Write-Output "Generated: $outMd"
Write-Output "Rows: $($out.Count)"
Write-Output "Unique input field paths: $($g.Count)"
$g|Select-Object -First 15|ForEach-Object{ Write-Output ("- {0}: {1}" -f $_.Name,$_.Count) }
