using System.Collections.ObjectModel;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using OpenJarvis.WinUI.Models;
using OpenJarvis.WinUI.Services;

namespace OpenJarvis.WinUI.Views;

public sealed partial class ChatPage : Page
{
    private readonly ObservableCollection<ChatMessage> _messages = [];
    private readonly ObservableCollection<ToolCallInfo> _tools = [];
    private CancellationTokenSource? _sendCts;
    private Conversation? _active;

    public ChatPage()
    {
        InitializeComponent();
        ConversationList.ItemsSource = App.Services.Conversations.Items;
        MessageList.ItemsSource = _messages;
        ToolList.ItemsSource = _tools;
        AgentBox.ItemsSource = AgentChoices.All;
        AgentBox.SelectedItem = App.Services.Settings.Current.SelectedAgent;
        Loaded += OnLoaded;
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
        var models = await App.Services.Api.GetModelsAsync(CancellationToken.None);
        ModelBox.ItemsSource = models.Count > 0 ? models : new[] { App.Services.Settings.Current.SelectedModel };
        var selected = App.Services.Settings.Current.SelectedModel;
        if (models.Contains(selected))
        {
            ModelBox.SelectedItem = selected;
        }
        else if (ModelBox.Items.Count > 0)
        {
            ModelBox.SelectedIndex = 0;
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

    private void NewChat_Click(object sender, RoutedEventArgs e)
    {
        _active = App.Services.Conversations.NewConversation(
            ModelBox.SelectedItem as string ?? App.Services.Settings.Current.SelectedModel);
        ConversationList.SelectedItem = _active;
        ReloadMessages();
        _tools.Clear();
    }

    private void ConversationList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ConversationList.SelectedItem is Conversation conversation)
        {
            App.Services.Conversations.Select(conversation);
            _active = conversation;
            ReloadMessages();
        }
    }

    private void ModelBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ModelBox.SelectedItem is string model)
        {
            App.Services.Settings.Current.SelectedModel = model;
            App.Services.Settings.Save();
            if (_active is not null)
            {
                _active.Model = model;
            }
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

        var text = PromptBox.Text.Trim();
        PromptBox.Text = "";
        var user = new ChatMessage { Role = "user", Content = text };
        var assistant = new ChatMessage { Role = "assistant", Content = "" };
        _active.Messages.Add(user);
        _active.Messages.Add(assistant);
        if (_active.Title == "New chat")
        {
            _active.Title = text.Length > 42 ? text[..42] : text;
        }

        _messages.Add(user);
        _messages.Add(assistant);
        _tools.Clear();
        App.Services.Conversations.Touch(_active);

        _sendCts?.Cancel();
        _sendCts = new CancellationTokenSource();
        SendButton.IsEnabled = false;
        CancelButton.IsEnabled = true;
        var payload = new
        {
            model = ModelBox.SelectedItem as string ?? App.Services.Settings.Current.SelectedModel,
            stream = true,
            temperature = App.Services.Settings.Current.Temperature,
            max_tokens = App.Services.Settings.Current.MaxTokens,
            messages = _active.Messages
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
            App.Services.Conversations.Touch(_active);
        }
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
