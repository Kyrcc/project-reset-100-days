param(
    [switch] $SelfTest,
    [string] $TestImage,
    [switch] $Diagnose
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Runtime.WindowsRuntime

Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class NativeMethods
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int X, Y; }

    [DllImport("user32.dll")]
    public static extern short GetAsyncKeyState(int virtualKeyCode);

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr window, out RECT rect);

    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);

    [DllImport("user32.dll")]
    public static extern bool GetCursorPos(out POINT point);

    [DllImport("user32.dll")]
    public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);

    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();
}
'@

$null = [NativeMethods]::SetProcessDPIAware()

# Load Windows' built-in OCR types.
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime]

function Wait-WinRtOperation {
    param(
        [Parameter(Mandatory)] $Operation,
        [Parameter(Mandatory)] [Type] $ResultType
    )

    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and
            $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1
        } |
        Select-Object -First 1

    $task = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

function Get-TextFromImage {
    param(
        [Parameter(Mandatory)] [string] $ImagePath,
        [Parameter(Mandatory)] $OcrEngine
    )

    $file = Wait-WinRtOperation `
        ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) `
        ([Windows.Storage.StorageFile])
    $stream = Wait-WinRtOperation `
        ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) `
        ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Wait-WinRtOperation `
        ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) `
        ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Wait-WinRtOperation `
        ($decoder.GetSoftwareBitmapAsync()) `
        ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Wait-WinRtOperation `
        ($OcrEngine.RecognizeAsync($bitmap)) `
        ([Windows.Media.Ocr.OcrResult])

    $text = $result.Text
    $bitmap.Dispose()
    $stream.Dispose()
    return $text
}

function Get-CustomerName {
    param([Parameter(Mandatory)] [string] $OcrText)

    # OCR often inserts spaces and may omit underscores. The numeric customer ID
    # is therefore used as the stable boundary after the name.
    $compact = $OcrText -replace '\s+', ''
    $match = [regex]::Match($compact, '([\p{IsCJKUnifiedIdeographs}]{2,6})(?=\d{4,})')
    if ($match.Success) {
        return $match.Groups[1].Value
    }

    # Fallback for a title that contains no numeric ID.
    $fallback = [regex]::Match($compact, '[\p{IsCJKUnifiedIdeographs}]{2,6}')
    if ($fallback.Success) {
        return $fallback.Value
    }

    throw "未能从窗口左上角识别客户姓名。识别结果：$OcrText"
}

function Get-Salutation {
    param([Parameter(Mandatory)] [string] $CustomerName)

    $compoundSurnames = @(
        '欧阳', '司马', '上官', '诸葛', '东方', '皇甫', '尉迟', '公孙',
        '慕容', '司徒', '司空', '夏侯', '令狐', '宇文', '长孙', '端木',
        '南宫', '独孤'
    )

    foreach ($surname in $compoundSurnames) {
        if ($CustomerName.StartsWith($surname)) {
            return $surname
        }
    }

    $characters = [System.Globalization.StringInfo]::ParseCombiningCharacters($CustomerName)
    $length = $characters.Count

    if ($length -eq 2) {
        return $CustomerName.Substring($characters[0], $characters[1] - $characters[0]) + '哥'
    }

    if ($length -ge 3) {
        $start = $characters[$length - 2]
        return $CustomerName.Substring($start)
    }

    return $CustomerName
}

function Set-ClipboardTextWithRetry {
    param([Parameter(Mandatory)] [string] $Text)

    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            [System.Windows.Forms.Clipboard]::SetText($Text)
            return
        }
        catch {
            Start-Sleep -Milliseconds 100
        }
    }
    throw '剪贴板正被其他程序占用，请稍后再试。'
}

