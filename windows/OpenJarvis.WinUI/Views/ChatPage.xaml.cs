using System.Collections.ObjectModel;
using System.Text.Json;
using Microsoft.UI.Input;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using OpenJarvis.WinUI.Models;
using OpenJarvis.WinUI.Services;

namespace OpenJarvis.WinUI.Views;

public sealed partial class ChatPage : Page
{
    private readonly ObservableCollection<ChatMessage> _messages = [];
    private readonly ObservableCollection<ToolCallInfo> _tools = [];
    private CancellationTokenSource? _sendCts;
    private const double DefaultSidebarWidth = 260;
    private const double MinSidebarWidth = 200;
    private const double MaxSidebarWidth = 560;

    private Conversation? _active;
    private Conversation? _chatBeforeDelete;
    private bool _suppressModelChange;
    private bool _suppressListSelection;
    private bool _resizingSidebar;
    private double _resizeStartWidth;
    private double _resizeStartX;

    public ChatPage()
    {
        InitializeComponent();
        App.Services.Conversations.Items.CollectionChanged += OnConversationsChanged;
        ApplyConversationFilter();
        MessageList.ItemsSource = _messages;
        ToolList.ItemsSource = _tools;
        AgentBox.ItemsSource = AgentChoices.All;
        AgentBox.SelectedItem = App.Services.Settings.Current.SelectedAgent;
        ApplySidebar(App.Services.Settings.Current.ChatSidebarCollapsed);
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        App.Services.Supervisor.StatusChanged += OnBackendStatusChanged;
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        App.Services.Supervisor.StatusChanged -= OnBackendStatusChanged;
        App.Services.Conversations.Items.CollectionChanged -= OnConversationsChanged;
    }

    private void OnConversationsChanged(object? sender, System.Collections.Specialized.NotifyCollectionChangedEventArgs e) =>
        ApplyConversationFilter();

    private void ConversationSearchBox_TextChanged(
        AutoSuggestBox sender, AutoSuggestBoxTextChangedEventArgs args) =>
        ApplyConversationFilter();

    private void ApplyConversationFilter()
    {
        var query = ConversationSearchBox?.Text?.Trim() ?? "";
        var items = App.Services.Conversations.Items.AsEnumerable();
        if (query.Length > 0)
        {
            items = items.Where(c => c.Title.Contains(query, StringComparison.OrdinalIgnoreCase));
        }

        _suppressListSelection = true;
        try
        {
            ConversationList.ItemsSource = items.ToList();
            ConversationList.SelectedItem = _active;
        }
        finally
        {
            _suppressListSelection = false;
        }
    }

    private void ToggleTheme_Click(object sender, RoutedEventArgs e)
    {
        var next = App.Services.Settings.CycleTheme();
        ThemeToggleIcon.Glyph = next switch
        {
            "Light" => "", // Sunny
            "Dark" => "", // ClearNight
            _ => "" // Settings/auto-ish glyph for "system"
        };
    }

    private void OnBackendStatusChanged(object? sender, EventArgs e)
    {
        DispatcherQueue.TryEnqueue(SyncSelectedModel);
    }

    private void SyncSelectedModel()
    {
        var model = App.Services.Settings.Current.SelectedModel;
        if (string.IsNullOrWhiteSpace(model) || SelectedModelId() == model)
        {
            return;
        }

        _suppressModelChange = true;
        try
        {
            EnsureModelInPicker(model, installed: true);
            SelectModelInPicker(model);
            if (_active is not null)
            {
                _active.Model = model;
            }
        }
        finally
        {
            _suppressModelChange = false;
        }
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        _active = App.Services.Conversations.Active;
        if (_active is null)
        {
            _active = App.Services.Conversations.NewConversation(App.Services.Settings.Current.SelectedModel);
        }

        ConversationList.SelectedItem = _active;
        ReloadMessages();
        await RefreshServerAsync();
    }

    private void ReloadMessages()
    {
        _messages.Clear();
        if (_active is null)
        {
            return;
        }

        foreach (var message in _active.Messages)
        {
            _messages.Add(message);
        }
    }

