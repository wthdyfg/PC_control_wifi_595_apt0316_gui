using System;
using Python.Runtime;
namespace wifi_ctrlV1
{

    // 1. 定义一个管理类来持有 Uart SDK 实例
    public class UartManager : IDisposable
    {
        private dynamic sdk;
        private bool isInitialized = false;
        private IntPtr threadState;

        public UartManager(string pythonDllPath)
        {
            if (string.IsNullOrEmpty(Runtime.PythonDLL))
            {
                Runtime.PythonDLL = pythonDllPath;
                PythonEngine.Initialize();
                // 允许 Python 后台线程 (如看门狗和接收线程) 运行
                threadState = PythonEngine.BeginAllowThreads();
            }
            isInitialized = true;
        }

        // --- 建立连接 (串口号, 波特率) ---
        public bool Connect(string portName, int baudRate = 115200)
        {
            using (Py.GIL())
            {
                try
                {
                    dynamic sys = Py.Import("sys");
                    dynamic os = Py.Import("os");

                    // 1. 设置 SDK 路径
                    string sdkPath = @"d:\code\python\FW_X6898_44SET\uart_sdk_project";
                    sys.path.append(sdkPath);

                    // 2. 告诉 Python 去哪里找第三方库
                    string sitePackages = @"C:\Users\Administrator\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\site-packages";
                    sys.path.append(sitePackages);
                    sys.path.append(Path.Combine(sitePackages, "win32"));
                    sys.path.append(Path.Combine(sitePackages, "win32", "lib"));
                    sys.path.append(Path.Combine(sitePackages, "Pythonwin"));
                    
                    // 对于 Python 3.8+，必须显式添加 DLL 目录，否则 win32api 会加载失败
                    string pywin32System32 = Path.Combine(sitePackages, "pywin32_system32");
                    if (Directory.Exists(pywin32System32))
                    {
                        os.add_dll_directory(pywin32System32);
                    }
                    sys.path.append(pywin32System32);

                    // 预导入 pywin32 的核心组件，防止加载顺序问题
                    try { Py.Import("pywintypes"); } catch { }
                    try { Py.Import("pythoncom"); } catch { }

                    // 3. 导入并实例化
                    dynamic uartModule = Py.Import("uart_sdk");
                    sdk = uartModule.UartSDK();

                    // 4. 调用连接
                    return sdk.Connect(portName, baudRate);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"连接异常: {ex.Message}");
                    return false;
                }
            }
        }

        // --- 发送数据 (带 ACK 等待) ---
        public int SendDataWaitACK(byte[] data, int timeoutMs = 1000)
        {
            if (sdk == null) return -1;
            using (Py.GIL())
            {
                try
                {
                    // Python SDK 内部已处理 Byte[] 转换
                    return sdk.SendDataWaitACK(data, timeoutMs);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"发送异常: {ex.Message}");
                    return -1;
                }
            }
        }

        // --- 发送汉字 (GBK) ---
        public bool SendCustomText(string text)
        {
            if (sdk == null) return false;
            using (Py.GIL())
            {
                try
                {
                    return sdk.SendCustomText(text);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"文本发送异常: {ex.Message}");
                    return false;
                }
            }
        }

        // --- 触发外部烧录器 ---
        public void TriggerProgrammer()
        {
            if (sdk == null) return;
            using (Py.GIL())
            {
                sdk.TriggerProgrammer();
            }
        }

        // --- 断开连接 ---
        public void Disconnect()
        {
            if (sdk == null) return;
            using (Py.GIL())
            {
                sdk.Disconnect();
            }
        }

        public void Dispose()
        {
            if (isInitialized)
            {
                try
                {
                    if (threadState != IntPtr.Zero)
                    {
                        PythonEngine.EndAllowThreads(threadState);
                        threadState = IntPtr.Zero;
                    }
                    // 注意：在 .NET Core / .NET 5+ 环境下，PythonEngine.Shutdown() 
                    // 可能会抛出 PlatformNotSupportedException。
                    // 既然程序即将退出，通常可以安全地捕获并忽略它。
                    if (PythonEngine.IsInitialized)
                    {
                        PythonEngine.Shutdown();
                    }
                }
                catch (PlatformNotSupportedException)
                {
                    // 忽略平台不支持的关闭异常
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Dispose 异常: {ex.Message}");
                }
                isInitialized = false;
            }
        }
    }

    internal class Program
    {
        static void Main(string[] args)
        {
            // 确保指向正确的 Python 3.13 DLL 路径
            string dllPath = @"C:\Users\Administrator\python-sdk\python3.13.2\python313.dll";

            using (var manager = new UartManager(dllPath))
            {
                Console.WriteLine("请输入串口号 (例如 COM3):");
                string port = Console.ReadLine();

                if (manager.Connect(port, 115200))
                {
                    Console.WriteLine($"成功连接到 {port}");

                    while (true)
                    {
                        Console.WriteLine("\n请输入指令 (1: 发送测试数据, 2: 发送汉字, 3: 触发烧录, 4: 断开, q: 退出):");
                        string input = Console.ReadLine();

                        if (input == "1")
                        {
                            byte[] data = new byte[] { 0xFF, 0x00, 0xAA, 0x55, 0x01, 0x02 };
                            int res = manager.SendDataWaitACK(data, 1000);
                            Console.WriteLine(res == 1 ? "收到应答: ACK" : "超时或失败");
                        }
                        else if (input == "2")
                        {
                            Console.WriteLine("请输入要发送的汉字:");
                            string text = Console.ReadLine();
                            manager.SendCustomText(text);
                        }
                        else if (input == "3")
                        {
                            manager.TriggerProgrammer();
                        }
                        else if (input == "4")
                        {
                            manager.Disconnect();
                            Console.WriteLine("已断开");
                        }
                        else if (input == "q")
                        {
                            break;
                        }
                    }
                }
                else
                {
                    Console.WriteLine("连接失败，请检查串口号是否正确。");
                }
            }
            Console.WriteLine("程序已退出。");
        }
    }
}
