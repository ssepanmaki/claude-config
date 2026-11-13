<#
.SYNOPSIS
Shrinks a screenshot for model reading: optional crop, scale to fit MaxWidth x MaxHeight (cuts the bottom
instead of squashing a tall page), saves as JPEG. Prints the output path and the image's estimated token cost.
.EXAMPLE
shot-shrink.ps1 page.png                          # -> page.small.jpg, max 800x800
shot-shrink.ps1 page.png -Crop 0,800,1440,900     # a region further down a full-page shot
#>
param(
  [Parameter(Mandatory)][string]$In,
  [string]$Out,
  [int]$MaxWidth = 800,
  [int]$MaxHeight = 800,
  [int[]]$Crop,
  [int]$Quality = 70
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
if (-not $Out) { $Out = [IO.Path]::ChangeExtension($In, '.small.jpg') }

$src = [Drawing.Image]::FromFile((Resolve-Path $In))
try {
  $rect = if ($Crop) { [Drawing.Rectangle]::new($Crop[0], $Crop[1], $Crop[2], $Crop[3]) } else { [Drawing.Rectangle]::new(0, 0, $src.Width, $src.Height) }
  $scale = [Math]::Min(1.0, $MaxWidth / $rect.Width)
  $rect.Height = [Math]::Min($rect.Height, [int]($MaxHeight / $scale))
  $w = [int]($rect.Width * $scale); $h = [int]($rect.Height * $scale)

  $dst = [Drawing.Bitmap]::new($w, $h)
  $g = [Drawing.Graphics]::FromImage($dst)
  $g.InterpolationMode = 'HighQualityBicubic'
  $g.DrawImage($src, [Drawing.Rectangle]::new(0, 0, $w, $h), $rect, 'Pixel')
  $g.Dispose()

  $codec = [Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object MimeType -eq 'image/jpeg'
  $params = [Drawing.Imaging.EncoderParameters]::new(1)
  $params.Param[0] = [Drawing.Imaging.EncoderParameter]::new([Drawing.Imaging.Encoder]::Quality, [long]$Quality)
  $dst.Save($Out, $codec, $params)
  $dst.Dispose()
  $cut = if ($rect.Y + $rect.Height -lt $src.Height) { " (cut at y=$($rect.Y + $rect.Height) of $($src.Height))" } else { '' }
  "$Out ${w}x${h} ~$([int]($w * $h / 750)) tokens$cut"
} finally { $src.Dispose() }
