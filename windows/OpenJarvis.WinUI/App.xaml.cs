using Microsoft.UI.Xaml;
using OpenJarvis.WinUI.Services;

namespace OpenJarvis.WinUI;

public partial class App : Application
{
    public static AppServices Services { get; private set; } = null!;
    private Window? _window;

    public App()
    {
        var earlySettings = new SettingsStore();
        earlySettings.Load();
        var theme = SettingsStore.ApplicationThemeOrNull(earlySettings.Current.Theme);
        if (theme is { } requested)
        {
            RequestedTheme = requested;
        }

        InitializeComponent();
        UnhandledException += OnUnhandledException;
    }

    public static Window? MainWindowInstance { get; private set; }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        Services = AppServices.Create();
        _window = new MainWindow();
        MainWindowInstance = _window;
        Services.Settings.ApplyWindowTheme(_window);
        _window.Activate();
    }

    private static void OnUnhandledException(object sender, Microsoft.UI.Xaml.UnhandledExceptionEventArgs e)
    {
        e.Handled = true;
        Services?.Supervisor.ReportUiError(e.Exception.Message);
    }
}
