$ErrorActionPreference='Stop'
$src='C:\storyboard\AIStory\_kie_market_model_params_snapshot.json'
if(!(Test-Path $src)){ throw 'snapshot file not found' }
$data=(Get-Content $src -Raw | ConvertFrom-Json).model_pages

$videoPages=@()
foreach($m in $data){
  $u=[string]$m.url; $t=[string]$m.title
  $isVideo = ($u -match '/market/(kling|bytedance|hailuo|sora2|wan|infinitalk|grok-imagine|topaz)/') -or ($u -match '/runway-api/(generate-ai-video|extend-ai-video|generate-aleph-video)') -or ($t -match 'Video|视频|Kling|Sora|Hailuo|Bytedance|Wan|Runway|Infinitalk|Grok Imagine')
  if($isVideo){ $videoPages += $m }
}
$videoPages = $videoPages | Sort-Object url -Unique

$allowedParamNames = @(
  'model','prompt','negative_prompt','duration','resolution','aspect_ratio','image_url','image_urls','last_frame_url','first_frame_url','mode','quality','seed','seeds','fps','sound','multi_shots','multi_prompt','watermark','enableTranslation','callbackUrl','callBackUrl','webHook','generationType','outputFormat','promptUpsampling','safetyTolerance'
)

function Extract-ParamPairs([string]$content){
  $pairs = @{}
  if([string]::IsNullOrWhiteSpace($content)){ return $pairs }
  $lines = $content -split "`n"

  foreach($lineRaw in $lines){
    $line = ($lineRaw -replace '\r','').Trim()
    if(-not $line){ continue }

    if($line -match '^\|.+\|$' -and $line -notmatch '^\|[-: ]+\|$'){
      $cells = $line.Trim('|').Split('|') | ForEach-Object { $_.Trim() }
      if($cells.Count -ge 2){
        $name = $cells[0]
        if($allowedParamNames -contains $name){
          $desc = ($cells[1..($cells.Count-1)] -join ' | ')
          if(-not $pairs.ContainsKey($name)){ $pairs[$name] = @() }
          $pairs[$name] += $desc
        }
      }
    }

    if($line -match '"(?<k>[a-zA-Z_][a-zA-Z0-9_]*)"\s*:\s*(?<v>.+)$'){
      $k = $Matches['k']; $v = $Matches['v']
      if($allowedParamNames -contains $k){
        if(-not $pairs.ContainsKey($k)){ $pairs[$k] = @() }
        $pairs[$k] += $v
      }
    }

    if($line -match '^(?:-|\*|\d+\.)?\s*(?<k>[a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(?<v>.+)$'){
      $k = $Matches['k']; $v = $Matches['v']
      if($allowedParamNames -contains $k){
        if(-not $pairs.ContainsKey($k)){ $pairs[$k] = @() }
        $pairs[$k] += $v
      }
    }
  }

  return $pairs
}

function Normalize-Options([string[]]$vals){
  $joined = ($vals -join ' | ')
  $opts=@()
  $regexes=@(
    '\b(\d{3,4}P|\d{3,4}x\d{3,4}|720p|1080p|1K|2K|4K)\b',
    '\b(\d{1,2}:\d{1,2}|portrait|landscape|auto)\b',
    '\b(std|pro|fast|turbo|standard|master|quality|multi_shots|true|false)\b',
    '"([^"]+)"'
  )
  foreach($r in $regexes){
    [regex]::Matches($joined,$r,'IgnoreCase') | ForEach-Object {
      $v = if($_.Groups.Count -gt 1){ $_.Groups[1].Value } else { $_.Value }
      if($v){ $opts += $v.Trim() }
    }
  }
  $opts = $opts | Where-Object { $_ -and $_.Length -le 40 } | Sort-Object -Unique
  return ($opts -join ', ')
}

$rows=@()
foreach($m in $videoPages){
  $url=[string]$m.url
  $title=[string]$m.title
  try { $content = (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 45).Content } catch { continue }
  $pairs = Extract-ParamPairs $content

  $modelVal = if($pairs.ContainsKey('model')){ Normalize-Options $pairs['model'] } else { '' }
  $resolutionVal = if($pairs.ContainsKey('resolution')){ Normalize-Options $pairs['resolution'] } else { '' }
  $aspectRatioVal = if($pairs.ContainsKey('aspect_ratio')){ Normalize-Options $pairs['aspect_ratio'] } else { '' }
  $durationVal = if($pairs.ContainsKey('duration')){ Normalize-Options $pairs['duration'] } else { '' }
  $modeVal = if($pairs.ContainsKey('mode')){ Normalize-Options $pairs['mode'] } else { '' }
  $qualityVal = if($pairs.ContainsKey('quality')){ Normalize-Options $pairs['quality'] } else { '' }
  $soundVal = if($pairs.ContainsKey('sound')){ Normalize-Options $pairs['sound'] } else { '' }
  $multiShotsVal = if($pairs.ContainsKey('multi_shots')){ Normalize-Options $pairs['multi_shots'] } else { '' }
  $imageRefsVal = if($pairs.ContainsKey('image_url') -or $pairs.ContainsKey('image_urls')){ 'yes' } else { '' }

  $rows += [PSCustomObject]@{
    title = $title
    url = $url
    model = $modelVal
    resolution = $resolutionVal
    aspect_ratio = $aspectRatioVal
    duration = $durationVal
    mode = $modeVal
    quality = $qualityVal
    sound = $soundVal
    multi_shots = $multiShotsVal
    image_refs = $imageRefsVal
  }
}

$rows = $rows | Sort-Object title
$outMd='C:\storyboard\AIStory\_kie_video_models_param_matrix_vetted.md'
$outCsv='C:\storyboard\AIStory\_kie_video_models_param_matrix_vetted.csv'

$lines=@()
$lines+='# KIE Video Models Param Matrix (Vetted Pass)'
$lines+="Generated at: $(Get-Date -Format s)"
$lines+="Total video docs parsed: $($rows.Count)"
$lines+=''
$lines+='| Model Page | URL | model | resolution options | aspect_ratio options | duration options | mode options | quality options | sound | multi_shots | image refs |'
$lines+='|---|---|---|---|---|---|---|---|---|---|---|'
foreach($r in $rows){
  $vals=@($r.title,$r.url,$r.model,$r.resolution,$r.aspect_ratio,$r.duration,$r.mode,$r.quality,$r.sound,$r.multi_shots,$r.image_refs)
  $vals = $vals | ForEach-Object { ([string]$_).Replace('|','/').Replace("`n",' ').Trim() }
  $lines += "| $($vals[0]) | $($vals[1]) | $($vals[2]) | $($vals[3]) | $($vals[4]) | $($vals[5]) | $($vals[6]) | $($vals[7]) | $($vals[8]) | $($vals[9]) | $($vals[10]) |"
}

Set-Content -Path $outMd -Value $lines -Encoding UTF8
$rows | Export-Csv -Path $outCsv -NoTypeInformation -Encoding UTF8

Write-Output "Generated: $outMd"
Write-Output "Generated: $outCsv"
Write-Output "Rows: $($rows.Count)"
