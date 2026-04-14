from uart_sdk import UartSDK
import time

def test():
    sdk = UartSDK()
    
    # 1. 连接串口 (根据实际串口修改，如 COM3)
    port = "COM3"
    print(f"正在尝试连接 {port}...")
    if not sdk.Connect(port, 115200):
        print("连接失败!")
        return

    try:
        # 2. 发送测试数据 (6字节)
        test_data = [0xFF, 0x00, 0xAA, 0x55, 0x01, 0x02]
        print(f"发送数据: {test_data}")
        
        # 使用 WaitACK 方式发送 (等待应答)
        result = sdk.SendDataWaitACK(test_data, 1000)
        if result == 1:
            print("收到 ACK (成功)")
        elif result == 0:
            print("等待 ACK 超时")
        else:
            print("发送数据失败")

        # 3. 发送自定义文本 (GBK编码)
        print("发送文本测试: '串口调试成功'")
        sdk.SendCustomText("串口调试成功")

        # 4. 触发外部烧录程序
        # print("尝试触发外部烧录程序...")
        # sdk.TriggerProgrammer()

        # 5. 等待一段时间，观察看门狗心跳
        print("等待 10 秒看门狗心跳测试 (silent=True)...")
        for i in range(10):
            time.sleep(1)
            # if i == 5:
            #     # 测试断开重连逻辑
            #     pass

    finally:
        # 6. 断开连接
        sdk.Disconnect()
        print("测试结束")

if __name__ == "__main__":
    test()
