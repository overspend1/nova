using System.Text;
using System.Text.Json;
using Microsoft.UI.Dispatching;
using Nova.Desktop.Models;
using Nova.Desktop.Services;

namespace Nova.Desktop.Views;

public sealed partial class MainPage : Page
{
    private readonly NovaCoreClient _coreClient;
    private readonly VoiceCoordinator _voiceCoordinator = new();
    private readonly JsonSerializerOptions _jsonOptions = new() { PropertyNameCaseInsensitive = true };
    private readonly JsonSerializerOptions _indentedJsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    private IntentDto? _lastIntent;
    private List<ActionStepDto> _lastPlanSteps = [];

    public MainPage()
    {
        InitializeComponent();

        var pipePath = Environment.GetEnvironmentVariable("NOVA_PIPE_PATH") ?? "\\\\.\\pipe\\nova-core-v1";
        var authToken = Environment.GetEnvironmentVariable("NOVA_AUTH_TOKEN") ?? string.Empty;
        _coreClient = new NovaCoreClient(pipePath, authToken);
        ResponseBox.Text = "Nova ready. Start the core service and set NOVA_AUTH_TOKEN before planning.";
    }

    private async void OnPlanClicked(object sender, RoutedEventArgs e)
    {
        await RunSafeAsync(async () =>
        {
            EnsurePromptAvailable();
            var response = await _coreClient.PostAsync<object, JsonElement>(
                "/actions/plan",
                new
                {
                    input = PromptBox.Text,
                    channel = "text"
                });

            var plan = response.Deserialize<PlanResponseDto>(_jsonOptions)
                       ?? throw new InvalidOperationException("Failed to parse plan response.");

            _lastIntent = plan.Intent;
            _lastPlanSteps = plan.Steps;
            ResponseBox.Text = JsonSerializer.Serialize(plan, _indentedJsonOptions);
        });
    }

    private async void OnExecuteDryRunClicked(object sender, RoutedEventArgs e)
    {
        await RunSafeAsync(async () =>
        {
            await EnsurePlanReadyAsync();
            var execute = await _coreClient.PostAsync<object, JsonElement>(
                "/actions/execute",
                new
                {
                    mode = "dry-run",
                    intent = _lastIntent,
                    steps = _lastPlanSteps,
                    approvals = BuildApprovals(_lastPlanSteps, allowWrite: false, allowSystem: false)
                });

            ResponseBox.Text = JsonSerializer.Serialize(execute, _indentedJsonOptions);
        });
    }

    private async void OnExecuteApprovedClicked(object sender, RoutedEventArgs e)
    {
        await RunSafeAsync(async () =>
        {
            await EnsurePlanReadyAsync();
            EnsureApprovalConfirmed();
            var execute = await _coreClient.PostAsync<object, JsonElement>(
                "/actions/execute",
                new
                {
                    mode = "execute",
                    intent = _lastIntent,
                    steps = _lastPlanSteps,
                    approvals = BuildApprovals(
                        _lastPlanSteps,
                        allowWrite: ApproveWritesCheckbox.IsChecked == true,
                        allowSystem: ApproveSystemCheckbox.IsChecked == true)
                });

            var result = execute.Deserialize<ExecuteResponseDto>(_jsonOptions)
                         ?? throw new InvalidOperationException("Failed to parse execute response.");
            ResponseBox.Text = $"Execution status: {result.Audit.Status}\n"
                + JsonSerializer.Serialize(result, _indentedJsonOptions);
            await RefreshAuditAsync();
            ApprovalConfirmedCheckbox.IsChecked = false;
        });
    }

