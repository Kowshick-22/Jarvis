using System.Diagnostics;
using OpenJarvis.WinUI.Models;

namespace OpenJarvis.WinUI.Services;

public sealed class BackendSupervisor : IDisposable
{
    private readonly JarvisApiClient _api;
    private readonly FoundryClient _foundry;
    private readonly SettingsStore _settings;
    private readonly NativeJob _job = new();
    private Process? _jarvis;
    private CancellationTokenSource? _loop;
    private int _backoffMs = 1000;

    public BackendSupervisor(JarvisApiClient api, FoundryClient foundry, SettingsStore settings)
    {
        _api = api;
        _foundry = foundry;
        _settings = settings;
    }

    public BackendStatus Status { get; } = new();
    public event EventHandler? StatusChanged;

    public string LastError { get; private set; } = "";

    public void ReportUiError(string message)
    {
        LastError = message;
        Status.Failed = true;
        Status.Detail = message;
        StatusChanged?.Invoke(this, EventArgs.Empty);
    }

    public void Start()
    {
        _loop?.Cancel();
        _loop = new CancellationTokenSource();
        _ = Task.Run(() => SuperviseAsync(_loop.Token));
    }

    public async Task RestartWithAgentAsync(string agent, CancellationToken cancellationToken)
    {
        _settings.Current.SelectedAgent = agent;
        _settings.Save();
        StopJarvis();
        await StartJarvisAsync(cancellationToken);
    }

    public void Dispose()
    {
        _loop?.Cancel();
        StopJarvis();
        _job.Dispose();
    }

    private async Task SuperviseAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                _api.SetBaseUrl(_settings.Current.ApiUrl);
                SetStatus("Checking backend", "Looking for a local OpenJarvis server…", false, false);
                using var shortWait = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                shortWait.CancelAfter(TimeSpan.FromSeconds(2));
                if (await _api.IsHealthyAsync(shortWait.Token))
                {
                    SetStatus("Ready", "Attached to an existing OpenJarvis server.", true, false);
                    _backoffMs = 1000;
                    await WaitUntilUnhealthyAsync(cancellationToken);
                    continue;
                }

                SetStatus("Starting Foundry Local", "Starting the Windows ML inference service…", false, false);
                var host = await _foundry.EnsureServiceAsync(cancellationToken);
                TomlSettings.SetFoundryHost(host);

                SetStatus("Starting OpenJarvis", "Launching jarvis serve…", false, false);
                await StartJarvisAsync(cancellationToken);

                var deadline = DateTime.UtcNow.AddMinutes(10);
                while (DateTime.UtcNow < deadline && !cancellationToken.IsCancellationRequested)
                {
                    if (await _api.IsEngineHealthyAsync(cancellationToken))
                    {
                        SetStatus("Ready", "OpenJarvis is ready.", true, false);
                        _backoffMs = 1000;
                        await WaitUntilUnhealthyAsync(cancellationToken);
                        break;
                    }

                    if (_jarvis is { HasExited: true })
                    {
                        throw new InvalidOperationException(
                            $"jarvis serve exited with code {_jarvis.ExitCode}. Check {AppPaths.LogsDir}.");
                    }

                    SetStatus("Waiting", "Waiting for /health…", false, false);
                    await Task.Delay(1000, cancellationToken);
                }
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                return;
            }
            catch (Exception ex)
            {
                LastError = ex.Message;
                SetStatus("Error", Actionable(ex.Message), false, true);
                try
                {
                    await Task.Delay(_backoffMs, cancellationToken);
                }
                catch (OperationCanceledException)
                {
                    return;
                }

                _backoffMs = Math.Min(_backoffMs * 2, 30_000);
            }
        }
    }

    private async Task StartJarvisAsync(CancellationToken cancellationToken)
    {
        StopJarvis();
        var jarvis = AppPaths.JarvisExecutable();
        var start = new ProcessStartInfo
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            WorkingDirectory = Directory.Exists(AppPaths.SrcDir) ? AppPaths.SrcDir : AppPaths.LocalAppData
        };

        if (jarvis.EndsWith("uv.exe", StringComparison.OrdinalIgnoreCase))
        {
            start.FileName = jarvis;
            start.Arguments =
                $"run jarvis serve --engine foundry_local --model {_settings.Current.SelectedModel} --agent {_settings.Current.SelectedAgent} --port 8000 --host 127.0.0.1";
        }
        else if (File.Exists(jarvis))
        {
            start.FileName = jarvis;
            start.Arguments =
                $"serve --engine foundry_local --model {_settings.Current.SelectedModel} --agent {_settings.Current.SelectedAgent} --port 8000 --host 127.0.0.1";
        }
        else
        {
            throw new InvalidOperationException(
                "The OpenJarvis backend is not installed. Repair or reinstall OpenJarvis from Apps & Features.");
        }

        Directory.CreateDirectory(AppPaths.LogsDir);
        start.Environment["OPENJARVIS_HOME"] = AppPaths.ConfigDir;
        _jarvis = Process.Start(start)
            ?? throw new InvalidOperationException("Failed to start jarvis serve.");
        _job.Add(_jarvis);
        _ = DrainAsync(_jarvis, cancellationToken);
        await Task.Delay(500, cancellationToken);
    }

    private async Task WaitUntilUnhealthyAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            await Task.Delay(3000, cancellationToken);
            if (!await _api.IsHealthyAsync(cancellationToken))
            {
                SetStatus("Recovering", "The backend stopped. Restarting…", false, false);
                return;
            }
        }
    }

    private void StopJarvis()
    {
        try
        {
            if (_jarvis is { HasExited: false })
            {
                _jarvis.Kill(entireProcessTree: true);
            }
        }
        catch
        {
            // Best effort.
        }

        _jarvis?.Dispose();
        _jarvis = null;
    }

    private static async Task DrainAsync(Process process, CancellationToken cancellationToken)
    {
        try
        {
            var log = Path.Combine(AppPaths.LogsDir, "jarvis-serve.log");
            await using var writer = new StreamWriter(log, append: true);
            while (!process.HasExited && !cancellationToken.IsCancellationRequested)
            {
                var line = await process.StandardOutput.ReadLineAsync(cancellationToken);
                if (line is null)
                {
                    break;
                }

                await writer.WriteLineAsync(line);
            }
        }
        catch
        {
            // Logging is best-effort.
        }
    }

    private void SetStatus(string phase, string detail, bool ready, bool failed)
    {
        Status.Phase = phase;
        Status.Detail = detail;
        Status.Ready = ready;
        Status.Failed = failed;
        StatusChanged?.Invoke(this, EventArgs.Empty);
    }

    private static string Actionable(string message)
    {
        if (message.Contains("Foundry", StringComparison.OrdinalIgnoreCase))
        {
            return message + " Install the Foundry Local Windows ML ARM64 package, then reopen OpenJarvis.";
        }

        if (message.Contains("jarvis", StringComparison.OrdinalIgnoreCase))
        {
            return message + " Reinstall OpenJarvis if the backend files are missing.";
        }

        return message;
    }
}
