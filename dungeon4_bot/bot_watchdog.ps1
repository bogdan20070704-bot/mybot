param(
    [int]$CheckIntervalSeconds = 5
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$WatchdogLog = Join-Path $ProjectRoot "bot_watchdog.log"
$StdoutLog = Join-Path $ProjectRoot "bot_stdout.log"
$StderrLog = Join-Path $ProjectRoot "bot_stderr.log"

function Write-WatchdogLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $WatchdogLog -Value "[$timestamp] $Message"
}

function Get-BotProcess {
    $pattern = '(?i)(-m\s+bot\.main|bot[\\/]+main\.py)'
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            ($_.Name -ieq "python.exe" -or $_.Name -ieq "py.exe") -and
            $_.CommandLine -and
            $_.CommandLine -match $pattern
        }
}

# Prevent parallel watchdog instances from racing and creating duplicate bot processes.
$mutexName = "Global\dungeon_bot_watchdog_lock"
$mutex = New-Object System.Threading.Mutex($false, $mutexName)
if (-not $mutex.WaitOne(0, $false)) {
    Write-Output "Watchdog is already running."
    exit 0
}

try {
    $python = Get-Command python -ErrorAction SilentlyContinue
    $py = Get-Command py -ErrorAction SilentlyContinue

    if ($python) {
        $launcherPath = $python.Source
        $launcherArgs = @("-m", "bot.main")
    }
    elseif ($py) {
        $launcherPath = $py.Source
        $launcherArgs = @("-3", "-m", "bot.main")
    }
    else {
        Write-WatchdogLog "Python launcher not found in PATH."
        throw "Python launcher not found in PATH."
    }

    Write-WatchdogLog "Watchdog started. Check interval: ${CheckIntervalSeconds}s."

    while ($true) {
        try {
            $botProcess = Get-BotProcess | Select-Object -First 1
            if ($null -eq $botProcess) {
                $started = Start-Process `
                    -FilePath $launcherPath `
                    -ArgumentList $launcherArgs `
                    -WorkingDirectory $ProjectRoot `
                    -RedirectStandardOutput $StdoutLog `
                    -RedirectStandardError $StderrLog `
                    -PassThru

                Write-WatchdogLog "Bot started. PID=$($started.Id)."
                Start-Sleep -Seconds 2
                if ($started.HasExited) {
                    Write-WatchdogLog "Bot exited quickly. Exit code: $($started.ExitCode)."
                }
            }
        }
        catch {
            Write-WatchdogLog "Watchdog loop error: $($_.Exception.Message)"
        }

        Start-Sleep -Seconds $CheckIntervalSeconds
    }
}
finally {
    if ($mutex) {
        $mutex.ReleaseMutex() | Out-Null
        $mutex.Dispose()
    }
}