function Invoke-NameHelper {
    param(
        [Parameter(Mandatory)] $OcrEngine,
        [Parameter(Mandatory)] [string] $ScriptDirectory,
        [switch] $Diagnose
    )

    $window = [NativeMethods]::GetForegroundWindow()
    $rect = New-Object NativeMethods+RECT
    if ($window -eq [IntPtr]::Zero -or -not [NativeMethods]::GetWindowRect($window, [ref] $rect)) {
        throw '没有找到当前聊天窗口。'
    }

    $windowWidth = $rect.Right - $rect.Left
    $windowHeight = $rect.Bottom - $rect.Top
    if ($windowWidth -lt 450 -or $windowHeight -lt 350) {
        throw '当前窗口太小，请先打开或放大客户聊天窗口。'
    }

    # The app has two layouts:
    # 1. A compact standalone chat window, where the title is near the left.
    # 2. A wide main window, where navigation and the conversation list occupy
    #    roughly the first 23% of the window.
    # Coordinates remain relative to the active window, so moving the window
    # does not affect recognition.
    if ($windowWidth -ge 1800) {
        $captureX = $rect.Left + [int]($windowWidth * 0.2285)
        $captureY = $rect.Top + [int]($windowHeight * 0.0065)
        $captureWidth = [Math]::Min(780, $windowWidth - ($captureX - $rect.Left) - 30)
        $captureHeight = [Math]::Min(115, $windowHeight - ($captureY - $rect.Top) - 30)
    }
    else {
        $captureX = $rect.Left + 18
        $captureY = $rect.Top + 22
        $captureWidth = [Math]::Min(700, $windowWidth - 36)
        $captureHeight = [Math]::Min(95, $windowHeight - 44)
    }

    $imagePath = Join-Path $env:TEMP 'wecom-name-helper-title.png'
    $image = New-Object System.Drawing.Bitmap $captureWidth, $captureHeight
    $graphics = [System.Drawing.Graphics]::FromImage($image)
    try {
        $graphics.CopyFromScreen(
            $captureX,
            $captureY,
            0,
            0,
            $image.Size,
            [System.Drawing.CopyPixelOperation]::SourceCopy
        )
        $image.Save($imagePath, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $graphics.Dispose()
        $image.Dispose()
    }

    $ocrText = Get-TextFromImage -ImagePath $imagePath -OcrEngine $OcrEngine
    $customerName = Get-CustomerName -OcrText $ocrText
    $salutation = Get-Salutation -CustomerName $customerName

    if ($Diagnose) {
        [System.Windows.Forms.MessageBox]::Show(
            "识别文字：$ocrText`r`n客户姓名：$customerName`r`n生成称呼：$salutation`r`n`r`n诊断模式没有点击输入框、复制内容或填入话术。",
            '称呼识别诊断结果',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        ) | Out-Null
        return
    }

    $messagePath = Join-Path $ScriptDirectory '今日话术.txt'
    if (-not (Test-Path -LiteralPath $messagePath)) {
        throw '找不到“今日话术.txt”。'
    }
    $message = (Get-Content -LiteralPath $messagePath -Raw -Encoding UTF8).Trim()
    if ([string]::IsNullOrWhiteSpace($message)) {
        throw '“今日话术.txt”是空的，请先填写话术。'
    }

    $fullText = $salutation + $message
    Set-ClipboardTextWithRetry -Text $fullText

    # Click near the bottom of the active chat window, inside the message input
    # area, then paste. Enter is deliberately not pressed.
    $inputX = $rect.Left + [Math]::Max(220, [int]($windowWidth * 0.48))
    $inputY = $rect.Bottom - 34
    $originalCursor = New-Object NativeMethods+POINT
    $hasOriginalCursor = [NativeMethods]::GetCursorPos([ref] $originalCursor)
    try {
        [NativeMethods]::SetCursorPos($inputX, $inputY) | Out-Null
        [NativeMethods]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
        [NativeMethods]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 120
        [System.Windows.Forms.SendKeys]::SendWait('^v')
    }
    finally {
        if ($hasOriginalCursor) {
            [NativeMethods]::SetCursorPos($originalCursor.X, $originalCursor.Y) | Out-Null
        }
    }
    [Console]::Beep(900, 80)
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$language = New-Object Windows.Globalization.Language 'zh-Hans'
$ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if ($null -eq $ocrEngine) {
    [System.Windows.Forms.MessageBox]::Show(
        'Windows 中文文字识别不可用，请先安装“中文（简体）”语言包。',
        '企业微信称呼助手'
    ) | Out-Null
    exit 1
}

if ($SelfTest) {
    if ([string]::IsNullOrWhiteSpace($TestImage) -or -not (Test-Path -LiteralPath $TestImage)) {
        throw '自测模式需要一个有效的 -TestImage 图片路径。'
    }
    $testText = Get-TextFromImage -ImagePath (Resolve-Path -LiteralPath $TestImage).Path -OcrEngine $ocrEngine
    $testName = Get-CustomerName -OcrText $testText
    $testSalutation = Get-Salutation -CustomerName $testName
    [PSCustomObject]@{
        Name = $testName
        Salutation = $testSalutation
        TwoCharacterExample = Get-Salutation -CustomerName '张三'
        CompoundSurnameExample = Get-Salutation -CustomerName '欧阳成'
    } | Format-List
    exit 0
}

$notification = New-Object System.Windows.Forms.NotifyIcon
$notification.Icon = [System.Drawing.SystemIcons]::Information
if ($Diagnose) {
    $notification.Text = '企业微信称呼助手诊断模式：按 F8 只检查识别结果'
}
else {
    $notification.Text = '企业微信称呼助手：按 F8 填入个性化话术'
}
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$exitItem = New-Object System.Windows.Forms.ToolStripMenuItem
$exitItem.Text = '退出称呼助手'
$script:running = $true
$exitItem.Add_Click({ $script:running = $false })
$menu.Items.Add($exitItem) | Out-Null
$notification.ContextMenuStrip = $menu
$notification.Visible = $true
if ($Diagnose) {
    $notification.ShowBalloonTip(
        2500,
        '称呼识别诊断模式已启动',
        '打开测试客户聊天后按 F8；诊断模式不会点击、复制或填入任何内容。',
        [System.Windows.Forms.ToolTipIcon]::Info
    )
}
else {
    $notification.ShowBalloonTip(
        2500,
        '企业微信称呼助手已启动',
        '打开客户聊天后按 F8；工具只填入话术，不会自动发送。',
        [System.Windows.Forms.ToolTipIcon]::Info
    )
}

Write-Host ''
if ($Diagnose) {
    Write-Host '企业微信称呼助手诊断模式正在运行。' -ForegroundColor Cyan
    Write-Host '打开测试客户聊天后按 F8；只显示识别结果，不会操作聊天框。'
}
else {
    Write-Host '企业微信称呼助手正在运行。' -ForegroundColor Green
    Write-Host '打开客户聊天后按 F8；检查内容后手动发送。'
}
Write-Host '请保持此窗口开启，可以将它最小化。'
Write-Host '关闭此窗口，助手就会停止。'
Write-Host ''

try {
    $f8WasDown = $false
    while ($script:running) {
        [System.Windows.Forms.Application]::DoEvents()
        $f8IsDown = (([NativeMethods]::GetAsyncKeyState(0x77) -band 0x8000) -ne 0)
        if ($f8IsDown -and -not $f8WasDown) {
            try {
                Invoke-NameHelper `
                    -OcrEngine $ocrEngine `
                    -ScriptDirectory $scriptDirectory `
                    -Diagnose:$Diagnose
            }
            catch {
                [Console]::Beep(350, 180)
                $notification.ShowBalloonTip(
                    4000,
                    '未能填入话术',
                    $_.Exception.Message,
                    [System.Windows.Forms.ToolTipIcon]::Error
                )
            }
        }
        $f8WasDown = $f8IsDown
        Start-Sleep -Milliseconds 50
    }
}
finally {
    $notification.Visible = $false
    $notification.Dispose()
    $menu.Dispose()
}
