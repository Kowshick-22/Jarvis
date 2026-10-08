using System.Collections.ObjectModel;
using System.Text.Json;
using OpenJarvis.WinUI.Models;

namespace OpenJarvis.WinUI.Services;

public sealed class ConversationStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    public ObservableCollection<Conversation> Items { get; } = [];
    public Conversation? Active { get; private set; }

    public void Load()
    {
        Items.Clear();
        Active = null;
        if (!File.Exists(AppPaths.ConversationsPath))
        {
            return;
        }

        try
        {
            var file = JsonSerializer.Deserialize<ConversationStoreFile>(
                File.ReadAllText(AppPaths.ConversationsPath), JsonOptions)
                ?? new ConversationStoreFile();
            foreach (var conversation in file.Conversations.Values.OrderByDescending(c => c.UpdatedAt))
            {
                Items.Add(conversation);
            }

            if (file.ActiveId is not null)
            {
                Active = Items.FirstOrDefault(c => c.Id == file.ActiveId);
            }

            Active ??= Items.FirstOrDefault();
        }
        catch
        {
            // Keep an empty store rather than crashing the UI.
        }
    }

    public void Save()
    {
        Directory.CreateDirectory(AppPaths.ConfigDir);
        var file = new ConversationStoreFile
        {
            Version = 1,
            ActiveId = Active?.Id,
            Conversations = Items.ToDictionary(c => c.Id)
        };
        File.WriteAllText(AppPaths.ConversationsPath, JsonSerializer.Serialize(file, JsonOptions));
    }

    public Conversation NewConversation(string model)
    {
        var conversation = new Conversation { Model = model };
        Items.Insert(0, conversation);
        Active = conversation;
        Save();
        return conversation;
    }

    public void Select(Conversation conversation)
    {
        Active = conversation;
        Save();
    }

    public void Touch(Conversation conversation)
    {
        conversation.UpdatedAt = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        if (Items.Contains(conversation))
        {
            Items.Remove(conversation);
            Items.Insert(0, conversation);
        }

        Save();
    }
}
