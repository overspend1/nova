using System.Text.Json.Serialization;

namespace Nova.Desktop.Models
{
    public sealed class IntentDto
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("rawInput")]
        public string RawInput { get; set; } = string.Empty;

        [JsonPropertyName("normalizedInput")]
        public string NormalizedInput { get; set; } = string.Empty;

        [JsonPropertyName("taskType")]
        public string TaskType { get; set; } = string.Empty;
    }

    public sealed class ActionStepDto
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("title")]
        public string Title { get; set; } = string.Empty;

        [JsonPropertyName("description")]
        public string Description { get; set; } = string.Empty;

        [JsonPropertyName("kind")]
        public string Kind { get; set; } = string.Empty;

        [JsonPropertyName("risk")]
        public string Risk { get; set; } = string.Empty;

        [JsonPropertyName("requiresApproval")]
        public bool RequiresApproval { get; set; }
    }

    public sealed class PlanResponseDto
    {
        [JsonPropertyName("intent")]
        public IntentDto Intent { get; set; } = new();

        [JsonPropertyName("steps")]
        public List<ActionStepDto> Steps { get; set; } = new List<ActionStepDto>();
    }

    public sealed class StepAuditDto
    {
        [JsonPropertyName("stepId")]
        public string StepId { get; set; } = string.Empty;

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("details")]
        public string? Details { get; set; }
    }

    public sealed class ExecutionAuditDto
    {
        [JsonPropertyName("runId")]
        public string RunId { get; set; } = string.Empty;

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("steps")]
        public List<StepAuditDto> Steps { get; set; } = new List<StepAuditDto>();
    }

    public sealed class ExecuteResponseDto
    {
        [JsonPropertyName("audit")]
        public ExecutionAuditDto Audit { get; set; } = new();
    }
}
