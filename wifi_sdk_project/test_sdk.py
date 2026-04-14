import wifi_sdk

def main():
    print("SDK 交互测试启动")
    ip = input("设备IP(回车默认 192.168.4.1): ").strip() or "192.168.4.1"
    p = input("端口(回车默认 8080): ").strip()
    port = int(p) if p else 8080
    print(f"正在连接到 {ip}:{port} ...")
    ok = wifi_sdk.Connect(ip, port)
    if ok != 1:
        print("连接失败")
        return
    print("连接成功")
    try:
        while True:
            print("\n指令: 1全开 2全关 3触发烧录 4断开 5自定义发送 q退出")
            cmd = input("选择: ").strip().lower()
            if cmd == "1":
                data = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
                r = wifi_sdk.SendDataWaitACK(data, 1000)
                print("ACK成功" if r == 1 else "ACK超时或失败")
            elif cmd == "2":
                data = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                r = wifi_sdk.SendDataWaitACK(data, 1000)
                print("ACK成功" if r == 1 else "ACK超时或失败")
            elif cmd == "3":
                wifi_sdk.TriggerProgrammer()
                print("已触发烧录")
            elif cmd == "4":
                wifi_sdk.Disconnect()
                print("已断开连接")
            elif cmd == "5":
                s = input("输入6字节十六进制(如: FF 00 01 02 03 04): ").strip()
                parts = s.split()
                if len(parts) != 6:
                    print("格式错误，需6个字节")
                    continue
                try:
                    data = bytes(int(x, 16) for x in parts)
                except Exception:
                    print("解析失败，请使用十六进制字节")
                    continue
                to = input("超时毫秒(默认1000): ").strip()
                timeout = int(to) if to else 1000
                r = wifi_sdk.SendDataWaitACK(data, timeout)
                print("ACK成功" if r == 1 else "ACK超时或失败")
            elif cmd == "q":
                break
            else:
                print("无效指令")
    finally:
        wifi_sdk.Disconnect()
        print("已退出并断开连接")

if __name__ == "__main__":
    main()
