using System.Text.Json;
using Microsoft.UI.Xaml;
using OpenJarvis.WinUI.Models;

namespace OpenJarvis.WinUI.Services;

public sealed class SettingsStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    public AppSettings Current { get; private set; } = new();

    public void Load()
    {
        try
        {
            if (File.Exists(AppPaths.UiSettingsPath))
            {
                Current = JsonSerializer.Deserialize<AppSettings>(
                    File.ReadAllText(AppPaths.UiSettingsPath), JsonOptions) ?? new AppSettings();
            }
        }
        catch
        {
            Current = new AppSettings();
        }
    }

    public void Save()
    {
        Directory.CreateDirectory(AppPaths.ConfigDir);
        File.WriteAllText(AppPaths.UiSettingsPath, JsonSerializer.Serialize(Current, JsonOptions));
        TomlSettings.SetAllowCloud(Current.AllowCloud);
    }

    /// <summary>
    /// Must run in the <see cref="Application"/> constructor before
    /// <c>InitializeComponent</c>. Setting <see cref="Application.RequestedTheme"/>
    /// later throws COMException 0x80131515.
    /// </summary>
    public static ApplicationTheme? ApplicationThemeOrNull(string theme) =>
        theme switch
        {
            "Light" => ApplicationTheme.Light,
            "Dark" => ApplicationTheme.Dark,
            _ => null
        };

    public void ApplyWindowTheme(Window? window = null)
    {
        window ??= App.MainWindowInstance;
        if (window?.Content is not FrameworkElement root)
        {
            return;
        }

        root.RequestedTheme = Current.Theme switch
        {
            "Light" => ElementTheme.Light,
            "Dark" => ElementTheme.Dark,
            _ => ElementTheme.Default
        };
    }
}
