namespace Nova.Desktop
{
    public partial class App : Application
    {
        private Window? _window;

        public App()
        {
            InitializeComponent();
        }

        protected override void OnLaunched(LaunchActivatedEventArgs args)
        {
            _window ??= new Window();
            _window.Content = new MainPage();
            _window.Activate();
        }
    }
}