    private async Task RefreshServerAsync()
    {
        var info = await App.Services.Api.GetInfoAsync(CancellationToken.None);
        var catalog = await App.Services.Foundry.ListCatalogAsync(CancellationToken.None);
        var apiModels = await App.Services.Api.GetModelsAsync(CancellationToken.None);
        _suppressModelChange = true;
        try
        {
            PopulateModelPicker(catalog, apiModels);
            var selected = App.Services.Settings.Current.SelectedModel;
            if (!SelectModelInPicker(selected) && ModelBox.Items.Count > 0)
            {
                ModelBox.SelectedIndex = FirstSelectableIndex();
            }
        }
        finally
        {
            _suppressModelChange = false;
        }

        if (info?.Hardware is { } hw)
        {
            var ep = string.IsNullOrWhiteSpace(hw.ExecutionProvider) ? "unknown" : hw.ExecutionProvider;
            var fallback = hw.ExecutionProviderFallback ? " (CPU fallback)" : "";
            var gpu = hw.Gpu?.Name ?? "no GPU reported";
            HardwareText.Text = $"{info.Engine} · {info.Model} · {ep}{fallback} · {gpu}";
            if (info.ToolCalling is { Supported: false })
            {
                HardwareText.Text += " · tools unavailable";
            }
        }
    }

    private const string AvailableSeparator = "── Available to download ──";

    private void PopulateModelPicker(FoundryModelCatalog catalog, IReadOnlyList<string> apiModels)
    {
        ModelBox.ItemsSource = null;
        ModelBox.Items.Clear();

        var installed = catalog.Installed.Count > 0
            ? catalog.Installed
            : apiModels;
        var selected = App.Services.Settings.Current.SelectedModel;
        if (!string.IsNullOrWhiteSpace(selected) &&
            !installed.Contains(selected, StringComparer.OrdinalIgnoreCase) &&
            !catalog.Available.Contains(selected, StringComparer.OrdinalIgnoreCase))
        {
            installed = installed.Append(selected).ToArray();
        }

        foreach (var id in installed)
        {
            ModelBox.Items.Add(ModelPickerItem(id));
        }

        if (catalog.Available.Count > 0)
        {
            ModelBox.Items.Add(new ComboBoxItem
            {
                Content = AvailableSeparator,
                IsEnabled = false,
                IsHitTestVisible = false
            });
            foreach (var id in catalog.Available)
            {
                ModelBox.Items.Add(ModelPickerItem(id));
            }
        }

        if (ModelBox.Items.Count == 0 && !string.IsNullOrWhiteSpace(selected))
        {
            ModelBox.Items.Add(ModelPickerItem(selected));
        }
    }

    private static ComboBoxItem ModelPickerItem(string id) =>
        new() { Content = id, Tag = id };

    private bool SelectModelInPicker(string model)
    {
        if (string.IsNullOrWhiteSpace(model))
        {
            return false;
        }

        foreach (var item in ModelBox.Items)
        {
            if (item is ComboBoxItem combo &&
                string.Equals(combo.Tag as string ?? combo.Content as string, model, StringComparison.OrdinalIgnoreCase))
            {
                ModelBox.SelectedItem = combo;
                return true;
            }
        }

        return false;
    }

    private void EnsureModelInPicker(string model, bool installed)
    {
        if (SelectModelInPicker(model))
        {
            return;
        }

        var item = ModelPickerItem(model);
        if (installed)
        {
            var separator = ModelBox.Items
                .OfType<ComboBoxItem>()
                .FirstOrDefault(i => i.Content as string == AvailableSeparator);
            if (separator is not null)
            {
                ModelBox.Items.Insert(ModelBox.Items.IndexOf(separator), item);
            }
            else
            {
                ModelBox.Items.Insert(0, item);
            }
        }
        else
        {
            ModelBox.Items.Add(item);
        }
    }

    private int FirstSelectableIndex()
    {
        for (var i = 0; i < ModelBox.Items.Count; i++)
        {
            if (ModelBox.Items[i] is ComboBoxItem { IsEnabled: true })
            {
                return i;
            }
        }

        return 0;
    }

    private string? SelectedModelId()
    {
        return ModelBox.SelectedItem switch
        {
            ComboBoxItem { Tag: string tag } => tag,
            ComboBoxItem { Content: string content } => content,
            string id => id,
            _ => null
        };
    }

