using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using OpenJarvis.WinUI.Services;
using OpenJarvis.WinUI.Views;

namespace OpenJarvis.WinUI;

public sealed partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        App.Services.Settings.ApplyWindowTheme(this);
        Activated += OnActivated;
        TrySetIcon();
        App.Services.Supervisor.StatusChanged += OnStatusChanged;
        App.Services.Supervisor.Start();
        NavView.SelectedItem = NavView.MenuItems[0];
        if (!App.Services.Settings.Current.SetupComplete)
        {
            NavigateTo("setup");
        }
        else
        {
            NavigateTo("chat");
        }

        _ = CheckUpdatesAsync();
        Closed += (_, _) => App.Services.Supervisor.Dispose();
    }

    private bool _reappliedThemeAfterActivation;

    private void OnActivated(object sender, WindowActivatedEventArgs e)
    {
        if (_reappliedThemeAfterActivation || e.WindowActivationState == WindowActivationState.Deactivated)
        {
            return;
        }

        _reappliedThemeAfterActivation = true;
        DispatcherQueue.TryEnqueue(() => App.Services.Settings.ApplyWindowTheme(this));
    }

    private void TrySetIcon()
    {
        try
        {
            IntPtr hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            var windowId = Microsoft.UI.Win32Interop.GetWindowIdFromWindow(hwnd);
            var appWindow = Microsoft.UI.Windowing.AppWindow.GetFromWindowId(windowId);
            appWindow.Resize(new Windows.Graphics.SizeInt32(1920, 1200));
        }
        catch
        {
            // Window chrome is optional.
        }
    }

    private void NavView_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        if (args.IsSettingsSelected)
        {
            NavigateTo("settings");
            return;
        }

        if (args.SelectedItem is NavigationViewItem item && item.Tag is string tag)
        {
            NavigateTo(tag);
        }
    }

    private void NavigateTo(string tag)
    {
        var page = tag switch
        {
            "chat" => typeof(ChatPage),
            "settings" => typeof(SettingsPage),
            "setup" => typeof(SetupPage),
            "approvals" => typeof(ApprovalsPage),
            "dashboard" => typeof(DashboardPage),
            "datasources" => typeof(DataSourcesPage),
            "agents" => typeof(AgentsPage),
            "logs" => typeof(LogsPage),
            _ => typeof(ChatPage)
        };
        ContentFrame.Navigate(page);
    }

    private void OnStatusChanged(object? sender, EventArgs e)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            var status = App.Services.Supervisor.Status;
            StatusText.Text = string.IsNullOrWhiteSpace(status.Detail)
                ? status.Phase
                : $"{status.Phase}: {status.Detail}";
            ErrorBar.IsOpen = status.Failed;
            ErrorBar.Message = status.Detail;
        });
    }

    private async Task CheckUpdatesAsync()
    {
        try
        {
            var update = await App.Services.Updates.CheckAsync(
                App.Services.UpdateManifestUrl, CancellationToken.None);
            if (update is null)
            {
                return;
            }

            DispatcherQueue.TryEnqueue(async () =>
            {
                var dialog = new ContentDialog
                {
                    Title = "Update available",
                    Content = $"OpenJarvis {update.Version} is available.\n{update.Notes}",
                    PrimaryButtonText = "Download",
                    CloseButtonText = "Later",
                    XamlRoot = Content.XamlRoot,
                    RequestedTheme = App.Services.Settings.CurrentElementTheme()
                };
                if (await dialog.ShowAsync() == ContentDialogResult.Primary)
                {
                    UpdateChecker.LaunchInstaller(update.Url);
                }
            });
        }
        catch
        {
            // Updates are optional.
        }
    }
}
