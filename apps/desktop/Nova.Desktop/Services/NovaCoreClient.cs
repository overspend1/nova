using System.IO.Pipes;
using System.Text;
using System.Text.Json;

namespace Nova.Desktop.Services;

public sealed class NovaCoreClient
{
    private readonly string _pipeName;
    private readonly string _authToken;
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    public NovaCoreClient(string pipePath, string authToken)
    {
        _pipeName = NormalizePipeName(pipePath);
        _authToken = authToken;
    }

    public Task<TResponse> GetAsync<TResponse>(string endpoint, CancellationToken cancellationToken = default)
    {
        return SendAsync<object, TResponse>("GET", endpoint, null, cancellationToken);
    }

    public Task<TResponse> PostAsync<TRequest, TResponse>(
        string endpoint,
        TRequest payload,
        CancellationToken cancellationToken = default)
    {
        return SendAsync<TRequest, TResponse>("POST", endpoint, payload, cancellationToken);
    }

    private async Task<TResponse> SendAsync<TRequest, TResponse>(
        string method,
        string endpoint,
        TRequest? payload,
        CancellationToken cancellationToken)
    {
        using var client = new NamedPipeClientStream(
            ".",
            _pipeName,
            PipeDirection.InOut,
            PipeOptions.Asynchronous);

        await client.ConnectAsync(cancellationToken);

        var body = payload is null ? string.Empty : JsonSerializer.Serialize(payload, _jsonOptions);
        var request = BuildRequest(method, endpoint, body);
        var bytes = Encoding.UTF8.GetBytes(request);
        await client.WriteAsync(bytes, cancellationToken);
        await client.FlushAsync(cancellationToken);

        using var reader = new StreamReader(client, Encoding.UTF8);
        var responseRaw = await reader.ReadToEndAsync(cancellationToken);
        var responseBody = ParseHttpBody(responseRaw, out var statusCode);

        if (statusCode >= 400)
        {
            throw new InvalidOperationException($"Nova core returned {statusCode}: {responseBody}");
        }

        if (typeof(TResponse) == typeof(string))
        {
            return (TResponse)(object)responseBody;
        }

        return JsonSerializer.Deserialize<TResponse>(responseBody, _jsonOptions)
               ?? throw new InvalidOperationException("Unable to parse Nova core response.");
    }

    private string BuildRequest(string method, string endpoint, string body)
    {
        var length = Encoding.UTF8.GetByteCount(body);
        var builder = new StringBuilder();
        builder.Append($"{method} {endpoint} HTTP/1.1\r\n");
        builder.Append("Host: nova-core\r\n");
        builder.Append("Connection: close\r\n");
        builder.Append($"x-nova-token: {_authToken}\r\n");

        if (method == "POST")
        {
            builder.Append("Content-Type: application/json\r\n");
            builder.Append($"Content-Length: {length}\r\n");
        }

        builder.Append("\r\n");
        if (!string.IsNullOrEmpty(body))
        {
            builder.Append(body);
        }

        return builder.ToString();
    }

    private static string ParseHttpBody(string responseRaw, out int statusCode)
    {
        var lines = responseRaw.Split("\r\n");
        statusCode = 500;
        if (lines.Length > 0)
        {
            var parts = lines[0].Split(' ');
            if (parts.Length >= 2 && int.TryParse(parts[1], out var parsed))
            {
                statusCode = parsed;
            }
        }

        var separator = "\r\n\r\n";
        var index = responseRaw.IndexOf(separator, StringComparison.Ordinal);
        if (index < 0)
        {
            return "{}";
        }
        return responseRaw[(index + separator.Length)..];
    }

    private static string NormalizePipeName(string pipePath)
    {
        var marker = "\\\\.";
        if (pipePath.StartsWith(marker))
        {
            var segments = pipePath.Split('\\', StringSplitOptions.RemoveEmptyEntries);
            return segments[^1];
        }
        return pipePath;
    }
}

