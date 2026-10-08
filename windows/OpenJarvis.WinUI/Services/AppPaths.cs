namespace OpenJarvis.WinUI.Services;

public static class AppPaths
{
    public static string LocalAppData =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "OpenJarvis");

    public static string ConfigDir =>
        Environment.GetEnvironmentVariable("OPENJARVIS_HOME") is { Length: > 0 } home
            ? home
            : Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                ".openjarvis");

    public static string ConfigToml => Path.Combine(ConfigDir, "config.toml");
    public static string ConversationsPath => Path.Combine(ConfigDir, "winui-conversations.json");
    public static string UiSettingsPath => Path.Combine(ConfigDir, "winui-settings.json");
    public static string RuntimeDir => Path.Combine(LocalAppData, "runtime");
    public static string SrcDir => Path.Combine(LocalAppData, "src");
    public static string VenvDir => Path.Combine(LocalAppData, "venv");
    public static string LogsDir => Path.Combine(LocalAppData, "logs");

    public static string JarvisExecutable()
    {
        var scripts = Path.Combine(VenvDir, "Scripts", "jarvis.exe");
        if (File.Exists(scripts))
        {
            return scripts;
        }

        var uv = FindOnPath("uv.exe");
        return uv ?? "";
    }

    public static string? FindOnPath(string fileName)
    {
        var path = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (var dir in path.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            var candidate = Path.Combine(dir.Trim(), fileName);
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return null;
    }
}
