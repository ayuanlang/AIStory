$ErrorActionPreference='Stop'

$src='C:\storyboard\AIStory\_kie_all_models_param_matrix_vetted_clean.csv'
if(!(Test-Path $src)){ throw 'missing clean matrix source csv' }

$rows=Import-Csv $src
$urls=$rows|Select-Object -ExpandProperty url -Unique

$out=@()

function Normalize-EnumItem([string]$v){
  if([string]::IsNullOrWhiteSpace($v)){ return '' }
  $x=[string]$v
  $x=$x.Trim()
  $x=$x -replace '^[\s''"]+|[\s''"]+$',''
  $x=$x -replace '\s+',' '
  return $x
}

function Compress-Path([string[]]$parts){
  if(-not $parts -or $parts.Count -eq 0){ return '' }

  $drop=@(
    'requestbody','content','application/json','application/xml','schema','properties',
    'responses','headers','items','anyof','oneof','allof','components','schemas'
  )

  $kept=@()
  foreach($p in $parts){
    $pp=([string]$p).Trim()
    if(-not $pp){ continue }
    if($drop -contains $pp.ToLower()){ continue }
    if($pp -match '^\d{3}$'){ continue }
    $kept += $pp
  }

  if($kept.Count -eq 0){
    return ($parts -join '.')
  }
  return ($kept -join '.')
}

foreach($u in $urls){
  try{
    $c=(Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 50).Content
  }catch{
    continue
  }

  $title=''
  $tm=[regex]::Match($c,'(?m)^#\s+(.+)$')
  if($tm.Success){ $title=$tm.Groups[1].Value.Trim() }

  $lines=$c -split "`n"
  $stack=New-Object System.Collections.ArrayList

  for($i=0; $i -lt $lines.Count; $i++){
    $raw=($lines[$i] -replace '\r','')
    if([string]::IsNullOrWhiteSpace($raw)){ continue }

    # YAML-like key line: key: value
    $km=[regex]::Match($raw,'^(?<indent>\s*)(?<key>[A-Za-z_][A-Za-z0-9_\-\./]*)\s*:\s*(?<val>.*)$')
    if($km.Success){
      $indent=$km.Groups['indent'].Value.Length
      $key=$km.Groups['key'].Value.Trim()
      $val=$km.Groups['val'].Value.Trim()

      while($stack.Count -gt 0 -and [int]$stack[$stack.Count-1].indent -ge $indent){
        $stack.RemoveAt($stack.Count-1) | Out-Null
      }

      if($key.ToLower() -eq 'enum'){
        $enumVals=@()

        # Case 1: inline enum: [a, b, c]
        if($val -match '^\[(.*)\]$'){
          $inner=$Matches[1]
          $parts=$inner -split ','
          foreach($p in $parts){
            $nv=Normalize-EnumItem $p
            if($nv){ $enumVals += $nv }
          }
        }

        # Case 2: block enum list
        $j=$i+1
        while($j -lt $lines.Count){
          $ln=($lines[$j] -replace '\r','')
          if([string]::IsNullOrWhiteSpace($ln)){
            $j++
            continue
          }

          $lm=[regex]::Match($ln,'^(?<ind>\s*)-\s*(?<v>.+?)\s*$')
          if($lm.Success){
            $li=[int]$lm.Groups['ind'].Value.Length
            if($li -le $indent){ break }
            $nv=Normalize-EnumItem $lm.Groups['v'].Value
            if($nv){ $enumVals += $nv }
            $j++
            continue
          }

          $nextKey=[regex]::Match($ln,'^(?<ni>\s*)(?<nk>[A-Za-z_][A-Za-z0-9_\-\./]*)\s*:')
          if($nextKey.Success -and [int]$nextKey.Groups['ni'].Value.Length -le $indent){
            break
          }

          $j++
        }

        $enumVals=$enumVals|Sort-Object -Unique
        if($enumVals.Count -gt 0){
          $pathParts=@()
          foreach($s in $stack){
            $pathParts += [string]$s.key
          }

          $fieldPath=Compress-Path $pathParts
          if(-not $fieldPath){ $fieldPath='(root)' }

          $out += [PSCustomObject]@{
            title=$title
            url=$u
            field_path=$fieldPath
            enum_values=($enumVals -join '; ')
            value_count=$enumVals.Count
          }
        }
      } else {
        $obj=[PSCustomObject]@{ indent=$indent; key=$key }
        $stack.Add($obj) | Out-Null
      }
    }
  }
}

$out=$out|Sort-Object title,field_path -Unique

$csv='C:\storyboard\AIStory\_kie_all_enum_values_catalog.csv'
$md='C:\storyboard\AIStory\_kie_all_enum_values_catalog.md'
$out|Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8

$lines=@()
$lines+='# KIE All Enum Values Catalog'
$lines+="Generated at: $(Get-Date -Format s)"
$lines+="Rows: $($out.Count)"
$lines+=''
$byField=$out|Group-Object field_path|Sort-Object Count -Descending
$lines+="Unique field paths: $($byField.Count)"
$lines+='Top field paths by page count:'
foreach($g in ($byField|Select-Object -First 25)){
  $lines += "- $($g.Name): $($g.Count)"
}
$lines+=''
$lines+='| field_path | model page | value_count | enum_values |'
$lines+='|---|---|---|---|'
foreach($r in $out){
  $vals=@($r.field_path,$r.title,$r.value_count,$r.enum_values)
  $vals=$vals|ForEach-Object{([string]$_).Replace('|','/').Trim()}
  $lines += "| $($vals[0]) | $($vals[1]) | $($vals[2]) | $($vals[3]) |"
}

Set-Content -Path $md -Value $lines -Encoding UTF8

Write-Output "Generated: $csv"
Write-Output "Generated: $md"
Write-Output "Rows: $($out.Count)"
Write-Output "Unique field paths: $($byField.Count)"
if($byField.Count -gt 0){
  Write-Output 'Top field paths:'
  $byField|Select-Object -First 15|ForEach-Object{ Write-Output ("- {0}: {1}" -f $_.Name,$_.Count) }
}
