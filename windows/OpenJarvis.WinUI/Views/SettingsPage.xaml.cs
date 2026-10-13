using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using OpenJarvis.WinUI.Services;

namespace OpenJarvis.WinUI.Views;

public sealed partial class SettingsPage : Page
{
    public SettingsPage()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Loaded += (_, _) =>
        {
            ApplySupervisorStatus();
            App.Services.Supervisor.StatusChanged += OnSupervisorStatusChanged;
        };
        Unloaded += (_, _) => App.Services.Supervisor.StatusChanged -= OnSupervisorStatusChanged;
    }

    private void OnSupervisorStatusChanged(object? sender, EventArgs e) =>
        DispatcherQueue.TryEnqueue(ApplySupervisorStatus);

    /// <summary>
    /// Mirrors <see cref="App.Services.Supervisor"/>'s live status — the
    /// same automatic install/start/model-load sequence <c>MainWindow</c>'s
    /// status text already shows, not a separate manually-triggered setup
    /// flow. The former standalone Setup page re-ran that whole sequence by
    /// hand on every click, so it always started from a blank 0% (it never
    /// looked at the supervisor's real state) and finished "instantly" once
    /// clicked, because the supervisor had usually already done the work
    /// in the background seconds after launch.
    /// </summary>
    private void ApplySupervisorStatus()
    {
        var status = App.Services.Supervisor.Status;
        SetupStatusText.Text = string.IsNullOrWhiteSpace(status.Detail)
            ? status.Phase
            : $"{status.Phase} — {status.Detail}";
        SetupStatusIcon.Glyph = status switch
        {
            { Failed: true } => "", // Error
            { Ready: true } => "", // CheckMark
            _ => "" // Sync (in progress)
        };
        SetupErrorBar.IsOpen = status.Failed;
        SetupErrorBar.Message = status.Detail;
        RetrySetupButton.IsEnabled = !status.Ready;
    }

    private void RetrySetup_Click(object sender, RoutedEventArgs e) => App.Services.Supervisor.Start();

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        var settings = App.Services.Settings.Current;
        ApiBox.Text = settings.ApiUrl;
        TemperatureBox.Value = settings.Temperature;
        MaxTokensBox.Value = settings.MaxTokens;
        CloudSwitch.IsOn = settings.AllowCloud;
        foreach (ComboBoxItem item in ThemeBox.Items)
        {
            if (item.Tag as string == settings.Theme)
            {
                ThemeBox.SelectedItem = item;
            }
        }

        ThemeBox.SelectedIndex = ThemeBox.SelectedIndex < 0 ? 0 : ThemeBox.SelectedIndex;
        _themeReady = true;

        var info = await App.Services.Api.GetInfoAsync(CancellationToken.None);
        if (info?.Hardware is { } hw)
        {
            var ep = string.IsNullOrWhiteSpace(hw.ExecutionProvider) ? "unknown" : hw.ExecutionProvider;
            var fallback = hw.ExecutionProviderFallback
                ? "CPU fallback is active. GPU/NPU plugins were not used."
                : "Accelerated execution provider is active.";
            HardwareBlock.Text =
                $"Engine: {info.Engine}\nModel: {info.Model}\nCPU: {hw.CpuBrand}\nArch: {hw.Arch}\n" +
                $"RAM: {hw.RamGb} GB\nGPU: {hw.Gpu?.Name ?? "none"}\nExecution provider: {ep}\n{fallback}";
        }
        else
        {
            HardwareBlock.Text = "Connect to a running backend to read hardware and execution provider.";
        }

        WindowsAiList.ItemsSource = WindowsAiAvailability.Probe()
            .Select(s => $"{s.Api}: {s.ReadyState}. {s.Detail}")
            .ToList();
    }

    private bool _themeReady;

    private void ThemeBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_themeReady)
        {
            return;
        }

        if (ThemeBox.SelectedItem is ComboBoxItem item &&
            item.Tag is string tag &&
            tag != App.Services.Settings.Current.Theme)
        {
            App.Services.Settings.Current.Theme = tag;
            App.Services.Settings.ApplyWindowTheme();
            App.Services.Settings.Persist();
        }
    }

    private void CloudSwitch_Toggled(object sender, RoutedEventArgs e)
    {
        // Applied on Save so the user makes an explicit choice.
    }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        var settings = App.Services.Settings.Current;
        settings.ApiUrl = ApiBox.Text.Trim();
        settings.Temperature = TemperatureBox.Value;
        settings.MaxTokens = (int)MaxTokensBox.Value;
        settings.AllowCloud = CloudSwitch.IsOn;
        App.Services.Settings.Save();
        TomlSettings.SetAllowCloud(settings.AllowCloud);
        App.Services.Api.SetBaseUrl(settings.ApiUrl);
        if (settings.AllowCloud)
        {
            App.Services.Supervisor.ReportUiError(
                "Cloud inference is enabled. Restart OpenJarvis so jarvis serve attaches cloud engines.");
        }
    }
}
