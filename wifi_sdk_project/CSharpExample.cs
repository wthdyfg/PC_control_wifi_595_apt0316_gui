using System;
using Python.Runtime;

namespace WifiControlExample
{
    // 1. 定义一个管理类来持有 SDK 实例
    public class WifiManager : IDisposable
    {
        private dynamic sdk;
        private bool isInitialized = false;

        public WifiManager(string pythonDllPath)
        {
            // 初始化 Python 引擎 (整个程序运行期间只需执行一次)
            // 在 pythonnet 3.x 中，正确的方法是使用 Runtime.PythonDLL
            // 注意：某些版本可能需要使用 Environment.SetEnvironmentVariable("PYTHONNET_PYDLL", pythonDllPath);
            if (string.IsNullOrEmpty(Runtime.PythonDLL)) {
                try {
                    Runtime.PythonDLL = pythonDllPath;
                    PythonEngine.Initialize();
                    // 允许 Python 后台线程 (如看门狗) 运行
                    PythonEngine.BeginAllowThreads();
                } catch (Exception) {
                    // 如果 Runtime.PythonDLL 报错，尝试环境变量方式
                    Environment.SetEnvironmentVariable("PYTHONNET_PYDLL", pythonDllPath);
                    PythonEngine.Initialize();
                    // 允许 Python 后台线程 (如看门狗) 运行
                    PythonEngine.BeginAllowThreads();
                }
            }
            isInitialized = true;
        }

        // --- 建立连接 (通常在程序启动或点击连接按钮时调用) ---
        public bool Connect(string ip, int port)
        {
            using (Py.GIL())
            {
                try {
                    sdk = Py.Import("wifi_sdk");
                    return sdk.Connect(ip, port) == 1;
                } catch (Exception ex) {
                    Console.WriteLine($"连接异常: {ex.Message}");
                    return false;
                }
            }
        }

        // --- 发送数据 (可以在任何需要的时候独立调用) ---
        public bool SendData(byte[] data, int timeoutMs = 1000)
        {
            if (sdk == null) return false;

            using (Py.GIL())
            {
                try {
                    // 调用带反馈的发送接口
                    return sdk.SendDataWaitACK(data, timeoutMs) == 1;
                } catch (Exception ex) {
                    Console.WriteLine($"发送异常: {ex.Message}");
                    return false;
                }
            }
        }

        // --- 断开连接 ---
        public bool Disconnect()
        {
            if (sdk == null) return true;

            using (Py.GIL())
            {
                try {
                    return sdk.Disconnect() == 1;
                } catch (Exception ex) {
                    Console.WriteLine($"断开异常: {ex.Message}");
                    return false;
                }
            }
        }

        // --- 触发烧录 ---
        public void TriggerProgrammer()
        {
            if (sdk == null) return;
            using (Py.GIL()) {
                sdk.TriggerProgrammer();
            }
        }

        public void Dispose()
        {
            if (isInitialized) {
                PythonEngine.Shutdown();
            }
        }
    }

    // --- 使用示例 ---
    class Program
    {
        static void Main(string[] args)
        {
            string dllPath = @"C:\Users\Administrator\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python313.dll";
            
            // 1. 初始化管理器
            using (var manager = new WifiManager(dllPath))
            {
                // 2. 在这里连接
                Console.WriteLine("正在连接...");
                if (manager.Connect("192.168.4.1", 8080))
                {
                    Console.WriteLine("连接成功！现在您可以根据需要随时发送数据。");

                    // 3. 模拟在不同时间点发送数据
                    while (true)
                    {
                        Console.WriteLine("\n请输入指令 (1: 发送全开, 2: 发送全关, 3: 触发烧录, 4: 断开连接, q: 退出):");
                        string input = Console.ReadLine();

                        if (input == "1") {
                            manager.SendData(new byte[] { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF });
                        }
                        else if (input == "2") {
                            manager.SendData(new byte[] { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 });
                        }
                        else if (input == "3") {
                            manager.TriggerProgrammer();
                        }
                        else if (input == "4") {
                            if (manager.Disconnect()) {
                                Console.WriteLine("已成功断开连接。");
                            }
                        }
                        else if (input == "q") {
                            break;
                        }
                    }
                }
                else
                {
                    Console.WriteLine("连接失败！");
                }
            }
        }
    }
}
