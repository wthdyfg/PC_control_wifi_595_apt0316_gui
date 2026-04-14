import socket
import threading
import time
from pywinauto import Application

class WifiSDK:
    """
    WiFi 控制器 SDK - 剥离了 GUI 的核心逻辑，用于生成 DLL 或供外部调用
    """
    def __init__(self):
        self.sock = None
        self.is_connected = False
        self.is_programming = False
        self.last_active_time = 0
        self.ack_event = threading.Event()  # 用于同步等待下位机回复的事件信号
        self.receive_thread = None
        self.watchdog_thread = None
        self._lock = threading.Lock()       # 线程锁，确保发送数据时的线程安全

    def _log(self, message):
        """简单的日志输出，方便在控制台调试"""
        print(f"[SDK_LOG] {time.strftime('%H:%M:%S')} - {message}")

    def connect(self, ip, port):
        """
        建立 TCP 连接
        :param ip: 从机设备 IP 地址
        :param port: 从机设备 端口号
        :return: (状态码, 消息) 1为成功，0为失败
        """
        self._log(f"尝试连接到 {ip}:{port}...")
        if self.is_connected:
            self._log("已连接，无需重复连接。")
            return 1, "Already connected"
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2.0)  # 设置连接超时为 2 秒
            self.sock.connect((ip, port))
            
            self.is_connected = True
            self.last_active_time = time.time()
            
            # 启动后台接收监控线程：负责持续监听从机回复的数据（如 ACK）
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            self._log("接收线程已启动。")
            
            # 启动应用层看门狗线程：负责监控连接是否超时（心跳检测）
            self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
            self.watchdog_thread.start()
            self._log("看门狗线程已启动。")
            
            self._log("连接成功！")
            return 1, "Connected successfully"
        except Exception as e:
            self.is_connected = False
            self._log(f"连接失败: {e}")
            return 0, str(e)

    def disconnect(self):
        """断开当前 TCP 连接"""
        self._log("尝试断开连接...")
        self.is_connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.sock = None
        self._log("已断开连接。")
        return 1, "Disconnected"

    def send_data(self, data_bytes, silent=False):
        """
        发送原始数据包 (控制 48 路继电器)
        :param data_bytes: bytes 或 bytearray, 长度必须为 6 字节（对应 48 个 Bit）
        :param silent: 是否静默发送（不打印日志），用于心跳包
        :return: (状态码, 消息)
        """
        if not self.is_connected or not self.sock:
            if not silent: # 只有非静默发送才打印日志
                self._log("未连接，无法发送数据。")
            return 0, "Not connected"
        
        if len(data_bytes) != 6:
            if not silent: # 只有非静默发送才打印日志
                self._log(f"数据长度错误: {len(data_bytes)}，必须为 6 字节。")
            return 0, "Data length must be 6 bytes"

        try:
            # 兼容处理：确保 data_bytes 是 Python 的 bytes 类型
            # 解决 C# 传过来的 Byte[] 导致的 "can't set bytearray slice from Byte[]" 错误
            if not isinstance(data_bytes, (bytes, bytearray)):
                try:
                    # 尝试多种转换方式，确保鲁棒性
                    if hasattr(data_bytes, '__iter__'):
                        data_bytes = bytes([int(b) for b in data_bytes])
                    else:
                        # 如果是单个数值或其他情况
                        data_bytes = bytes([int(data_bytes)])
                except Exception as conv_e:
                    if not silent:
                        self._log(f"数据转换失败: {conv_e}")
                    return 0, f"Data conversion failed: {conv_e}"

            if len(data_bytes) != 6:
                if not silent:
                    self._log(f"数据长度错误: {len(data_bytes)}，必须为 6 字节。")
                return 0, "Data length must be 6 bytes"

            # 构建协议包: AA 55 01 [DATA x 6] CS
            head1 = 0xAA
            head2 = 0x55
            cmd = 0x01
            
            packet = bytearray([head1, head2, cmd])
            packet.extend(data_bytes)
            
            # 计算校验和 (CS)
            total = cmd
            for b in data_bytes:
                total += b
            cs = total & 0xFF
            packet.append(cs)
            
            # 使用锁确保 Socket 发送的原子性
            with self._lock:
                if self.sock:
                    self.sock.sendall(packet)
                else:
                    return 0, "Socket closed"
            
            if not silent:
                self._log(f"数据已发送: {packet.hex().upper()}")
            return 1, "Sent"
        except Exception as e:
            # 只有在确实发生连接错误时才断开
            if isinstance(e, (socket.error, BrokenPipeError, ConnectionResetError)):
                self.disconnect()
            
            if not silent:
                self._log(f"发送数据异常: {e}")
            return 0, str(e)

    def send_data_wait_ack(self, data_bytes, timeout=1.0):
        """
        发送数据并同步等待下位机回复确认信号 (ACK: 0x06)
        :param data_bytes: 6 字节控制数据
        :param timeout: 等待超时时间（秒）
        :return: (状态码, 消息)
        """
        self._log(f"调用 SendDataWaitACK，等待 {timeout} 秒...")
        self.ack_event.clear() # 清除之前的信号，准备开始新的等待
        
        success, msg = self.send_data(data_bytes, silent=False) # 外部调用 SendDataWaitACK 默认非静默
        if not success:
            self._log(f"SendDataWaitACK: 发送数据失败 - {msg}")
            return 0, msg
        
        self._log(f"SendDataWaitACK: 等待 ACK 信号...")
        # wait() 会阻塞当前线程，直到后台 _receive_loop 收到 0x06 调用 set() 或超时
        if self.ack_event.wait(timeout):
            self._log("SendDataWaitACK: 收到 ACK 信号！")
            return 1, "ACK received"
        else:
            self._log("SendDataWaitACK: 超时未收到 ACK 信号。")
            return 0, "Timeout waiting for ACK"

    def trigger_programmer(self, timeout=5.0):
        """
        异步触发外部 APT ISP2 烧录程序
        :param timeout: 查找外部窗口的超时时间（秒）
        :return: (状态码, 消息)
        """
        self._log("调用 TriggerProgrammer...")
        if self.is_programming:
            self._log("TriggerProgrammer: 烧录任务正在进行中，忽略本次触发。")
            return 0, "Programming in progress"
        
        def _task():
            self.is_programming = True
            try:
                self._log("TriggerProgrammer: 烧录任务开始。")
                # 延时 0.5s 等待硬件继电器吸合稳定
                time.sleep(0.5)
                
                app = None
                start_time = time.time()
                self._log(f"TriggerProgrammer: 尝试连接 APT ISP2 (超时 {timeout} 秒)...")
                
                # 循环查找 APT ISP2 窗口，支持 uia 和 win32 两种后端
                while time.time() - start_time < timeout:
                    try:
                        app = Application(backend="uia").connect(title_re=".*APT ISP2.*", timeout=0.5)
                        break
                    except:
                        try:
                            app = Application(backend="win32").connect(title_re=".*APT ISP2.*", timeout=0.5)
                            break
                        except:
                            pass
                    time.sleep(0.5)
                
                if not app:
                    self._log("TriggerProgrammer: 未找到 APT ISP2 程序。")
                    return
                
                self._log("TriggerProgrammer: 已连接到 APT ISP2。")
                dlg = app.window(title_re=".*APT ISP2.*")
                
                # 查找并点击“自动编程至芯片”按钮
                btn = dlg.child_window(title="自动编程至芯片", control_type="Button")
                if not btn.exists():
                    # 备选模糊匹配
                    btn = dlg.child_window(title_re=".*自动编程.*", control_type="Button")
                
                if btn.exists():
                    btn.click()
                    self._log("TriggerProgrammer: 成功点击 '自动编程至芯片'。")
                else:
                    self._log("TriggerProgrammer: 未找到 '自动编程至芯片' 按钮。")
            except Exception as e:
                self._log(f"TriggerProgrammer: 烧录任务异常 - {e}")
            finally:
                self.is_programming = False
                self._log("TriggerProgrammer: 烧录任务结束。")

        # 在独立线程中执行自动化操作，避免阻塞主通讯逻辑
        threading.Thread(target=_task, daemon=True).start()
        return 1, "Programmer triggered"

    def get_status(self):
        """获取当前 SDK 状态"""
        return {
            "connected": self.is_connected,
            "programming": self.is_programming,
            "last_active": time.time() - self.last_active_time
        }

    def _receive_loop(self):
        """后台接收线程：持续读取从机数据并更新状态"""
        self._log("接收线程: 启动。")
        while self.is_connected and self.sock:
            try:
                data = self.sock.recv(1024)
                if not data:
                    self._log("接收线程: 收到空数据，连接可能已断开。")
                    self.disconnect()
                    break
                
                # 更新最后活跃时间，重置看门狗计数器
                self.last_active_time = time.time()
                self._log(f"接收线程: 收到数据 - {data.hex().upper()}")
                
                # 核心反馈逻辑：检测到下位机返回的 ACK (0x06)
                if b'\x06' in data:
                    self._log("接收线程: 检测到 ACK (0x06)！设置 ACK 事件。")
                    self.ack_event.set() # 释放事件信号，通知正在等待的 SendDataWaitACK 函数
                
            except socket.timeout:
                continue # 超时是正常的，继续循环接收
            except Exception as e:
                self._log(f"接收线程: 发生错误 - {e}")
                self.disconnect()
                break
        self._log("接收线程: 退出。")

    def _watchdog_loop(self):
        """应用层看门狗：监控心跳超时"""
        self._log("看门狗线程: 启动。")
        while self.is_connected:
            time.sleep(1.0)
            if not self.is_connected: break
            
            now = time.time()
            diff = now - self.last_active_time
            
            # 如果超过 6 秒没有收到任何数据包，判定为异常掉线
            if diff > 6.0:
                self._log(f"看门狗线程: 心跳超时 ({int(diff)}s > 6s)，断开连接。")
                self.disconnect()
                break
            
            # 如果超过 2 秒没收到数据，发送一个全关状态的探测包，触发下位机回复 ACK
            if diff > 2.0 and diff < 6.0:
                self._log(f"看门狗线程: 超过 2 秒未活跃 ({int(diff)}s)，发送探测包。")
                # 发送一个全关状态的探测包，不改变继电器状态，但会触发下位机回复 ACK
                self.send_data(bytes([0x00]*6), silent=True) 
        self._log("看门狗线程: 退出。")

# 导出供外部（如 DLL、C#、C++）调用的全局实例及函数封装
_sdk = WifiSDK()

def Connect(ip, port):
    """供外部调用的连接接口"""
    success, msg = _sdk.connect(ip, port)
    return success

def Disconnect():
    """供外部调用的断开接口"""
    success, msg = _sdk.disconnect()
    return success

def SendData(data_6bytes):
    """
    供外部调用的直接发送接口
    data_6bytes: 6 字节的数据包
    """
    success, msg = _sdk.send_data(data_6bytes, silent=False) # 外部调用 SendData 默认非静默
    return success

def SendDataWaitACK(data_6bytes, timeout_ms):
    """
    供外部调用的带确认发送接口
    timeout_ms: 等待超时（毫秒）
    """
    success, msg = _sdk.send_data_wait_ack(data_6bytes, timeout=timeout_ms/1000.0)
    return success

def TriggerProgrammer():
    """供外部调用的触发烧录接口"""
    success, msg = _sdk.trigger_programmer()
    return success

def GetStatus():
    """供外部调用的状态查询接口 (1: 已连接, 0: 未连接)"""
    return 1 if _sdk.is_connected else 0
