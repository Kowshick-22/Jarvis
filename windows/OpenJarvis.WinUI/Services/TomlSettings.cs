using System.Text.RegularExpressions;

namespace OpenJarvis.WinUI.Services;

public static class TomlSettings
{
    public static void EnsureConfigDir()
    {
        Directory.CreateDirectory(AppPaths.ConfigDir);
    }

    public static void SetAllowCloud(bool allow)
    {
        EnsureConfigDir();
        var path = AppPaths.ConfigToml;
        var value = allow ? "true" : "false";
        if (!File.Exists(path))
        {
            File.WriteAllText(path, $"[engine]\ndefault = \"foundry_local\"\nallow_cloud = {value}\n");
            return;
        }

        var text = File.ReadAllText(path);
        if (Regex.IsMatch(text, @"^\s*allow_cloud\s*=", RegexOptions.Multiline))
        {
            text = Regex.Replace(
                text,
                @"^\s*allow_cloud\s*=\s*(true|false).*$",
                $"allow_cloud = {value}",
                RegexOptions.Multiline | RegexOptions.IgnoreCase);
        }
        else if (text.Contains("[engine]"))
        {
            text = text.Replace("[engine]", $"[engine]\nallow_cloud = {value}");
        }
        else
        {
            text = $"[engine]\nallow_cloud = {value}\n\n" + text;
        }

        File.WriteAllText(path, text);
    }

    public static void SetFoundryHost(string host)
    {
        EnsureConfigDir();
        var path = AppPaths.ConfigToml;
        var block = $"[engine.foundry_local]\nhost = \"{host}\"\n";
        if (!File.Exists(path))
        {
            File.WriteAllText(path, $"[engine]\ndefault = \"foundry_local\"\nallow_cloud = false\n\n{block}");
            return;
        }

        var text = File.ReadAllText(path);
        if (Regex.IsMatch(text, @"\[engine\.foundry_local\]"))
        {
            if (Regex.IsMatch(text, @"\[engine\.foundry_local\][^\[]*host\s*="))
            {
                text = Regex.Replace(
                    text,
                    @"(\[engine\.foundry_local\][^\[]*?host\s*=\s*)""[^""]*""",
                    $"$1\"{host}\"",
                    RegexOptions.Singleline);
            }
            else
            {
                text = Regex.Replace(
                    text,
                    @"\[engine\.foundry_local\]",
                    $"[engine.foundry_local]\nhost = \"{host}\"");
            }
        }
        else
        {
            text += "\n" + block;
        }

        File.WriteAllText(path, text);
    }

    public static void SetEngineDefault(string engine)
    {
        EnsureConfigDir();
        var path = AppPaths.ConfigToml;
        if (!File.Exists(path))
        {
            File.WriteAllText(path, $"[engine]\ndefault = \"{engine}\"\nallow_cloud = false\n");
            return;
        }

        var text = File.ReadAllText(path);
        if (Regex.IsMatch(text, @"^\s*default\s*=", RegexOptions.Multiline))
        {
            text = Regex.Replace(
                text,
                @"(?m)^(\s*default\s*=\s*)""[^""]*""",
                $"$1\"{engine}\"",
                RegexOptions.Multiline);
        }

        File.WriteAllText(path, text);
    }
}
