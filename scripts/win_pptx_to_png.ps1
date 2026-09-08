param(
  [Parameter(Mandatory=$true)][string]$Deck,
  [Parameter(Mandatory=$true)][string]$OutDir,
  [int]$Width = 1920
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = 1
try {
  $pres = $ppt.Presentations.Open($Deck, 1, 0, 0)
  $w = [double]$pres.PageSetup.SlideWidth
  $h = [double]$pres.PageSetup.SlideHeight
  $targetW = $Width
  $targetH = [int][Math]::Round($targetW * ($h / $w))
  $i = 1
  foreach($slide in $pres.Slides){
    $out = Join-Path $OutDir ('slide-{0:D2}.png' -f $i)
    $slide.Export($out, 'PNG', $targetW, $targetH)
    $i++
  }
  Write-Output "SLIDES=$($i-1)"
  $pres.Close()
} finally {
  $ppt.Quit()
  [System.Runtime.Interopservices.Marshal]::ReleaseComObject($ppt) | Out-Null
}