    private void ToggleSidebar_Click(object sender, RoutedEventArgs e)
    {
        var collapsed = Sidebar.Visibility == Visibility.Visible;
        ApplySidebar(collapsed);
        App.Services.Settings.Current.ChatSidebarCollapsed = collapsed;
        App.Services.Settings.Persist();
    }

    private void ApplySidebar(bool collapsed)
    {
        SidebarColumn.Width = collapsed ? new GridLength(0) : new GridLength(ClampSidebarWidth(SavedSidebarWidth()));
        SidebarGapColumn.Width = collapsed ? new GridLength(0) : new GridLength(16);
        Sidebar.Visibility = collapsed ? Visibility.Collapsed : Visibility.Visible;
        SidebarSplitter.Visibility = collapsed ? Visibility.Collapsed : Visibility.Visible;
        SidebarSplitter.IsTabStop = !collapsed;

        // ToggleSidebarButton now lives inside the Sidebar panel itself (it
        // collapses along with it, same as React's in-sidebar collapse
        // button), so it only ever needs to say "Hide" \u2014 ReopenSidebarButton,
        // in the always-visible content header, is the only way back once
        // collapsed (matching React's separate floating reopen button).
        ReopenSidebarButton.Visibility = collapsed ? Visibility.Visible : Visibility.Collapsed;
    }

    private void RootGrid_SizeChanged(object sender, SizeChangedEventArgs e)
    {
        if (_resizingSidebar || Sidebar.Visibility != Visibility.Visible)
        {
            return;
        }

        SidebarColumn.Width = new GridLength(ClampSidebarWidth(SavedSidebarWidth()));
    }

    private void SidebarSplitter_PointerPressed(object sender, PointerRoutedEventArgs e)
    {
        if (Sidebar.Visibility != Visibility.Visible)
        {
            return;
        }

        _resizingSidebar = true;
        _resizeStartWidth = SidebarColumn.ActualWidth;
        _resizeStartX = e.GetCurrentPoint(RootGrid).Position.X;
        SidebarSplitter.CapturePointer(e.Pointer);
        ShowSplitterActive();
        e.Handled = true;
    }

    private void SidebarSplitter_PointerMoved(object sender, PointerRoutedEventArgs e)
    {
        if (!_resizingSidebar)
        {
            return;
        }

        var x = e.GetCurrentPoint(RootGrid).Position.X;
        SidebarColumn.Width = new GridLength(ClampSidebarWidth(_resizeStartWidth + (x - _resizeStartX)));
        e.Handled = true;
    }

    private void SidebarSplitter_PointerReleased(object sender, PointerRoutedEventArgs e)
    {
        if (!_resizingSidebar)
        {
            return;
        }

        FinishSidebarResize();
        SidebarSplitter.ReleasePointerCapture(e.Pointer);
        e.Handled = true;
    }

    private void SidebarSplitter_PointerCaptureLost(object sender, PointerRoutedEventArgs e)
    {
        if (!_resizingSidebar)
        {
            return;
        }

        FinishSidebarResize();
    }

    private void SidebarSplitter_PointerEntered(object sender, PointerRoutedEventArgs e) =>
        ShowSplitterActive();

    private void SidebarSplitter_PointerExited(object sender, PointerRoutedEventArgs e)
    {
        if (!_resizingSidebar)
        {
            ShowSplitterIdle();
        }
    }

    private void SidebarSplitter_KeyDown(object sender, KeyRoutedEventArgs e)
    {
        var delta = e.Key switch
        {
            Windows.System.VirtualKey.Left => -16d,
            Windows.System.VirtualKey.Right => 16d,
            _ => 0d
        };
        if (delta == 0 || Sidebar.Visibility != Visibility.Visible)
        {
            return;
        }

        SidebarColumn.Width = new GridLength(ClampSidebarWidth(SidebarColumn.ActualWidth + delta));
        PersistSidebarWidth();
        e.Handled = true;
    }

    private void FinishSidebarResize()
    {
        _resizingSidebar = false;
        PersistSidebarWidth();
        ShowSplitterIdle();
    }

    private void PersistSidebarWidth()
    {
        App.Services.Settings.Current.ChatSidebarWidth = SidebarColumn.ActualWidth;
        App.Services.Settings.Persist();
    }

