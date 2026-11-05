# Renders each narration entry to a WAV file with the offline Windows voice.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File tts.ps1 -OutDir out\audio [-Voice "Microsoft Zira Desktop"] [-Rate 0]
param(
  [string]$OutDir = "out\audio",
  [string]$Voice = "Microsoft David Desktop",
  [int]$Rate = 0
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$items = Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot "narration.json") | ConvertFrom-Json
foreach ($item in $items) {
  $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $synth.SelectVoice($Voice)
  $synth.Rate = $Rate
  $path = Join-Path (Resolve-Path $OutDir) ($item.id + ".wav")
  $synth.SetOutputToWaveFile($path)
  $synth.Speak($item.text)
  $synth.Dispose()
  Write-Output "wrote $path"
}
