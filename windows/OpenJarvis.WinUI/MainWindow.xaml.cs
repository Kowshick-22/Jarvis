using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using OpenJarvis.WinUI.Services;
using OpenJarvis.WinUI.Views;

namespace OpenJarvis.WinUI;

public sealed partial class MainWindow : Window
{
    private const double DefaultNavPaneWidth = 260;
    private const double MinNavPaneWidth = 200;
    private const double MaxNavPaneWidth = 480;
    private bool _resizingNavPane;
    private double _resizeStartWidth;
    private double _resizeStartX;

    public MainWindow()
    {
        InitializeComponent();
        App.Services.Settings.ApplyWindowTheme(this);
        Activated += OnActivated;
        TrySetIcon();
        App.Services.Supervisor.StatusChanged += OnStatusChanged;

        NavView.OpenPaneLength = ClampNavPaneWidth(SavedNavPaneWidth());
        UpdateNavPaneSplitterPosition();

        SetupOverlay.Completed += SetupOverlay_Completed;
        SetupOverlay.Begin();

        _ = CheckUpdatesAsync();
        Closed += (_, _) => App.Services.Supervisor.Dispose();
    }

    private void SetupOverlay_Completed(object? sender, EventArgs e)
    {
        SetupOverlay.Visibility = Visibility.Collapsed;
        ShellGrid.Visibility = Visibility.Visible;
        NavView.SelectedItem = NavView.MenuItems[0];
        NavigateTo("chat");
        OnStatusChanged(this, EventArgs.Empty);
    }

    private void RootGrid_SizeChanged(object sender, SizeChangedEventArgs e)
    {
        if (_resizingNavPane)
        {
            return;
        }

        NavView.OpenPaneLength = ClampNavPaneWidth(SavedNavPaneWidth());
        UpdateNavPaneSplitterPosition();
    }

    private void NavPaneSplitter_PointerPressed(object sender, PointerRoutedEventArgs e)
    {
        _resizingNavPane = true;
        _resizeStartWidth = NavView.OpenPaneLength;
        _resizeStartX = e.GetCurrentPoint(RootGrid).Position.X;
        NavPaneSplitter.CapturePointer(e.Pointer);
        ShowNavSplitterActive();
        e.Handled = true;
    }

    private void NavPaneSplitter_PointerMoved(object sender, PointerRoutedEventArgs e)
    {
        if (!_resizingNavPane)
        {
            return;
        }

        var x = e.GetCurrentPoint(RootGrid).Position.X;
        NavView.OpenPaneLength = ClampNavPaneWidth(_resizeStartWidth + (x - _resizeStartX));
        UpdateNavPaneSplitterPosition();
        e.Handled = true;
    }

    private void NavPaneSplitter_PointerReleased(object sender, PointerRoutedEventArgs e)
    {
        if (!_resizingNavPane)
        {
            return;
        }

        FinishNavPaneResize();
        NavPaneSplitter.ReleasePointerCapture(e.Pointer);
        e.Handled = true;
    }

    private void NavPaneSplitter_PointerCaptureLost(object sender, PointerRoutedEventArgs e)
    {
        if (!_resizingNavPane)
        {
            return;
        }

        FinishNavPaneResize();
    }

    private void NavPaneSplitter_PointerEntered(object sender, PointerRoutedEventArgs e) =>
        ShowNavSplitterActive();

    private void NavPaneSplitter_PointerExited(object sender, PointerRoutedEventArgs e)
    {
        if (!_resizingNavPane)
        {
            ShowNavSplitterIdle();
        }
    }

    private void NavPaneSplitter_KeyDown(object sender, KeyRoutedEventArgs e)
    {
        var delta = e.Key switch
        {
            Windows.System.VirtualKey.Left => -16d,
            Windows.System.VirtualKey.Right => 16d,
            _ => 0d
        };
        if (delta == 0)
        {
            return;
        }

        NavView.OpenPaneLength = ClampNavPaneWidth(NavView.OpenPaneLength + delta);
        UpdateNavPaneSplitterPosition();
        PersistNavPaneWidth();
        e.Handled = true;
    }

    private void FinishNavPaneResize()
    {
        _resizingNavPane = false;
        PersistNavPaneWidth();
        ShowNavSplitterIdle();
    }

    private void PersistNavPaneWidth()
    {
        App.Services.Settings.Current.NavPaneWidth = NavView.OpenPaneLength;
        App.Services.Settings.Persist();
    }

    private static double SavedNavPaneWidth()
    {
        var saved = App.Services.Settings.Current.NavPaneWidth;
        return saved >= MinNavPaneWidth ? saved : DefaultNavPaneWidth;
    }

    private double ClampNavPaneWidth(double width)
    {
        var contentWidth = RootGrid.ActualWidth;
        var max = contentWidth - 400; // leave room for page content
        if (contentWidth <= 0 || max < MinNavPaneWidth)
        {
            max = MaxNavPaneWidth;
        }

        return Math.Clamp(width, MinNavPaneWidth, Math.Min(max, MaxNavPaneWidth));
    }

    private void UpdateNavPaneSplitterPosition()
    {
        NavPaneSplitter.Margin = new Thickness(NavView.OpenPaneLength, 0, 0, 0);
    }

    private void ShowNavSplitterActive()
    {
        NavPaneSplitterBar.Opacity = 1;
        if (Application.Current.Resources.TryGetValue("AccentFillColorDefaultBrush", out var accent) &&
            accent is Brush accentBrush)
        {
            NavPaneSplitterBar.Background = accentBrush;
        }
    }

    private void ShowNavSplitterIdle()
    {
        NavPaneSplitterBar.Opacity = 0.6;
        if (Application.Current.Resources.TryGetValue("DividerStrokeColorDefaultBrush", out var divider) &&
            divider is Brush dividerBrush)
        {
            NavPaneSplitterBar.Background = dividerBrush;
        }
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
            var iconPath = Path.Combine(AppContext.BaseDirectory, "Assets", "OpenJarvis.ico");
            if (File.Exists(iconPath))
            {
                appWindow.SetIcon(iconPath);
            }

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
