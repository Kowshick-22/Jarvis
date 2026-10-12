using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using OpenJarvis.WinUI.Services;

namespace OpenJarvis.WinUI.Views;

public sealed partial class SetupPage : Page
{
    private CancellationTokenSource? _cts;

    public SetupPage()
    {
        InitializeComponent();
    }

    private async void Start_Click(object sender, RoutedEventArgs e)
    {
        _cts?.Cancel();
        _cts = new CancellationTokenSource();
        SetupError.IsOpen = false;
        SetupProgress.IsIndeterminate = true;
        StartButton.IsEnabled = false;
        SkipButton.IsEnabled = false;
        var progress = new Progress<string>(line => SetupStatus.Text = line);
        try
        {
            SetupStatus.Text = "Installing Foundry Local if needed…";
            await App.Services.Foundry.EnsureInstalledAsync(_cts.Token, progress);

            SetupStatus.Text = "Starting Foundry Local…";
            await App.Services.Foundry.EnsureServiceAsync(_cts.Token, progress);

            var model = App.Services.Settings.Current.SelectedModel;
            try
            {
                await App.Services.Foundry.DownloadModelAsync(model, progress, _cts.Token);
            }
            catch (Exception ex) when (FoundryClient.CpuCatalogId(model) is string cpuModel)
            {
                ((IProgress<string>)progress).Report(
                    $"GPU/WebGPU load failed ({ex.Message}). Trying CPU catalog id {cpuModel}…");
                await App.Services.Foundry.DownloadModelAsync(cpuModel, progress, _cts.Token);
                App.Services.Settings.Current.SelectedModel = cpuModel;
                model = cpuModel;
            }

            App.Services.Settings.Current.SetupComplete = true;
            App.Services.Settings.Save();
            SetupProgress.IsIndeterminate = false;
            SetupProgress.Value = 100;
            SetupStatus.Text =
                "Setup complete. You can disconnect the network and chat with this model offline.";
        }
        catch (OperationCanceledException)
        {
            SetupStatus.Text = "Setup cancelled.";
        }
        catch (Exception ex)
        {
            SetupError.IsOpen = true;
            SetupError.Message = Actionable(ex.Message);
            SetupStatus.Text = "Setup stopped.";
        }
        finally
        {
            StartButton.IsEnabled = true;
            SkipButton.IsEnabled = true;
            if (SetupProgress.IsIndeterminate)
            {
                SetupProgress.IsIndeterminate = false;
            }
        }
    }

    private void Skip_Click(object sender, RoutedEventArgs e)
    {
        App.Services.Settings.Current.SetupComplete = true;
        App.Services.Settings.Save();
        SetupStatus.Text =
            "Setup skipped. Chat still needs Foundry Local and a loaded model — use Start setup when ready.";
    }

    private static string Actionable(string message)
    {
        if (message.Contains("download", StringComparison.OrdinalIgnoreCase))
        {
            return message + " Connect to the internet and try Start setup again.";
        }

        if (message.Contains("Add-AppxPackage", StringComparison.OrdinalIgnoreCase) ||
            message.Contains("Installing Foundry", StringComparison.OrdinalIgnoreCase))
        {
            return message
                + " If Windows blocked the package, enable developer sideloading for apps, then retry.";
        }

        if (message.Contains("generic-cpu", StringComparison.OrdinalIgnoreCase) ||
            message.Contains("Could not load model", StringComparison.OrdinalIgnoreCase))
        {
            return message
                + " On Parallels/VMs without a GPU, set the model to a *-generic-cpu catalog id in Settings after Setup.";
        }

        return message;
    }
}