    private async void OnBootstrapDryRunClicked(object sender, RoutedEventArgs e)
    {
        await RunSafeAsync(async () =>
        {
            EnsurePromptAvailable();
            var target = Environment.GetEnvironmentVariable("NOVA_BOOTSTRAP_TARGET")
                         ?? Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);

            var response = await _coreClient.PostAsync<object, JsonElement>(
                "/bootstrap/create",
                new
                {
                    brief = PromptBox.Text,
                    targetDirectory = target,
                    mode = "dry-run"
                });

            ResponseBox.Text = JsonSerializer.Serialize(response, _indentedJsonOptions);
        });
    }

    private async void OnPushToTalkClicked(object sender, RoutedEventArgs e)
    {
        await RunSafeAsync(async () =>
        {
            VoiceStatusText.Text = "Listening (push-to-talk)...";
            var transcript = await _voiceCoordinator.CapturePushToTalkAsync();
            if (!string.IsNullOrWhiteSpace(transcript))
            {
                PromptBox.Text = transcript;
                VoiceStatusText.Text = "Speech captured into prompt box.";
            }
            else
            {
                VoiceStatusText.Text = "No speech recognized.";
            }
        });
    }

    private async void OnRefreshAuditClicked(object sender, RoutedEventArgs e)
    {
        await RunSafeAsync(RefreshAuditAsync);
    }

    private async void OnWakeWordToggled(object sender, RoutedEventArgs e)
    {
        await RunSafeAsync(async () =>
        {
            if (WakeWordToggle.IsOn)
            {
                _ = _voiceCoordinator.StartWakeWordLoopAsync(
                    onWakeWord: async () =>
                    {
                        await DispatcherQueue.EnqueueAsync(() =>
                        {
                            VoiceStatusText.Text = "Wake-word trigger received. Press Push-To-Talk to capture intent.";
                        });
                    },
                    onStatus: status =>
                    {
                        _ = DispatcherQueue.EnqueueAsync(() => { VoiceStatusText.Text = status; });
                    });
            }
            else
            {
                _voiceCoordinator.StopWakeWordLoop(status =>
                {
                    VoiceStatusText.Text = status;
                });
            }
        });
    }

    private async Task RefreshAuditAsync()
    {
        var auditJson = await _coreClient.GetAsync<JsonElement>("/audit/timeline?limit=20");
        AuditBox.Text = JsonSerializer.Serialize(auditJson, _indentedJsonOptions);
    }

    private void EnsurePromptAvailable()
    {
        if (string.IsNullOrWhiteSpace(PromptBox.Text))
        {
            throw new InvalidOperationException("Prompt is empty.");
        }
    }

    private async Task EnsurePlanReadyAsync()
    {
        if (_lastIntent is not null && _lastPlanSteps.Count > 0)
        {
            return;
        }
        var planned = await _coreClient.PostAsync<object, JsonElement>(
            "/actions/plan",
            new
            {
                input = PromptBox.Text,
                channel = "text"
            });
        var plan = planned.Deserialize<PlanResponseDto>(_jsonOptions)
                   ?? throw new InvalidOperationException("Unable to read generated plan.");
        _lastIntent = plan.Intent;
        _lastPlanSteps = plan.Steps;
    }

    private void EnsureApprovalConfirmed()
    {
        if (ApprovalConfirmedCheckbox.IsChecked != true)
        {
            throw new InvalidOperationException(
                "Execution blocked. You must explicitly confirm approval before running mutating actions.");
        }
    }

    private static IReadOnlyList<object> BuildApprovals(
        IEnumerable<ActionStepDto> steps,
        bool allowWrite,
        bool allowSystem)
    {
        var output = new List<object>();
        foreach (var step in steps.Where(step => step.RequiresApproval))
        {
            var approved = step.Kind switch
            {
                "write" => allowWrite,
                "bootstrap" => allowWrite,
                "memory" => allowWrite,
                "system" => allowSystem,
                "install" => allowSystem,
                "git" => allowSystem,
                "network" => allowSystem,
                _ => false
            };
            output.Add(new
            {
                actionId = step.Id,
                approved,
                approver = "desktop-user"
            });
        }
        return output;
    }

    private async Task RunSafeAsync(Func<Task> action)
    {
        try
        {
            await action();
        }
        catch (Exception error)
        {
            var message = new StringBuilder()
                .AppendLine("Nova action failed.")
                .AppendLine(error.Message)
                .ToString();
            ResponseBox.Text = message;
        }
    }
}

internal static class DispatcherQueueExtensions
{
    public static Task EnqueueAsync(this DispatcherQueue queue, Action action)
    {
        var tcs = new TaskCompletionSource();
        _ = queue.TryEnqueue(() =>
        {
            try
            {
                action();
                tcs.SetResult();
            }
            catch (Exception error)
            {
                tcs.SetException(error);
            }
        });
        return tcs.Task;
    }
}
