namespace OpenJarvis.WinUI.Services;

/// <summary>
/// Copies the staged Python venv / source payload from the install directory
/// into %LOCALAPPDATA%\OpenJarvis on first launch so jarvis serve can start
/// without a terminal.
/// </summary>
public static class RuntimeBootstrap
{
    public static void EnsureLocalRuntime(IProgress<string>? progress = null)
    {
        Directory.CreateDirectory(AppPaths.LocalAppData);
        Directory.CreateDirectory(AppPaths.LogsDir);

        var payload = Path.Combine(AppContext.BaseDirectory, "payload");
        if (!Directory.Exists(payload))
        {
            // Dev builds may use a repo checkout with uv on PATH.
            return;
        }

        var payloadPython = Path.Combine(payload, "python");
        if (Directory.Exists(payloadPython) && !File.Exists(Path.Combine(AppPaths.PythonDir, "python.exe")))
        {
            progress?.Report("Installing Python runtime…");
            CopyDirectory(payloadPython, AppPaths.PythonDir);
        }

        var payloadVenv = Path.Combine(payload, "venv");
        if (Directory.Exists(payloadVenv) && !File.Exists(Path.Combine(AppPaths.VenvDir, "Scripts", "jarvis.exe")))
        {
            progress?.Report("Installing OpenJarvis backend runtime…");
            CopyDirectory(payloadVenv, AppPaths.VenvDir);
        }

        PointVenvAtLocalPython();

        var payloadSrc = Path.Combine(payload, "src");
        if (Directory.Exists(payloadSrc) && !Directory.Exists(Path.Combine(AppPaths.SrcDir, "src", "openjarvis")))
        {
            progress?.Report("Installing OpenJarvis source tree…");
            CopyDirectory(payloadSrc, AppPaths.SrcDir);
        }
    }

    /// <summary>
    /// A venv's pyvenv.cfg records the absolute path of its base interpreter,
    /// which is the build machine's path in the payload. Repoint it at the
    /// interpreter copied next to it so the venv starts on this machine.
    /// </summary>
    private static void PointVenvAtLocalPython()
    {
        var cfg = Path.Combine(AppPaths.VenvDir, "pyvenv.cfg");
        if (!File.Exists(cfg) || !File.Exists(Path.Combine(AppPaths.PythonDir, "python.exe")))
        {
            return;
        }

        var home = $"home = {AppPaths.PythonDir}";
        var lines = File.ReadAllLines(cfg);
        var updated = lines
            .Select(line => line.StartsWith("home =", StringComparison.OrdinalIgnoreCase) ? home : line)
            .ToArray();
        if (!updated.SequenceEqual(lines))
        {
            File.WriteAllLines(cfg, updated);
        }
    }

    private static void CopyDirectory(string source, string destination)
    {
        Directory.CreateDirectory(destination);
        foreach (var dir in Directory.EnumerateDirectories(source, "*", SearchOption.AllDirectories))
        {
            Directory.CreateDirectory(dir.Replace(source, destination));
        }

        foreach (var file in Directory.EnumerateFiles(source, "*", SearchOption.AllDirectories))
        {
            var dest = file.Replace(source, destination);
            Directory.CreateDirectory(Path.GetDirectoryName(dest)!);
            File.Copy(file, dest, overwrite: true);
        }
    }
}
