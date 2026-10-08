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
    }

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

    private void ThemeBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ThemeBox.SelectedItem is ComboBoxItem item && item.Tag is string tag)
        {
            App.Services.Settings.Current.Theme = tag;
            App.Services.Settings.ApplyWindowTheme();
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
