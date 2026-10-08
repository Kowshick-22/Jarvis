using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using OpenJarvis.WinUI.Models;

namespace OpenJarvis.WinUI.Services;

public sealed class SseEvent
{
    public string? Event { get; init; }
    public string Data { get; init; } = "";
}

public sealed class JarvisApiClient
{
    private readonly HttpClient _http = new() { Timeout = Timeout.InfiniteTimeSpan };
    private string _base = "http://127.0.0.1:8000";

    public void SetBaseUrl(string url)
    {
        _base = url.TrimEnd('/');
    }

    public async Task<bool> IsHealthyAsync(CancellationToken cancellationToken)
    {
        try
        {
            using var response = await _http.GetAsync($"{_base}/health", cancellationToken);
            return response.IsSuccessStatusCode || (int)response.StatusCode == 503;
        }
        catch (HttpRequestException)
        {
            return false;
        }
        catch (TaskCanceledException)
        {
            return false;
        }
    }

    public async Task<bool> IsEngineHealthyAsync(CancellationToken cancellationToken)
    {
        try
        {
            using var response = await _http.GetAsync($"{_base}/health", cancellationToken);
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    public async Task<ServerInfo?> GetInfoAsync(CancellationToken cancellationToken)
    {
        try
        {
            return await _http.GetFromJsonAsync<ServerInfo>($"{_base}/v1/info", cancellationToken);
        }
        catch
        {
            return null;
        }
    }

    public async Task<IReadOnlyList<string>> GetModelsAsync(CancellationToken cancellationToken)
    {
        try
        {
            using var response = await _http.GetAsync($"{_base}/v1/models", cancellationToken);
            response.EnsureSuccessStatusCode();
            using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync(cancellationToken));
            if (!doc.RootElement.TryGetProperty("data", out var data))
            {
                return [];
            }

            return data.EnumerateArray()
                .Select(item => item.TryGetProperty("id", out var id) ? id.GetString() ?? "" : "")
                .Where(id => !string.IsNullOrWhiteSpace(id))
                .ToList();
        }
        catch
        {
            return [];
        }
    }

    public async Task<IReadOnlyList<PendingApproval>> GetPendingApprovalsAsync(
        CancellationToken cancellationToken)
    {
        try
        {
            var payload = await _http.GetFromJsonAsync<JsonElement>(
                $"{_base}/v1/approvals/pending", cancellationToken);
            if (payload.ValueKind == JsonValueKind.Array)
            {
                return payload.Deserialize<List<PendingApproval>>() ?? [];
            }

            if (payload.TryGetProperty("approvals", out var approvals))
            {
                return approvals.Deserialize<List<PendingApproval>>() ?? [];
            }

            if (payload.TryGetProperty("pending", out var pending))
            {
                return pending.Deserialize<List<PendingApproval>>() ?? [];
            }
        }
        catch
        {
            // Backend may still be starting.
        }

        return [];
    }

    public Task ApproveAsync(string id, CancellationToken cancellationToken) =>
        _http.PostAsync($"{_base}/v1/approvals/{id}/approve", null, cancellationToken);

    public Task DenyAsync(string id, CancellationToken cancellationToken) =>
        _http.PostAsync($"{_base}/v1/approvals/{id}/deny", null, cancellationToken);

    public async IAsyncEnumerable<SseEvent> StreamChatAsync(
        object request,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, $"{_base}/v1/chat/completions")
        {
            Content = JsonContent.Create(request)
        };
        message.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("text/event-stream"));
        using var response = await _http.SendAsync(
            message, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken);
            throw new InvalidOperationException($"Chat failed ({(int)response.StatusCode}): {body}");
        }

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var reader = new StreamReader(stream, Encoding.UTF8);
        string? currentEvent = null;
        while (!reader.EndOfStream)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var line = await reader.ReadLineAsync(cancellationToken);
            if (line is null)
            {
                yield break;
            }

            if (line.StartsWith("event: ", StringComparison.Ordinal))
            {
                currentEvent = line["event: ".Length..].Trim();
            }
            else if (line.StartsWith("data: ", StringComparison.Ordinal))
            {
                var data = line["data: ".Length..];
                if (data == "[DONE]")
                {
                    yield break;
                }

                yield return new SseEvent { Event = currentEvent, Data = data };
                currentEvent = null;
            }
            else if (string.IsNullOrWhiteSpace(line))
            {
                currentEvent = null;
            }
        }
    }
}
