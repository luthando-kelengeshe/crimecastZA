$path = 'c:\Users\USER-PC\TUT\ISJ\Project\crimecastZA\232199660_ISJ107V Project Proposal 2026.docx'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Open($path)
$text = $doc.Content.Text
$doc.Close($false)
$word.Quit()
$text | Out-File -FilePath 'c:\Users\USER-PC\TUT\ISJ\Project\crimecastZA\proposal_text.txt' -Encoding UTF8
Write-Host 'Done'
