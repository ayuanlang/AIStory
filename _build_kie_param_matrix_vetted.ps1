param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('video','image','audio','chat')]
  [string]$Category
)

$ErrorActionPreference='Stop'
$src='C:\storyboard\AIStory\_kie_market_model_params_snapshot.json'
if(!(Test-Path $src)){ throw 'snapshot file not found' }
$data=(Get-Content $src -Raw | ConvertFrom-Json).model_pages

$allowedParamNames = @(
  'model','prompt','negative_prompt','duration','resolution','aspect_ratio','image_size','size','image_url','image_urls','last_frame_url','first_frame_url',
  'mode','quality','seed','seeds','fps','sound','multi_shots','multi_prompt','watermark','enableTranslation','callbackUrl','callBackUrl',
  'webHook','generationType','outputFormat','promptUpsampling','safetyTolerance','response_format','format','n_frames','audio_url','voice','style'
)

function Is-CategoryMatch([string]$category, [string]$url, [string]$title){
  $u = [string]$url
  $t = [string]$title

  switch($category){
    'video' {
      return ($u -match '/market/(kling|bytedance|hailuo|sora2|wan|infinitalk|topaz|grok-imagine)/') -or
             ($u -match '/runway-api/(generate-ai-video|extend-ai-video|generate-aleph-video)') -or
             ($t -match 'Video|视频|Kling|Sora|Hailuo|Bytedance|Wan|Runway|Infinitalk|Topaz|Grok Imagine')
    }
    'image' {
      return ($u -match '/(4o-image-api|flux-kontext-api)/') -or
             ($u -match '/market/(gpt-image|flux|recraft|seedream|ideogram|midjourney|stable-diffusion|imagen|bytedance.*image|grok.*image|qwen-image)/') -or
             ($t -match 'Image|图片|Flux|Recraft|Ideogram|Midjourney|GPT Image|Stable Diffusion|Imagen|Qwen')
    }
    'audio' {
      return ($u -match '/market/(music|audio|voice|text-to-speech|tts|suno|udio|minimax.*speech|fish-audio)/') -or
             ($t -match 'Music|Audio|Voice|语音|音乐|TTS|Suno|Udio|Speech')
    }
    'chat' {
      return ($u -match '/market/(gpt|claude|qwen|deepseek|gemini|llama|chat|reasoning)/') -or
             ($t -match 'Chat|对话|Reasoning|GPT|Claude|Qwen|DeepSeek|Gemini|Llama')
    }
  }

  return $false
}

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
    '\b(\d{1,2}:\d{1,2}|portrait|landscape|auto|square)\b',
    '\b(std|pro|fast|turbo|standard|master|quality|multi_shots|true|false|mp3|wav|flac|aac|json|b64_json|url)\b',
    '"([^"]+)"'
  )
  foreach($r in $regexes){
    [regex]::Matches($joined,$r,'IgnoreCase') | ForEach-Object {
      $v = if($_.Groups.Count -gt 1){ $_.Groups[1].Value } else { $_.Value }
      if($v){ $opts += $v.Trim() }
    }
  }
  $opts = $opts | Where-Object { $_ -and $_.Length -le 50 } | Sort-Object -Unique
  return ($opts -join ', ')
}

$pages=@()
foreach($m in $data){
  if(Is-CategoryMatch $Category ([string]$m.url) ([string]$m.title)){
    $pages += $m
  }
}
$pages = $pages | Sort-Object url -Unique

$rows=@()
foreach($m in $pages){
  $url=[string]$m.url
  $title=[string]$m.title
  try { $content = (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 45).Content } catch { continue }

  $pairs = Extract-ParamPairs $content

  $modelVal = if($pairs.ContainsKey('model')){ Normalize-Options $pairs['model'] } else { '' }
  $resolutionVal = if($pairs.ContainsKey('resolution')){ Normalize-Options $pairs['resolution'] } else { '' }
  $sizeVal = if($pairs.ContainsKey('image_size')){ Normalize-Options $pairs['image_size'] } elseif($pairs.ContainsKey('size')){ Normalize-Options $pairs['size'] } else { '' }
  $aspectRatioVal = if($pairs.ContainsKey('aspect_ratio')){ Normalize-Options $pairs['aspect_ratio'] } else { '' }
  $durationVal = if($pairs.ContainsKey('duration')){ Normalize-Options $pairs['duration'] } else { '' }
  $modeVal = if($pairs.ContainsKey('mode')){ Normalize-Options $pairs['mode'] } else { '' }
  $qualityVal = if($pairs.ContainsKey('quality')){ Normalize-Options $pairs['quality'] } else { '' }
  $formatVal = if($pairs.ContainsKey('outputFormat')){ Normalize-Options $pairs['outputFormat'] } elseif($pairs.ContainsKey('response_format')){ Normalize-Options $pairs['response_format'] } elseif($pairs.ContainsKey('format')){ Normalize-Options $pairs['format'] } else { '' }
  $soundVal = if($pairs.ContainsKey('sound')){ Normalize-Options $pairs['sound'] } else { '' }
  $multiShotsVal = if($pairs.ContainsKey('multi_shots')){ Normalize-Options $pairs['multi_shots'] } else { '' }
  $imageRefsVal = if($pairs.ContainsKey('image_url') -or $pairs.ContainsKey('image_urls')){ 'yes' } else { '' }

  $rows += [PSCustomObject]@{
    category = $Category
    title = $title
    url = $url
    model = $modelVal
    resolution = $resolutionVal
    image_size = $sizeVal
    aspect_ratio = $aspectRatioVal
    duration = $durationVal
    mode = $modeVal
    quality = $qualityVal
    output_format = $formatVal
    sound = $soundVal
    multi_shots = $multiShotsVal
    image_refs = $imageRefsVal
  }
}

$rows = $rows | Sort-Object title
$outMd="C:\storyboard\AIStory\_kie_${Category}_models_param_matrix_vetted.md"
$outCsv="C:\storyboard\AIStory\_kie_${Category}_models_param_matrix_vetted.csv"

$lines=@()
$lines+="# KIE $($Category.Substring(0,1).ToUpper()+$Category.Substring(1)) Models Param Matrix (Vetted Pass)"
$lines+="Generated at: $(Get-Date -Format s)"
$lines+="Total docs parsed: $($rows.Count)"
$lines+=''
$lines+='| Category | Model Page | URL | model | resolution | image_size/size | aspect_ratio | duration | mode | quality | output_format | sound | multi_shots | image refs |'
$lines+='|---|---|---|---|---|---|---|---|---|---|---|---|---|---|'
foreach($r in $rows){
  $vals=@($r.category,$r.title,$r.url,$r.model,$r.resolution,$r.image_size,$r.aspect_ratio,$r.duration,$r.mode,$r.quality,$r.output_format,$r.sound,$r.multi_shots,$r.image_refs)
  $vals = $vals | ForEach-Object { ([string]$_).Replace('|','/').Replace("`n",' ').Trim() }
  $lines += "| $($vals[0]) | $($vals[1]) | $($vals[2]) | $($vals[3]) | $($vals[4]) | $($vals[5]) | $($vals[6]) | $($vals[7]) | $($vals[8]) | $($vals[9]) | $($vals[10]) | $($vals[11]) | $($vals[12]) | $($vals[13]) |"
}

Set-Content -Path $outMd -Value $lines -Encoding UTF8
$rows | Export-Csv -Path $outCsv -NoTypeInformation -Encoding UTF8

Write-Output "Generated: $outMd"
Write-Output "Generated: $outCsv"
Write-Output "Rows: $($rows.Count)"