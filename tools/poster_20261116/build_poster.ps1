# Builds poster_final.pptx / .pdf from the official A0 template copy and poster_spec.json (PowerPoint COM).
# The template file itself is never modified: a work copy is opened and saved under a new name.
param([string]$SpecPath = (Join-Path $PSScriptRoot 'poster_spec.json'))
$ErrorActionPreference = 'Stop'
$spec = Get-Content -Raw -Encoding UTF8 $SpecPath | ConvertFrom-Json
$work = Join-Path $PSScriptRoot 'poster_build.pptx'
Copy-Item (Join-Path $PSScriptRoot 'template_copy.pptx') $work -Force
$app = New-Object -ComObject PowerPoint.Application
try {
  $pres = $app.Presentations.Open($work, $false, $false, $false)
  for ($i = $pres.Slides.Count; $i -ge 1; $i--) { if ($i -ne $spec.template_slide) { $pres.Slides($i).Delete() } }
  $slide = $pres.Slides(1)
  # Remove the template's off-slide helper notes and example picture (outside the printable A0 area).
  $w = $pres.PageSetup.SlideWidth
  for ($i = $slide.Shapes.Count; $i -ge 1; $i--) {
    $sh = $slide.Shapes($i)
    if ($sh.Left -lt -100 -or $sh.Left -ge $w) { $sh.Delete() }
  }
  foreach ($m in $spec.moves) {
    $sh = $slide.Shapes($m.name)
    if ($null -ne $m.left) { $sh.Left = ([single]$m.left) }
    if ($null -ne $m.top) { $sh.Top = ([single]$m.top) }
    if ($null -ne $m.width) { $sh.Width = ([single]$m.width) }
    if ($null -ne $m.height) { $sh.Height = ([single]$m.height) }
  }
  foreach ($t in $spec.replace_text) {
    $sh = $null
    foreach ($c in $slide.Shapes) { if ($c.HasTextFrame -and $c.TextFrame.HasText -and $c.TextFrame.TextRange.Text.StartsWith($t.starts_with)) { $sh = $c } }
    if ($null -eq $sh) { throw "template text not found: $($t.starts_with)" }
    $sh.TextFrame.TextRange.Text = ($t.lines -join "`r")
    for ($p = 1; $p -le $t.lines.Count; $p++) { $sh.TextFrame.TextRange.Paragraphs($p).Font.Size = ([single]$t.sizes[$p - 1]) }
  }
  foreach ($it in $spec.items) {
    if ($it.type -eq 'text') {
      $sh = $slide.Shapes.AddTextbox(1, ([single]$it.left), ([single]$it.top), ([single]$it.width), ([single]$it.height))
      $sh.Name = $it.name
      $tf = $sh.TextFrame
      $tf.WordWrap = -1; $tf.AutoSize = 0
      $tf.MarginLeft = 0; $tf.MarginRight = 0; $tf.MarginTop = 0; $tf.MarginBottom = 0
      $tf.TextRange.Text = ($it.lines -join "`r")
      $tf.TextRange.Font.Name = $spec.font; $tf.TextRange.Font.NameFarEast = $spec.font
      $tf.TextRange.Font.Size = ([single]$it.size)
      $tf.TextRange.Font.Color.RGB = 0x2B2017
      $tf.TextRange.ParagraphFormat.SpaceAfter = ([single]$it.space_after)
      $tf.TextRange.ParagraphFormat.SpaceWithin = 1.08
      if ($it.bold_first) { $tf.TextRange.Paragraphs(1).Font.Bold = -1 }
      if ($it.color) { $tf.TextRange.Font.Color.RGB = [int]$it.color }
      $sh.Height = ([single]$it.height)
    } elseif ($it.type -eq 'picture') {
      $sh = $slide.Shapes.AddPicture((Join-Path $spec.figure_dir $it.file), 0, -1, ([single]$it.left), ([single]$it.top), ([single]$it.width), ([single]$it.height))
      $sh.Name = $it.name
      $sh.LockAspectRatio = -1
    } elseif ($it.type -eq 'table') {
      $rows = $it.cells.Count; $cols = $it.cells[0].Count
      $sh = $slide.Shapes.AddTable($rows, $cols, ([single]$it.left), ([single]$it.top), ([single]$it.width), ([single]$it.height))
      $sh.Name = $it.name
      for ($r = 1; $r -le $rows; $r++) {
        for ($c = 1; $c -le $cols; $c++) {
          $cell = $sh.Table.Cell($r, $c)
          $tr = $cell.Shape.TextFrame.TextRange
          $tr.Text = [string]$it.cells[$r - 1][$c - 1]
          $tr.Font.Name = $spec.font; $tr.Font.NameFarEast = $spec.font; $tr.Font.Size = ([single]$it.size)
          $cell.Shape.TextFrame.MarginLeft = 8; $cell.Shape.TextFrame.MarginRight = 8
          $cell.Shape.TextFrame.MarginTop = 4; $cell.Shape.TextFrame.MarginBottom = 4
          if ($r -eq 1) { $tr.Font.Bold = -1; $tr.Font.Color.RGB = 0xFFFFFF; $cell.Shape.Fill.ForeColor.RGB = 0x8F6035 }
          else { $tr.Font.Bold = 0; $tr.Font.Color.RGB = 0x2B2017; if ($r % 2 -eq 0) { $cell.Shape.Fill.ForeColor.RGB = 0xFFFFFF } else { $cell.Shape.Fill.ForeColor.RGB = 0xF4EFEA } }
        }
      }
      for ($c = 1; $c -le $cols; $c++) { $sh.Table.Columns($c).Width = [single](([double]$it.width) * ([double]$it.col_fractions[$c - 1])) }
    }
  }
  $out = $spec.output_dir
  $pres.SaveAs((Join-Path $out 'poster_final.pptx'), 24)   # ppSaveAsOpenXMLPresentation
  $pres.SaveAs((Join-Path $out 'poster_final.pdf'), 32)    # ppSaveAsPDF
  $slide.Export((Join-Path $PSScriptRoot 'poster_preview.png'), 'PNG', 2384, 3370)
  # Layout report: every shape with its box, for the overlap / out-of-page check.
  $report = foreach ($sh in $slide.Shapes) { [pscustomobject]@{ name = $sh.Name; left = [math]::Round($sh.Left, 1); top = [math]::Round($sh.Top, 1); width = [math]::Round($sh.Width, 1); height = [math]::Round($sh.Height, 1); type = $sh.Type } }
  $report | ConvertTo-Json | Out-File -Encoding utf8 (Join-Path $PSScriptRoot 'poster_layout.json')
  "slides=$($pres.Slides.Count) size=$($pres.PageSetup.SlideWidth)x$($pres.PageSetup.SlideHeight) shapes=$($slide.Shapes.Count)"
  $pres.Close()
} finally {
  $app.Quit()
}
Remove-Item $work -Force -ErrorAction SilentlyContinue
