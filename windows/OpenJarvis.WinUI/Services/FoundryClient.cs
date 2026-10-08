using System.Diagnostics;
using System.Text.RegularExpressions;

namespace OpenJarvis.WinUI.Services;

public sealed class FoundryClient
{
    public event EventHandler<string>? Progress;

    public string? FindFoundry()
    {
        var onPath = AppPaths.FindOnPath("foundry.exe");
        if (onPath is not null)
        {
            return onPath;
        }

        var winget = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Microsoft", "WinGet", "Links", "foundry.exe");
        return File.Exists(winget) ? winget : null;
    }

    public async Task<string> EnsureServiceAsync(CancellationToken cancellationToken)
    {
        var foundry = FindFoundry()
            ?? throw new InvalidOperationException(
                "Foundry Local is not installed. Repair OpenJarvis from Apps & Features or install Foundry Local (Windows ML, ARM64).");

        Progress?.Invoke(this, "Starting Foundry Local…");
        await RunAsync(foundry, "service start", cancellationToken);
        var host = await DiscoverHostAsync(foundry, cancellationToken);
        TomlSettings.SetFoundryHost(host);
        TomlSettings.SetEngineDefault("foundry_local");
        return host;
    }

    public async Task DownloadModelAsync(string alias, IProgress<string>? progress, CancellationToken cancellationToken)
    {
        var foundry = FindFoundry()
            ?? throw new InvalidOperationException("Foundry Local is not installed.");
        progress?.Report($"Downloading model {alias}…");
        await RunAsync(foundry, $"model download {alias}", cancellationToken, progress);
        progress?.Report($"Loading model {alias}…");
        await RunAsync(foundry, $"model run {alias} --skip-chat", cancellationToken, progress);
    }

    public async Task<string> DiscoverHostAsync(string foundry, CancellationToken cancellationToken)
    {
        var (stdout, stderr) = await RunCaptureAsync(foundry, "service status --json", cancellationToken);
        var combined = stdout + "\n" + stderr;
        var match = Regex.Match(combined, @"https?://[^\s""']+");
        if (!match.Success)
        {
            (stdout, stderr) = await RunCaptureAsync(foundry, "service status", cancellationToken);
            combined = stdout + "\n" + stderr;
            match = Regex.Match(combined, @"https?://[^\s""']+");
        }

        if (!match.Success)
        {
            throw new InvalidOperationException(
                "Foundry Local started but did not report an endpoint. Run `foundry service status` and set [engine.foundry_local] host.");
        }

        var url = match.Value.TrimEnd('/');
        foreach (var suffix in new[] { "/openai/status", "/openai", "/v1" })
        {
            if (url.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
            {
                url = url[..^suffix.Length];
                break;
            }
        }

        return url;
    }

    private static async Task RunAsync(
        string fileName,
        string arguments,
        CancellationToken cancellationToken,
        IProgress<string>? progress = null)
    {
        var start = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        using var process = Process.Start(start)
            ?? throw new InvalidOperationException($"Failed to start {fileName}.");
        process.OutputDataReceived += (_, e) =>
        {
            if (!string.IsNullOrWhiteSpace(e.Data))
            {
                progress?.Report(e.Data);
            }
        };
        process.ErrorDataReceived += (_, e) =>
        {
            if (!string.IsNullOrWhiteSpace(e.Data))
            {
                progress?.Report(e.Data);
            }
        };
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        await process.WaitForExitAsync(cancellationToken);
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(
                $"Foundry command `{arguments}` failed with exit {process.ExitCode}.");
        }
    }

    private static async Task<(string Stdout, string Stderr)> RunCaptureAsync(
        string fileName,
        string arguments,
        CancellationToken cancellationToken)
    {
        var start = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        using var process = Process.Start(start)
            ?? throw new InvalidOperationException($"Failed to start {fileName}.");
        var stdout = await process.StandardOutput.ReadToEndAsync(cancellationToken);
        var stderr = await process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken);
        return (stdout, stderr);
    }
}
