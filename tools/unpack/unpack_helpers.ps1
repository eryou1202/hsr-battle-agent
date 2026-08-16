function Export-BinaryWindow {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [long]$Offset,

        [int]$Before = 128,

        [int]$After = 1024,

        [Parameter(Mandatory)]
        [string]$OutputPath
    )

    if (-not (Test-Path $Path -PathType Leaf)) {
        throw "输入文件不存在：$Path"
    }

    $FileInfo = Get-Item $Path
    $Start = [Math]::Max([long]0, $Offset - $Before)
    $End = [Math]::Min($FileInfo.Length, $Offset + $After)
    $Length = [int]($End - $Start)

    if ($Length -le 0) {
        throw "导出窗口长度无效：$Length"
    }

    $OutputDirectory = Split-Path $OutputPath -Parent

    if ($OutputDirectory) {
        New-Item `
            -ItemType Directory `
            -Force `
            -Path $OutputDirectory |
            Out-Null
    }

    $Buffer = New-Object byte[] $Length
    $Stream = $null

    try {
        $Stream = [System.IO.File]::OpenRead($Path)

        [void]$Stream.Seek(
            $Start,
            [System.IO.SeekOrigin]::Begin
        )

        $TotalRead = 0

        while ($TotalRead -lt $Length) {
            $Read = $Stream.Read(
                $Buffer,
                $TotalRead,
                $Length - $TotalRead
            )

            if ($Read -eq 0) {
                break
            }

            $TotalRead += $Read
        }

        if ($TotalRead -ne $Length) {
            throw "读取长度异常：期望 $Length 字节，实际 $TotalRead 字节"
        }

        [System.IO.File]::WriteAllBytes(
            $OutputPath,
            $Buffer
        )

        [PSCustomObject]@{
            SourcePath          = $Path
            MatchOffset        = $Offset
            MatchOffsetHex     = "0x{0:X}" -f $Offset
            WindowStart        = $Start
            WindowStartHex     = "0x{0:X}" -f $Start
            WindowEnd          = $End
            WindowEndHex       = "0x{0:X}" -f $End
            WindowLength       = $Length
            MatchOffsetInWindow = $Offset - $Start
            OutputPath         = $OutputPath
        }
    }
    finally {
        if ($null -ne $Stream) {
            $Stream.Dispose()
        }
    }
}
function Get-AsciiStrings {
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [int]$MinLength = 3
    )

    if (-not (Test-Path $Path -PathType Leaf)) {
        throw "文件不存在：$Path"
    }

    $Bytes = [System.IO.File]::ReadAllBytes($Path)
    $Text = [System.Text.Encoding]::ASCII.GetString($Bytes)

    [regex]::Matches(
        $Text,
        "[\x20-\x7E]{$MinLength,}"
    ) |
        ForEach-Object {
            $_.Value
        }
}