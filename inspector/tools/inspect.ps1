# inspect.ps1 <tool> [json-params] [-TimeoutMs 10000]
# Same-user pipe client for the FM27 Crimson Inspector (inspector-spec.md section 3). Prints the reply JSON.
param(
    [Parameter(Mandatory = $true)][string]$Tool,
    [string]$Params = '{}',
    [int]$TimeoutMs = 10000
)
$ErrorActionPreference = 'Stop'
$pipe = New-Object System.IO.Pipes.NamedPipeClientStream('.', 'fm27-crimson-inspector', [System.IO.Pipes.PipeDirection]::InOut)
try {
    $pipe.Connect([Math]::Min($TimeoutMs, 3000))
} catch {
    Write-Output ('{"v":1,"fault":{"kind":"offline","detail":"inspector pipe not available - is FM27 running with the plugin?"}}')
    exit 2
}
try {
    $id = Get-Random -Minimum 1 -Maximum 1000000
    $line = '{"id":' + $id + ',"tool":"' + $Tool + '","params":' + $Params + '}' + "`n"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($line)
    $pipe.Write($bytes, 0, $bytes.Length); $pipe.Flush()
    $ms = New-Object System.IO.MemoryStream
    $buf = New-Object byte[] 65536
    $task = $null
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.ElapsedMilliseconds -lt $TimeoutMs) {
        $task = $pipe.ReadAsync($buf, 0, $buf.Length)
        if (-not $task.Wait([Math]::Max(1, $TimeoutMs - $sw.ElapsedMilliseconds))) { break }
        $n = $task.Result
        if ($n -le 0) { break }
        $ms.Write($buf, 0, $n)
        if ([Array]::IndexOf($buf, [byte]10, 0, $n) -ge 0) { break }
    }
    $text = [System.Text.Encoding]::UTF8.GetString($ms.ToArray()).Trim()
    if (-not $text) { $text = '{"v":1,"fault":{"kind":"timeout","detail":"no reply within ' + $TimeoutMs + ' ms"}}' }
    Write-Output $text
} finally { $pipe.Dispose() }
