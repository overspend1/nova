using Windows.Media.SpeechRecognition;

namespace Nova.Desktop.Services
{
    public sealed class VoiceCoordinator
    {
        private CancellationTokenSource? _wakeWordCts;

        public bool WakeWordEnabled => _wakeWordCts is not null;

        public async Task<string?> CapturePushToTalkAsync(CancellationToken cancellationToken = default)
        {
            using var recognizer = new SpeechRecognizer();
            await recognizer.CompileConstraintsAsync();
            var result = await recognizer.RecognizeAsync().AsTask(cancellationToken);
            if (result.Status != SpeechRecognitionResultStatus.Success)
            {
                return null;
            }
            return result.Text;
        }

        public async Task StartWakeWordLoopAsync(Func<Task> onWakeWord, Action<string> onStatus)
        {
            if (_wakeWordCts is not null)
            {
                return;
            }

            _wakeWordCts = new CancellationTokenSource();
            onStatus("Wake-word loop enabled (placeholder engine).");

            // Wake-word engine integration point:
            // Replace this loop with local wake-word inference (e.g., OpenWakeWord).
            var ticks = 0;
            try
            {
                while (!_wakeWordCts.IsCancellationRequested)
                {
                    await Task.Delay(TimeSpan.FromSeconds(3), _wakeWordCts.Token);
                    ticks++;
                    onStatus("Listening for wake-word 'Nova'...");
                    if (ticks % 5 == 0)
                    {
                        await onWakeWord();
                    }
                }
            }
            catch (TaskCanceledException)
            {
                // Expected when wake-word loop is disabled.
            }
        }

        public void StopWakeWordLoop(Action<string> onStatus)
        {
            _wakeWordCts?.Cancel();
            _wakeWordCts?.Dispose();
            _wakeWordCts = null;
            onStatus("Wake-word loop disabled.");
        }
    }
}
