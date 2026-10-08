using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

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
        var progress = new Progress<string>(line => SetupStatus.Text = line);
        try
        {
            SetupStatus.Text = "Starting Foundry Local…";
            await App.Services.Foundry.EnsureServiceAsync(_cts.Token);
            await App.Services.Foundry.DownloadModelAsync(
                App.Services.Settings.Current.SelectedModel,
                progress,
                _cts.Token);
            App.Services.Settings.Current.SetupComplete = true;
            App.Services.Settings.Save();
            SetupProgress.IsIndeterminate = false;
            SetupProgress.Value = 100;
            SetupStatus.Text = "Setup complete. You can chat offline with this model.";
        }
        catch (Exception ex)
        {
            SetupError.IsOpen = true;
            SetupError.Message = ex.Message;
            SetupStatus.Text = "Setup stopped.";
        }
    }

    private void Skip_Click(object sender, RoutedEventArgs e)
    {
        App.Services.Settings.Current.SetupComplete = true;
        App.Services.Settings.Save();
        SetupStatus.Text = "Setup skipped. Chat still needs a running Foundry model.";
    }
}
