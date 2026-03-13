$ErrorActionPreference='Stop'
$src='C:\storyboard\AIStory\_kie_all_models_param_matrix_vetted_clean.csv'
if(!(Test-Path $src)){ throw 'missing clean matrix' }
$rows=Import-Csv $src
$urls=$rows|Select-Object -ExpandProperty url -Unique
$targets=@('aspect_ratio','resolution','output_format','duration','mode')
$out=@()

function Normalize-Value([string]$field, [string]$value){
  $v=[string]$value
  if([string]::IsNullOrWhiteSpace($v)){ return '' }
  $v=($v -replace '^["''\s]+|["''\s]+$','').Trim().ToLower()
  $v=$v -replace '\s+',' '

  switch($field){
    'aspect_ratio' {
      if($v -match '^\d{1,2}:\d{1,2}$' -or $v -in @('auto','portrait','landscape')){ return $v }
      return ''
    }
    'resolution' {
      if($v -match '^(\d{3,4}p|\d{1,2}k)$'){ return $v }
      if($v -in @('landscape_16_9','landscape_4_3','portrait_16_9','portrait_4_3','square','square_hd')){ return $v }
      return ''
    }
    'output_format' {
      if($v -in @('jpg','jpeg','png','webp','bmp','gif','mp4','mov','webm','wav','mp3','flac','aac')){ return $v }
      return ''
    }
    'duration' {
      # Keep clean, enum-like duration values (e.g., 5, 10, 5s, 10s, 5 seconds).
      if($v -match '^(\d{1,2})(?:\s*(s|sec|secs|second|seconds))?$'){
        return $Matches[1]
      }
      return ''
    }
    'mode' {
      if($v -in @('std','standard','pro','fast','turbo','master','quality','basic','high','multi_shots','storyboard','upscale','normal','fun','spicy')){ return $v }
      return ''
    }
    default {
      return ''
    }
  }
}

foreach($u in $urls){
  try{ $c=(Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 40).Content }catch{ continue }
  $lines=$c -split "`n"
  $title=''
  $m=[regex]::Match($c,'(?m)^#\s+(.+)$')
  if($m.Success){ $title=$m.Groups[1].Value.Trim() }

  foreach($f in $targets){
    $idxs=@()
    for($i=0;$i -lt $lines.Count;$i++){
      $ln=($lines[$i]-replace '\r','')
      if($ln -match "(?i)\b$f\b"){ $idxs += $i }
    }
    if($idxs.Count -eq 0){ continue }

    $enumVals=@()
    foreach($idx in $idxs){
      $start=[Math]::Max(0,$idx)
      $end=[Math]::Min($lines.Count-1,$idx+100)
      $block=($lines[$start..$end] -join "`n")

      if($block -match '(?is)enum\s*:\s*(.+?)(?:\n\s*[a-zA-Z_][a-zA-Z0-9_]*\s*:|\n\s*required\s*:|\n\s*x-apidog-orders\s*:|\n\s*example\s*:|\z)'){
        $enumSec=$Matches[1]
        [regex]::Matches($enumSec,'(?m)^\s*-\s*([^\r\n#]+)') | ForEach-Object {
          $v=$_.Groups[1].Value.Trim(" '")
          if($v){ $enumVals += $v }
        }
      }

      if($block -match '(?is)Allowed values\s*:\s*(.+?)(?:\n\s*Default\s*:|\n\s*Example\s*:|\n\s*[A-Za-z_][A-Za-z0-9_]*\s*$|\z)'){
        $avSec=$Matches[1]
        [regex]::Matches($avSec,'(?m)^\s*([0-9A-Za-z:_\-\.]+)\s*$') | ForEach-Object {
          $v=$_.Groups[1].Value.Trim()
          if($v -and $v -notmatch '^(Allowed|Default|Example)$'){ $enumVals += $v }
        }
      }
    }

    $enumVals=$enumVals|Where-Object{$_ -and $_ -notmatch '^type:|^description:'}|Sort-Object -Unique
    if($enumVals.Count -gt 0){
      $out += [PSCustomObject]@{
        title=$title
        url=$u
        field=$f
        allowed_values=($enumVals -join '; ')
        value_count=$enumVals.Count
      }
    }
  }
}

$out=$out|Sort-Object field,title
$csv='C:\storyboard\AIStory\_kie_field_allowed_values_catalog.csv'
$md='C:\storyboard\AIStory\_kie_field_allowed_values_catalog.md'
$out|Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8

$clean=@()
foreach($r in $out){
  $vals=([string]$r.allowed_values -split ';') | ForEach-Object { $_.Trim() }
  $kept=@()
  foreach($x in $vals){
    $n=Normalize-Value -field ([string]$r.field) -value $x
    if($n){ $kept += $n }
  }
  $kept=$kept|Sort-Object -Unique
  if($kept.Count -gt 0){
    $clean += [PSCustomObject]@{
      field=[string]$r.field
      title=[string]$r.title
      url=[string]$r.url
      allowed_values=($kept -join '; ')
      value_count=$kept.Count
    }
  }
}

$clean=$clean|Sort-Object field,title
$cleanCsv='C:\storyboard\AIStory\_kie_field_allowed_values_catalog_clean.csv'
$cleanMd='C:\storyboard\AIStory\_kie_field_allowed_values_catalog_clean.md'
$clean|Export-Csv -Path $cleanCsv -NoTypeInformation -Encoding UTF8

$lines=@()
$lines+='# KIE Field Allowed Values Catalog'
$lines+="Generated at: $(Get-Date -Format s)"
$lines+="Rows: $($out.Count)"
$lines+=''
$g=$out|Group-Object field|Sort-Object Name
foreach($x in $g){ $lines+="- $($x.Name): $($x.Count) pages with enums" }
$lines+=''
$lines+='| field | model page | value_count | allowed_values |'
$lines+='|---|---|---|---|'
foreach($r in $out){
  $vals=@($r.field,$r.title,$r.value_count,$r.allowed_values)
  $vals=$vals|ForEach-Object{([string]$_).Replace('|','/').Trim()}
  $lines += "| $($vals[0]) | $($vals[1]) | $($vals[2]) | $($vals[3]) |"
}
Set-Content -Path $md -Value $lines -Encoding UTF8

$lines2=@()
$lines2+='# KIE Field Allowed Values Catalog (Cleaned)'
$lines2+="Generated at: $(Get-Date -Format s)"
$lines2+="Rows: $($clean.Count)"
$lines2+=''
$g2=$clean|Group-Object field|Sort-Object Name
foreach($x in $g2){ $lines2+="- $($x.Name): $($x.Count) pages" }
$lines2+=''
$lines2+='| field | model page | value_count | allowed_values |'
$lines2+='|---|---|---|---|'
foreach($r in $clean){
  $vals=@($r.field,$r.title,$r.value_count,$r.allowed_values)
  $vals=$vals|ForEach-Object{([string]$_).Replace('|','/').Trim()}
  $lines2 += "| $($vals[0]) | $($vals[1]) | $($vals[2]) | $($vals[3]) |"
}
Set-Content -Path $cleanMd -Value $lines2 -Encoding UTF8

Write-Output "Generated: $csv"
Write-Output "Generated: $md"
Write-Output "Rows: $($out.Count)"
$g|ForEach-Object{ Write-Output ("- {0}: {1}" -f $_.Name,$_.Count) }
Write-Output "Generated: $cleanCsv"
Write-Output "Generated: $cleanMd"
Write-Output "Clean Rows: $($clean.Count)"
$g2|ForEach-Object{ Write-Output ("- clean {0}: {1}" -f $_.Name,$_.Count) }
