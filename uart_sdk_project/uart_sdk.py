import serial
import threading
import time
import sys
from pywinauto import Application

# UART SDK for C# / Python
# 包含串口连接、数据发送、应答检测、看门狗心跳及外部程序触发逻辑

class UartSDK:
    def __init__(self):
        self.ser = None
        self.is_connected = False
        self.last_active_time = 0
        self.ack_event = threading.Event()
        self.lock = threading.Lock()
        self.is_programming = False
        
        # 默认配置
        self.NUM_CHIPS = 6
        self.BITS_PER_CHIP = 8

    def Connect(self, port, baud=115200):
        """
        连接串口
        :param port: 串口号, 如 "COM3"
        :param baud: 波特率, 默认 115200
        :return: bool 是否连接成功
        """
        try:
            if self.is_connected:
                self.Disconnect()
                
            self.ser = serial.Serial(port, int(baud), timeout=0.1)
            self.is_connected = True
            self.last_active_time = time.time()
            
            # 启动后台线程
            threading.Thread(target=self._receive_thread, daemon=True).start()
            threading.Thread(target=self._watchdog_thread, daemon=True).start()
            
            print(f"SDK: 成功连接串口 {port}")
            return True
        except Exception as e:
            print(f"SDK: 连接失败 - {e}")
            return False

    def Disconnect(self):
        """断开串口连接"""
        self.is_connected = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass
        print("SDK: 串口已关闭")

    def _ensure_bytes(self, data_bytes):
        """
        确保数据是 bytes 类型，处理 C# 传入的 Byte[] (在 Python 中表现为 List 或 Enumerable)
        """
        if isinstance(data_bytes, (bytes, bytearray)):
            return data_bytes
        try:
            # 兼容 C# 的 Byte[] 数组
            return bytes([int(b) for b in data_bytes])
        except Exception as e:
            print(f"SDK: 数据转换失败 - {e}")
            return None

    def SendData(self, data_bytes, silent=False):
        """
        发送原始数据 (协议包: AA 55 01 [DATAx6] CS)
        :param data_bytes: 6字节数组
        :param silent: 是否静默发送（不打印日志，用于心跳）
        :return: bool 是否发送成功
        """
        if not self.is_connected or not self.ser:
            return False

        data_bytes = self._ensure_bytes(data_bytes)
        if data_bytes is None or len(data_bytes) < self.NUM_CHIPS:
            print(f"SDK: 数据长度错误, 需 {self.NUM_CHIPS} 字节")
            return False

        try:
            # 构造协议包
            cmd = 0x01
            packet = bytearray([0xAA, 0x55, cmd])
            packet.extend(data_bytes[:self.NUM_CHIPS])
            
            # 计算校验和
            total = cmd
            for b in data_bytes[:self.NUM_CHIPS]:
                total += b
            packet.append(total & 0xFF)

            with self.lock:
                self.ser.write(packet)
            
            if not silent:
                print(f"SDK: 发送数据 {packet.hex().upper()}")
            return True
        except Exception as e:
            print(f"SDK: 发送异常 - {e}")
            self.Disconnect()
            return False

    def SendDataWaitACK(self, data_bytes, timeout_ms=1000):
        """
        发送数据并等待应答 (ACK = 0x06)
        :param data_bytes: 6字节数组
        :param timeout_ms: 超时毫秒
        :return: int (1: 成功收到ACK, 0: 超时, -1: 发送失败)
        """
        self.ack_event.clear()
        if not self.SendData(data_bytes):
            return -1
        
        # 等待事件被 _receive_thread 触发
        success = self.ack_event.wait(timeout=timeout_ms / 1000.0)
        return 1 if success else 0

    def SendCustomText(self, text):
        """发送自定义汉字文本 (GBK编码)"""
        if not self.is_connected or not self.ser:
            return False
        try:
            encoded = text.encode('gbk')
            with self.lock:
                self.ser.write(encoded)
            print(f"SDK: 发送文本 '{text}'")
            return True
        except Exception as e:
            print(f"SDK: 发送文本失败 - {e}")
            return False

    def _receive_thread(self):
        """后台数据接收线程"""
        while self.is_connected and self.ser:
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    self.last_active_time = time.time()
                    
                    # 检查是否包含 ACK (0x06)
                    if b'\x06' in data:
                        self.ack_event.set()
                    
                    # 打印收到的原始十六进制（调试用）
                    # print(f"SDK: 收到数据 {data.hex().upper()}")
                else:
                    time.sleep(0.01)
            except:
                break

    def _watchdog_thread(self):
        """心跳/看门狗线程: 保持连接活跃"""
        # 获取当前所有位状态（全0）作为心跳包，或者自定义协议
        heartbeat_data = bytes([0]*self.NUM_CHIPS)
        while self.is_connected:
            time.sleep(1.0)
            if not self.is_connected: break
            
            diff = time.time() - self.last_active_time
            if diff > 6.0:
                print(f"SDK: 通讯超时 ({int(diff)}s > 6s)，断开连接")
                self.Disconnect()
                break
            if diff > 2.0:
                # 超过2秒未活动，发送心跳包（静默发送）
                self.SendData(heartbeat_data, silent=True)

    def TriggerProgrammer(self):
        """
        触发外部 APT ISP2 烧录程序
        :return: bool 是否成功启动触发线程
        """
        if self.is_programming:
            print("SDK: 正在烧录中，请勿重复触发")
            return False
            
        def _task():
            self.is_programming = True
            print("SDK: 正在尝试自动化操作外部程序...")
            try:
                # 尝试连接外部程序
                app = None
                for backend in ["uia", "win32"]:
                    try:
                        app = Application(backend=backend).connect(title_re=".*APT ISP2.*", timeout=2.0)
                        break
                    except:
                        continue
                
                if not app:
                    print("SDK: 未找到 APT ISP2 程序窗口")
                    return

                dlg = app.window(title_re=".*APT ISP2.*")
                btn = dlg.child_window(title_re=".*自动编程.*", control_type="Button")
                
                if btn.exists():
                    btn.click()
                    print("SDK: 已点击 '自动编程' 按钮")
                    
                    # 简单弹窗处理
                    time.sleep(1.0)
                    for _ in range(3):
                        try:
                            for d in app.windows():
                                if "未检测到烧录器" in d.window_text() or "确认" in d.window_text():
                                    ok_btn = d.child_window(title="确定", control_type="Button")
                                    if ok_btn.exists():
                                        ok_btn.click()
                                        print("SDK: 已自动关闭弹窗")
                        except:
                            pass
                        time.sleep(0.5)
                else:
                    print("SDK: 未找到烧录按钮控件")
            except Exception as e:
                print(f"SDK: 自动化异常 - {e}")
            finally:
                self.is_programming = False

        threading.Thread(target=_task, daemon=True).start()
        return True

if __name__ == "__main__":
    # 本地测试代码
    sdk = UartSDK()
    # sdk.Connect("COM3") # 请根据实际串口修改
    # time.sleep(10)
    # sdk.Disconnect()
