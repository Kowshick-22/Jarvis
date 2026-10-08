using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;
using WinRT;

namespace OpenJarvis.WinUI;

public static class Program
{
    [STAThread]
    public static void Main(string[] args)
    {
        ComWrappersSupport.InitializeComWrappers();
        Application.Start(InitializeApp);
    }

    private static void InitializeApp(ApplicationInitializationCallbackParams initParams)
    {
        var context = new DispatcherQueueSynchronizationContext(
            DispatcherQueue.GetForCurrentThread());
        SynchronizationContext.SetSynchronizationContext(context);
        var app = new App();
    }
}