    private double SavedSidebarWidth()
    {
        var saved = App.Services.Settings.Current.ChatSidebarWidth;
        return saved >= MinSidebarWidth ? saved : DefaultSidebarWidth;
    }

    private double ClampSidebarWidth(double width)
    {
        var contentWidth = RootGrid.ActualWidth - RootGrid.Padding.Left - RootGrid.Padding.Right;
        var max = contentWidth - 16 - 320;
        if (contentWidth <= 0 || max < MinSidebarWidth)
        {
            max = MaxSidebarWidth;
        }

        return Math.Clamp(width, MinSidebarWidth, Math.Min(max, MaxSidebarWidth));
    }

    private void ShowSplitterActive()
    {
        SidebarSplitterBar.Opacity = 1;
        if (Application.Current.Resources.TryGetValue("AccentFillColorDefaultBrush", out var accent) &&
            accent is Brush accentBrush)
        {
            SidebarSplitterBar.Background = accentBrush;
        }
    }

    private void ShowSplitterIdle()
    {
        SidebarSplitterBar.Opacity = 0.6;
        if (Application.Current.Resources.TryGetValue("DividerStrokeColorDefaultBrush", out var divider) &&
            divider is Brush dividerBrush)
        {
            SidebarSplitterBar.Background = dividerBrush;
        }
    }

    private void NewChat_Click(object sender, RoutedEventArgs e)
    {
        _active = App.Services.Conversations.NewConversation(
            SelectedModelId() ?? App.Services.Settings.Current.SelectedModel);
        ConversationList.SelectedItem = _active;
        ReloadMessages();
        _tools.Clear();
    }

