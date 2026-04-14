# Python 程序生成 DLL 说明文档

本文件说明了如何将现有的 [PC_control_wifi_gui_v0_1.py](file:///d:/code/python/FW_X6898_44SET/PC_control_wifi_gui_v0_1.py) 中的核心逻辑封装并生成为一个 DLL 文件，以便供 C++、C# 或其他语言调用。

## 1. 代码保护：如何隐藏源代码？

如果您生成 DLL 的主要目的是**不让别人看到源代码**，那么在选择技术方案时需要注意：

| 方案 | 保护等级 | 保护原理 | 反编译难度 |
| :--- | :--- | :--- | :--- |
| **Cython (方案 A)** | **高 (推荐)** | 将 Python 编译为 **C 代码**，再编译为**机器码二进制** (`.pyd`)。 | 极高 (类似反编译 C++) |
| **IronPython (方案 B)** | **中** | 将 Python 编译为 **.NET 中间语言 (MSIL)**。 | 较低 (可被 ILSpy 等工具反编译) |

### ⚠️ 重要提示：关于 `pywinauto` 的兼容性
当前的 `wifi_sdk.py` 使用了 `pywinauto` 来控制外部程序。**IronPython 对 `pywinauto` 的支持非常有限**，因为它不支持许多底层的 C 扩展。如果您强行使用 IronPython 编译，程序极大概率会在运行时报错。

**因此，为了同时实现“隐藏代码”和“兼容功能”，强烈建议坚持使用 Cython (方案 A)。**

---

## 2. 核心逻辑提取 (SDK 接口定义)

目前的 `wifi_sdk_project/wifi_sdk.py` 已为您提取好以下接口：

| 函数名 | 功能说明 | 参数 |
| :--- | :--- | :--- |
| `Connect(ip, port)` | 建立 WiFi 连接 | `char* ip`, `int port` |
| `Disconnect()` | 断开连接 | 无 |
| `SendDataWaitACK(data_array, timeout)` | 发送并等待下位机执行确认 | `unsigned char[6]`, `int timeout_ms` |
| `TriggerProgrammer()` | 触发外部 APT ISP2 烧录 | 无 |

---

## 3. 生成步骤 (使用 Cython 隐藏源码)

这是目前最安全且功能完整的方案：

### 第一步：环境准备 (必须)
由于 Cython 需要将 Python 转换为 C 并进行二进制编译，您的系统必须安装 **Microsoft C++ Build Tools**。
*   下载地址：[Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
*   安装时请勾选：**“使用 C++ 的桌面开发” (Desktop development with C++)**。
*   *注意：如果没有安装此编译器，执行编译命令会报错。*

### 第二步：执行编译
在 `wifi_sdk_project` 文件夹下执行：
```bash
python setup.py build_ext --inplace
```

### 第三步：清理源码
编译成功后，文件夹内会生成一个类似于 `wifi_sdk.cp3xx-win_amd64.pyd` 的二进制文件。
*   **此时您可以删除 `wifi_sdk.py` 原文件**。
*   外部程序（如 C#）只需调用这个 `.pyd` 文件，**完全无法看到您的 Python 源代码**。

---

## 4. 外部调用示例 (C# 调用加密后的 DLL)

在 C# 中调用生成的 `.pyd` 文件，目前最标准且性能最好的方式是使用 **`pythonnet`** 库。

### 4.1 准备工作
1.  在 Visual Studio 的 **NuGet 管理器** 中搜索并安装：`pythonnet`。
2.  将编译生成的 **`wifi_sdk.cp313-win_amd64.pyd`** 拷贝到 C# 项目的输出目录（例如 `bin\Debug\net8.0` 文件夹下）。
3.  确保您的运行环境安装了 **Python 3.13**。

### 4.2 C# 代码示例
我在 [CSharpExample.cs](file:///d:/code/python/FW_X6898_44SET/wifi_sdk_project/CSharpExample.cs) 中为您编写了完整的代码，关键部分如下：

```csharp
using Python.Runtime;

public void SecureControl() {
    // 1. 设置 Python 库路径 (填入您实际的 python313.dll 路径)
    string pythonDll = @"C:\Path\To\python313.dll";
    Environment.SetEnvironmentVariable("PYTHONNET_PYDLL", pythonDll);
    
    // 2. 初始化 Python 引擎
    PythonEngine.Initialize();
    
    using (Py.GIL()) { // 必须在 GIL 锁内操作
        // 3. 导入加密后的二进制文件 (文件名中前面的 wifi_sdk)
        // 注意：无需提供 .pyd 源码，只要文件在运行目录下即可
        dynamic sdk = Py.Import("wifi_sdk"); 
        
        // 4. 调用接口
        int result = sdk.Connect("172.19.181.231", 8080);
        if (result == 1) {
            // 调用发送并等待确认
            byte[] data = new byte[] { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF };
            int ackResult = sdk.SendDataWaitACK(data, 1000);
        }
    }
    
    // 5. 释放引擎
    PythonEngine.Shutdown();
}
```

### 4.3 注意事项 (避坑指南)
*   **文件名导入**：如果编译出来的文件名是 `wifi_sdk.cp313-win_amd64.pyd`，在 C# 中导入时**只需写 `wifi_sdk`**。
*   **平台一致性**：如果生成的 `.pyd` 是 64 位的，C# 项目也必须设置为 **x64** 平台，不能使用 AnyCPU。
*   **DLL 冲突**：如果 C# 报错找不到模块，请检查 `PYTHONNET_PYDLL` 路径是否正确，以及 `.pyd` 文件是否和 `.exe` 在同一目录下。

---

## 5. 常见问题 (FAQ)

1. **报错 "Microsoft Visual C++ 14.0 or greater is required"**：
   * 必须安装上述第一步中的 **Visual Studio Build Tools**，否则无法生成二进制文件。
2. **生成的 `.pyd` 文件可以被看到源码吗？**：
   * 不可以。`.pyd` 是编译后的机器码二进制文件，就像普通的 `.dll` 一样，只能通过汇编级反汇编，无法直接还原为 Python 源码。
3. **IronPython 为什么不推荐？**：
   * 第一，反编译容易；第二，不支持 `pywinauto` 这种涉及 Windows 底层操作的库。

---
**后续操作建议**：如果您确认需要生成 DLL，我将为您编写剥离了 GUI 的 `wifi_sdk.py` 核心逻辑文件。