    private void ConversationList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_suppressListSelection)
        {
            return;
        }

        if (ConversationList.SelectedItem is Conversation conversation)
        {
            App.Services.Conversations.Select(conversation);
            _active = conversation;
            ReloadMessages();
        }
    }

    private void DeleteChat_PointerPressed(object sender, PointerRoutedEventArgs e)
    {
        _chatBeforeDelete = _active;
    }

    private async void DeleteChat_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not FrameworkElement { Tag: string id })
        {
            return;
        }

        var conversation = App.Services.Conversations.Items.FirstOrDefault(c => c.Id == id);
        if (conversation is null)
        {
            return;
        }

        var dialog = new ContentDialog
        {
            Title = "Delete chat?",
            Content = $"\"{conversation.Title}\" will be removed from this device.",
            PrimaryButtonText = "Delete",
            CloseButtonText = "Cancel",
            DefaultButton = ContentDialogButton.Close,
            XamlRoot = XamlRoot,
            RequestedTheme = App.Services.Settings.CurrentElementTheme()
        };
        if (await dialog.ShowAsync() != ContentDialogResult.Primary)
        {
            RestoreChatIfDeleteCancelled(id);
            return;
        }

        var deletingActive = _active?.Id == conversation.Id;
        if (deletingActive)
        {
            _sendCts?.Cancel();
        }

        _suppressListSelection = true;
        try
        {
            App.Services.Conversations.Delete(conversation);
            if (!deletingActive)
            {
                return;
            }

            _active = App.Services.Conversations.Active
                ?? App.Services.Conversations.NewConversation(
                    SelectedModelId() ?? App.Services.Settings.Current.SelectedModel);
            ConversationList.SelectedItem = _active;
            ReloadMessages();
            _tools.Clear();
        }
        finally
        {
            _suppressListSelection = false;
        }
    }

    private void RestoreChatIfDeleteCancelled(string deletedId)
    {
        if (_chatBeforeDelete is null ||
            _chatBeforeDelete.Id == deletedId ||
            _active?.Id != deletedId ||
            !App.Services.Conversations.Items.Contains(_chatBeforeDelete))
        {
            return;
        }

        _suppressListSelection = true;
        try
        {
            ConversationList.SelectedItem = _chatBeforeDelete;
            App.Services.Conversations.Select(_chatBeforeDelete);
            _active = _chatBeforeDelete;
            ReloadMessages();
        }
        finally
        {
            _suppressListSelection = false;
        }
    }

    private async void ModelBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_suppressModelChange)
        {
            return;
        }

        if (ModelBox.SelectedItem is ComboBoxItem { IsEnabled: false })
        {
            _suppressModelChange = true;
            try
            {
                SelectModelInPicker(App.Services.Settings.Current.SelectedModel);
            }
            finally
            {
                _suppressModelChange = false;
            }

            return;
        }

        var model = SelectedModelId();
        if (string.IsNullOrWhiteSpace(model) ||
            model == AvailableSeparator ||
            model == App.Services.Settings.Current.SelectedModel)
        {
            return;
        }

        App.Services.Settings.Current.SelectedModel = model;
        App.Services.Settings.Save();
        if (_active is not null)
        {
            _active.Model = model;
        }

        try
        {
            await App.Services.Supervisor.RestartWithModelAsync(model, CancellationToken.None);
            await RefreshServerAsync();
        }
        catch (Exception ex)
        {
            App.Services.Supervisor.ReportUiError(ex.Message);
        }
    }

    private async void AgentBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (AgentBox.SelectedItem is not string agent ||
            agent == App.Services.Settings.Current.SelectedAgent)
        {
            return;
        }

        try
        {
            await App.Services.Supervisor.RestartWithAgentAsync(agent, CancellationToken.None);
        }
        catch (Exception ex)
        {
            App.Services.Supervisor.ReportUiError(ex.Message);
        }
    }

    private async void Send_Click(object sender, RoutedEventArgs e) => await SendAsync();

    private async void PromptBox_KeyDown(object sender, KeyRoutedEventArgs e)
    {
        if (e.Key == Windows.System.VirtualKey.Enter &&
            Microsoft.UI.Input.InputKeyboardSource.GetKeyStateForCurrentThread(Windows.System.VirtualKey.Shift)
                .HasFlag(Windows.UI.Core.CoreVirtualKeyStates.Down) == false)
        {
            e.Handled = true;
            await SendAsync();
        }
    }

    private void Cancel_Click(object sender, RoutedEventArgs e) => _sendCts?.Cancel();

    private void CopyMessage_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not FrameworkElement { Tag: ChatMessage message })
        {
            return;
        }

        var package = new Windows.ApplicationModel.DataTransfer.DataPackage();
        package.SetText(message.Content);
        Windows.ApplicationModel.DataTransfer.Clipboard.SetContent(package);
    }

    private void MessageRow_PointerEntered(object sender, PointerRoutedEventArgs e)
    {
        if (sender is FrameworkElement { } row && row.FindName("CopyButton") is Button button)
        {
            button.Opacity = 1;
        }
    }

    private void MessageRow_PointerExited(object sender, PointerRoutedEventArgs e)
    {
        if (sender is FrameworkElement { } row && row.FindName("CopyButton") is Button button)
        {
            button.Opacity = 0;
        }
    }

    private async Task SendAsync()
    {
        if (_active is null || string.IsNullOrWhiteSpace(PromptBox.Text))
        {
            return;
        }

        if (!App.Services.Supervisor.Status.Ready)
        {
            App.Services.Supervisor.ReportUiError(App.Services.Supervisor.Status.Detail);
            return;
        }

        var active = _active;
        var text = PromptBox.Text.Trim();
        PromptBox.Text = "";
        var user = new ChatMessage { Role = "user", Content = text };
        var assistant = new ChatMessage { Role = "assistant", Content = "" };
        active.Messages.Add(user);
        active.Messages.Add(assistant);
        if (active.Title == "New chat")
        {
            active.Title = text.Length > 42 ? text[..42] : text;
        }

        _messages.Add(user);
        _messages.Add(assistant);
        _tools.Clear();
        App.Services.Conversations.Touch(active);

        _sendCts?.Cancel();
        _sendCts = new CancellationTokenSource();
        SendButton.IsEnabled = false;
        CancelButton.IsEnabled = true;
        var payload = new
        {
            model = ResolveModelId(
                SelectedModelId() ?? App.Services.Settings.Current.SelectedModel),
            stream = true,
            temperature = App.Services.Settings.Current.Temperature,
            max_tokens = App.Services.Settings.Current.MaxTokens,
            messages = active.Messages
                .Where(m => m != assistant)
                .Select(m => new { role = m.Role, content = m.Content })
                .ToList()
        };

        try
        {
            await foreach (var evt in App.Services.Api.StreamChatAsync(payload, _sendCts.Token))
            {
                ApplySse(assistant, evt);
                MessageList.ScrollIntoView(assistant);
            }
        }
        catch (OperationCanceledException)
        {
            assistant.Content += assistant.Content.Length == 0 ? "(stopped)" : "";
        }
        catch (Exception ex)
        {
            assistant.Content = string.IsNullOrEmpty(assistant.Content)
                ? $"The request failed: {ex.Message}"
                : assistant.Content;
            App.Services.Supervisor.ReportUiError(ex.Message);
        }
        finally
        {
            SendButton.IsEnabled = true;
            CancelButton.IsEnabled = false;
            if (App.Services.Conversations.Items.Contains(active))
            {
                App.Services.Conversations.Touch(active);
            }
        }
    }

    private string ResolveModelId(string selected)
    {
        if (string.IsNullOrWhiteSpace(selected))
        {
            return selected;
        }

        if (selected.Contains(':', StringComparison.Ordinal))
        {
            return selected;
        }

        foreach (var item in ModelBox.Items.OfType<ComboBoxItem>())
        {
            if (item.Content as string == AvailableSeparator)
            {
                continue;
            }

            var id = item.Tag as string ?? item.Content as string ?? "";
            if (id.Equals(selected, StringComparison.OrdinalIgnoreCase) ||
                id.StartsWith(selected + ":", StringComparison.OrdinalIgnoreCase) ||
                id.StartsWith(selected + "-", StringComparison.OrdinalIgnoreCase))
            {
                return id;
            }
        }

        return selected;
    }

    private void ApplySse(ChatMessage assistant, SseEvent evt)
    {
        if (evt.Event is "tool_call_start" or "tool_call_end")
        {
            try
            {
                using var doc = JsonDocument.Parse(evt.Data);
                var root = doc.RootElement;
                var name = root.TryGetProperty("tool", out var tool) ? tool.GetString() ?? "tool" : "tool";
                var existing = _tools.FirstOrDefault(t => t.Tool == name) ?? new ToolCallInfo { Tool = name };
                if (!_tools.Contains(existing))
                {
                    _tools.Add(existing);
                }

                existing.Status = evt.Event == "tool_call_end" ? "success" : "running";
                if (root.TryGetProperty("arguments", out var args))
                {
                    existing.Arguments = args.ToString();
                }

                if (root.TryGetProperty("result", out var result))
                {
                    existing.Result = result.ToString();
                }

                assistant.ToolCalls = _tools.ToList();
            }
            catch
            {
                _tools.Add(new ToolCallInfo { Tool = evt.Event, Status = "running" });
            }

            return;
        }

        try
        {
            using var doc = JsonDocument.Parse(evt.Data);
            if (doc.RootElement.TryGetProperty("choices", out var choices) &&
                choices.GetArrayLength() > 0)
            {
                var delta = choices[0].GetProperty("delta");
                if (delta.TryGetProperty("content", out var content))
                {
                    assistant.Content += content.GetString();
                    var index = _messages.IndexOf(assistant);
                    if (index >= 0)
                    {
                        _messages[index] = assistant;
                    }
                }
            }
        }
        catch
        {
            // Non-JSON keepalive chunks are ignored.
        }
    }
}

public sealed class SidebarResizeGrip : Grid
{
    public SidebarResizeGrip()
    {
        ProtectedCursor = InputSystemCursor.Create(InputSystemCursorShape.SizeWestEast);
    }
}

/// <summary>
/// Picks the user (plain-text, right-aligned bubble) vs. assistant
/// (Markdown-rendered, no bubble) message template. React's own
/// <c>MessageBubble.tsx</c> draws the same distinction — it only runs
/// ReactMarkdown on the assistant branch, rendering the user's text as-is.
/// </summary>
public sealed class ChatMessageTemplateSelector : DataTemplateSelector
{
    public DataTemplate? UserTemplate { get; set; }
    public DataTemplate? AssistantTemplate { get; set; }

    protected override DataTemplate? SelectTemplateCore(object item) =>
        item is ChatMessage { Role: "user" } ? UserTemplate : AssistantTemplate;

    protected override DataTemplate? SelectTemplateCore(object item, DependencyObject container) =>
        SelectTemplateCore(item);
}
