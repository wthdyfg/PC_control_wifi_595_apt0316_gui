import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import time
from pywinauto import Application

# ================= 配置 =================
DEFAULT_IP = "172.19.181.231"
DEFAULT_PORT = 8080
NUM_CHIPS = 6
BITS_PER_CHIP = 8

class WifiControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("WiFi控制器")
        self.root.geometry("1000x800")
        
        self.sock = None
        self.is_connected = False
        
        # 存储 48 个变量 (0 或 1)
        self.bit_vars = [] 
        
        self._init_ui()
        
    def _init_ui(self):
        # 1. 连接设置区域
        conn_frame = ttk.LabelFrame(self.root, text="连接设置", padding="10")
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(conn_frame, text="从机设备 IP地址:").pack(side="left", padx=5)
        self.ip_entry = ttk.Entry(conn_frame, width=15)
        self.ip_entry.insert(0, DEFAULT_IP)
        self.ip_entry.pack(side="left", padx=5)
        
        ttk.Label(conn_frame, text="端口:").pack(side="left", padx=5)
        self.port_entry = ttk.Entry(conn_frame, width=6)
        self.port_entry.insert(0, str(DEFAULT_PORT))
        self.port_entry.pack(side="left", padx=5)
        
        # 自动搜索按钮
        self.btn_scan = ttk.Button(conn_frame, text="自动搜索", command=self.start_scan)
        self.btn_scan.pack(side="left", padx=5)
        
        self.btn_connect = ttk.Button(conn_frame, text="连接", command=self.toggle_connection)
        self.btn_connect.pack(side="left", padx=10)
        
        self.status_lbl = ttk.Label(conn_frame, text="状态: 未连接", foreground="red")
        self.status_lbl.pack(side="left", padx=10)

        # 2. 控制矩阵区域 (6行 x 8列)
        matrix_frame = ttk.LabelFrame(self.root, text="输出控制矩阵 (48路)", padding="10")
        matrix_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 滚动条支持 (防止屏幕太小)
        # highlightthickness=0 去除画布获取焦点时的黑色边框
        canvas = tk.Canvas(matrix_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(matrix_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 生成 48 个复选框
        for chip in range(NUM_CHIPS):
            chip_frame = ttk.LabelFrame(scrollable_frame, text=f"芯片 #{chip + 1}", padding="5")
            chip_frame.pack(fill="x", pady=5, padx=5)
            
            for bit in range(BITS_PER_CHIP):
                global_index = chip * BITS_PER_CHIP + bit
                var = tk.IntVar()
                self.bit_vars.append(var)
                
                # 按钮样式: 选中为 "On", 未选中为 "Off"
                btn = tk.Checkbutton(
                    chip_frame, 
                    text=f"Bit {bit}", 
                    variable=var,
                    command=lambda c=chip, b=bit: self.on_bit_change(c, b)
                )
                btn.pack(side="left", padx=5)

            # 添加全开/全关控制
            ttk.Separator(chip_frame, orient="vertical").pack(side="left", padx=10, fill="y")
            ttk.Button(chip_frame, text="全开", width=4, 
                      command=lambda c=chip: self.set_chip_bits(c, 1)).pack(side="left", padx=2)
            ttk.Button(chip_frame, text="全关", width=4, 
                      command=lambda c=chip: self.set_chip_bits(c, 0)).pack(side="left", padx=2)

        # 3. 操作区域
        action_frame = ttk.Frame(self.root, padding="10")
        action_frame.pack(fill="x", padx=10, pady=5)
        
        self.auto_send_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(action_frame, text="自动发送", variable=self.auto_send_var).pack(side="left", padx=10)
        
        ttk.Button(action_frame, text="立即发送数据", command=self.send_data).pack(side="left", padx=10)
        ttk.Button(action_frame, text="全选", command=self.select_all).pack(side="left", padx=5)
        ttk.Button(action_frame, text="全清", command=self.clear_all).pack(side="left", padx=5)
        
        # 4. 日志区域
        log_frame = ttk.LabelFrame(self.root, text="通讯日志", padding="5")
        log_frame.pack(fill="x", padx=10, pady=5)
        
        self.log_text = tk.Text(log_frame, height=6, state="disabled")
        self.log_text.pack(fill="x")

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def start_scan(self):
        """启动设备扫描"""
        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")
            return
            
        self.btn_scan.config(state="disabled")
        self.log(f"开始扫描局域网内开放端口 {port} 的设备...")
        threading.Thread(target=self._scan_thread, args=(port,), daemon=True).start()

    def _scan_thread(self, port):
        # 1. 获取本机 IP 所在的网段
        local_ip = self._get_local_ip()
        if not local_ip:
            self.root.after(0, lambda: self.log("无法获取本机IP，扫描失败"))
            self.root.after(0, lambda: self.btn_scan.config(state="normal"))
            return
        
        base_ip = ".".join(local_ip.split(".")[:-1])
        self.root.after(0, lambda: self.log(f"本机IP: {local_ip}, 扫描网段: {base_ip}.1-254"))
        
        found_ip = None
        lock = threading.Lock()
        threads = []
        
        # 扫描函数
        def check_ip(ip):
            nonlocal found_ip
            if found_ip: return
            
            # 尝试连接，增加重试机制和更合理的超时
            for timeout in [0.2, 0.4]: # 第一次 0.2s，失败重试 0.4s
                if found_ip: return
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout) 
                try:
                    result = s.connect_ex((ip, port))
                    if result == 0:
                        with lock:
                            if not found_ip:
                                found_ip = ip
                        s.close()
                        return # 成功找到
                except:
                    pass
                finally:
                    s.close()

        # 启动 254 个线程
        # 优化启动策略：分批启动，避免瞬间拥塞
        active_threads = []
        for i in range(1, 255):
            if found_ip: break
            
            target_ip = f"{base_ip}.{i}"
            if target_ip == local_ip: continue 
            
            t = threading.Thread(target=check_ip, args=(target_ip,))
            t.start()
            active_threads.append(t)
            
            # 每启动 20 个线程等待一下，给网络喘息机会
            if len(active_threads) % 20 == 0:
                time.sleep(0.1)
            
        # 等待结果
        # 最多等待 10 秒
        for _ in range(100): 
            if found_ip: break
            if not any(t.is_alive() for t in active_threads): break
            time.sleep(0.1)
            
        if found_ip:
            self.root.after(0, lambda: self.log(f"找到设备: {found_ip}"))
            self.root.after(0, lambda: self.ip_entry.delete(0, "end"))
            self.root.after(0, lambda: self.ip_entry.insert(0, found_ip))
            # 自动连接
            # self.root.after(0, self.connect) 
        else:
            self.root.after(0, lambda: self.log("未找到设备 (请检查从机设备是否在同一网段且端口正确)"))
            
        self.root.after(0, lambda: self.btn_scan.config(state="normal"))

    def _get_local_ip(self):
        try:
            # 创建一个 UDP socket 连接到外网 IP 来获取本机 IP
            # 不需要实际发送数据
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return socket.gethostbyname(socket.gethostname())

    def toggle_connection(self):
        if not self.is_connected:
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        ip = self.ip_entry.get().strip()
        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")
            return
            
        self.btn_connect.config(state="disabled")
        self.log(f"正在连接到 {ip}:{port}...")
        
        # 使用线程避免界面卡顿
        threading.Thread(target=self._connect_thread, args=(ip, port), daemon=True).start()

    def _connect_thread(self, ip, port):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # 恢复默认的超时设置，不依赖底层 TCP KeepAlive
            self.sock.settimeout(2.0) 
            self.sock.connect((ip, port))
            
            self.is_connected = True
            # 初始化最后活跃时间
            self.last_active_time = time.time()
            
            self.root.after(0, self._update_ui_connected)
            
            # 启动接收/监控线程
            threading.Thread(target=self._receive_thread, daemon=True).start()
            
            # 启动应用层看门狗线程
            threading.Thread(target=self._watchdog_thread, daemon=True).start()
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"连接失败: {e}"))
            self.root.after(0, lambda: self.btn_connect.config(state="normal"))

    def _receive_thread(self):
        """后台接收线程，用于监控连接状态和接收数据"""
        self.root.after(0, lambda: self.log("系统提示: 接收监控线程已启动"))
        while self.is_connected and self.sock:
            try:
                # 阻塞读取，如果对方断开，recv 会返回空字节
                try:
                    data = self.sock.recv(1024)
                except socket.timeout:
                    continue # 超时没数据，继续循环检测状态
                except (OSError, ConnectionResetError, ConnectionAbortedError) as e:
                     # 捕获各种连接异常
                     if self.is_connected:
                         self.root.after(0, lambda e=e: self.log(f"连接异常中断: {e}"))
                         self.root.after(0, lambda: messagebox.showwarning("掉线警告", "连接异常断开！\n(检测到 从机设备 或网络中断)"))
                         self.root.after(0, self.disconnect)
                     break
                
                if not data:
                    # 返回空数据，说明对方关闭了连接
                    if self.is_connected:
                        self.root.after(0, lambda: self.log("检测到服务器已断开连接 (从机设备掉线)"))
                        self.root.after(0, lambda: messagebox.showwarning("掉线警告", "连接已断开！\n(检测到 从机设备 或网络中断)"))
                        self.root.after(0, self.disconnect)
                    break
                
                # 处理接收到的数据 (例如 ACK)
                self.last_active_time = time.time() # 更新最后活跃时间
                
                if b'\x06' in data:
                     self.root.after(0, lambda: self.log("收到 ACK (成功)"))
                else:
                     hex_str = " ".join([f"{b:02X}" for b in data])
                     self.root.after(0, lambda: self.log(f"收到数据: {hex_str}"))
                     
            except Exception as e:
                # 其他未预期的错误
                if self.is_connected: # 只有在认为连接时才报错
                    self.root.after(0, lambda: self.log(f"连接监控错误: {e}"))
                    self.root.after(0, lambda: messagebox.showwarning("掉线警告", f"连接监控错误！\n{e}"))
                    self.root.after(0, self.disconnect)
                break

    def _watchdog_thread(self):
        """应用层看门狗：监控最后一次收到数据的时间"""
        self.root.after(0, lambda: self.log("系统提示: 连接看门狗已启动 (超时阈值: 6秒)"))
        while self.is_connected:
            time.sleep(1.0)
            if not self.is_connected: break
            
            now = time.time()
            diff = now - self.last_active_time
            
            # 策略：
            # 1. 如果超过 2 秒没收到数据，主动发一个包探测一下
            # 2. 如果超过 6 秒没收到数据，判定为掉线
            
            if diff > 6.0:
                self.root.after(0, lambda: self.log(f"系统提示: 心跳超时 ({int(diff)}s > 6s)"))
                self.root.after(0, lambda: messagebox.showwarning("掉线警告", "连接超时！\n(超过6秒未收到设备响应)"))
                self.root.after(0, self.disconnect)
                break
                
            if diff > 2.0:
                # 尝试静默发送当前状态，触发 从机设备 回复 ACK
                self.send_data(silent=True)

    def _update_ui_connected(self):
        self.btn_connect.config(text="断开连接", state="normal")
        self.status_lbl.config(text="状态: 已连接", foreground="green")
        self.log("连接成功！")
        # 连接后立即发送当前状态
        self.send_data()

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.sock = None
        self.is_connected = False
        self.btn_connect.config(text="连接", state="normal")
        self.status_lbl.config(text="状态: 未连接", foreground="red")
        self.log("已断开连接")

    def on_bit_change(self, chip_index=None, bit_index=None):
        if self.is_connected and self.auto_send_var.get():
            self.send_data()
        
        # 自动化控制逻辑：任意芯片的任意 Bit 被选中时，触发烧录
        if chip_index is not None and bit_index is not None:
            # 获取该位的状态
            idx = chip_index * BITS_PER_CHIP + bit_index
            if self.bit_vars[idx].get() == 1:
                self.trigger_programmer()

    def trigger_programmer(self):
        """查找外部 APT ISP2 程序并点击 '自动编程至芯片'"""
        def _run():
            self.log("正在尝试触发外部烧录程序...")
            try:
                # 1. 连接到应用程序 (5秒超时重试)
                app = None
                start_time = time.time()
                while time.time() - start_time < 5.0:
                    try:
                        # 优先尝试 uia
                        app = Application(backend="uia").connect(title_re=".*APT ISP2.*", timeout=0.5)
                        break
                    except:
                        try:
                            # 回退到 win32
                            app = Application(backend="win32").connect(title_re=".*APT ISP2.*", timeout=0.5)
                            break
                        except:
                            pass
                    time.sleep(0.5)
                
                if app is None:
                    self.root.after(0, lambda: self.log("提示: 触发不成功 (5秒内未找到烧录程序)"))
                    return

                # 2. 找到窗口
                dlg = app.window(title_re=".*APT ISP2.*")
                
                # 3. 查找并点击按钮
                # 按钮文本可能是 "自动编程至芯片"
                try:
                    btn = dlg.child_window(title="自动编程至芯片", control_type="Button")
                    if not btn.exists():
                         # 尝试模糊匹配
                         btn = dlg.child_window(title_re=".*自动编程.*", control_type="Button")
                    
                    if btn.exists():
                        btn.click()
                        self.root.after(0, lambda: self.log("成功点击 '自动编程至芯片'"))
                        
                        # --- 弹窗检测逻辑 ---
                        # 点击后，立即检查是否有模态弹窗出现
                        # 尝试多次检测，因为弹窗可能有一点延迟
                        popup_found = False
                        for _ in range(5): # 尝试 3 次，每次间隔 0.5s
                            time.sleep(0.5)
                            try:
                                # 查找属于该应用程序的子窗口/弹窗
                                # 注意：模态弹窗通常没有特定的标题，或者是 "提示"、"错误" 等
                                # 我们可以查找所有子窗口，看是否有文本包含 "未检测到烧录器"
                                
                                # 获取当前活动窗口或查找特定弹窗
                                # 这里的逻辑是：如果有一个新的顶层窗口或对话框出现
                                dialogs = app.windows()
                                for d in dialogs:
                                    # 排除主窗口自己
                                    if d.handle == dlg.handle:
                                        continue
                                    
                                    # 检查弹窗内容
                                    # 通常弹窗里有一个 Static 文本控件
                                    try:
                                        # 获取弹窗内的所有文本
                                        texts = [c.window_text() for c in d.descendants(control_type="Text")]
                                        full_text = " ".join(texts)
                                        
                                        if "未检测到烧录器" in full_text or "连接后重试" in full_text:
                                            self.root.after(0, lambda t=full_text: self.log(f"!!! 警告: 检测到弹窗 !!!\n{t}"))
                                            
                                            # 可选：自动点击 "确定" 关闭它
                                            ok_btn = d.child_window(title="确定", control_type="Button")
                                            if ok_btn.exists():
                                                ok_btn.click()
                                                self.root.after(0, lambda: self.log("已自动关闭警告弹窗"))
                                            
                                            popup_found = True
                                            break
                                    except:
                                        pass
                                
                                if popup_found:
                                    break
                                    
                            except Exception:
                                pass
                        
                        if popup_found:
                            return # 如果有弹窗，说明失败了，不再抓取日志
                        
                        # 4. 抓取日志 (新增功能)
                        # 延时等待烧录完成或日志刷新 (根据实际情况调整时间)
                        time.sleep(2) 
                        
                        try:
                            # 尝试获取日志内容
                            # 策略：直接定位到 TabControl 下面的内容
                            # "消息记录" 通常是一个 TabItem，下面的内容可能是一个 RichEdit 或 Edit
                            log_found = False
                            
                            # 尝试找到 "消息记录" 这个 Tab
                            # 注意：如果 Tab 没有被选中，有时候内容是不可见的。
                            # 这里假设 "消息记录" 是默认选中的，或者我们尝试去点击它
                            try:
                                tab_item = dlg.child_window(title="消息记录", control_type="TabItem")
                                if tab_item.exists():
                                    tab_item.select()
                                    time.sleep(0.5) # 等待切换
                            except:
                                pass # 可能没有 TabItem 结构，直接找 Edit

                            # 获取主窗口下的所有 Edit 控件
                            # 通常日志框是最大的那个文本框，或者位置靠下的
                            edits = dlg.descendants(control_type="Edit") + dlg.descendants(control_type="Document") + dlg.descendants(control_type="Pane")
                            
                            # 过滤出可能是日志的控件
                            # 我们可以通过查找父级是否包含 "消息记录" 或者通过文本特征
                            candidate_logs = []
                            for ctrl in edits:
                                try:
                                    text = ctrl.window_text()
                                    if text and len(text.strip()) > 0:
                                        candidate_logs.append(text)
                                except:
                                    pass
                            
                            # 如果找到多个，我们假设包含 "烧录"、"成功"、"失败" 等关键字的是目标
                            # 或者直接取最长的那一段
                            if candidate_logs:
                                # 按长度排序，取最长的
                                best_log = max(candidate_logs, key=len)
                                self.root.after(0, lambda t=best_log: self.log(f"--- APT ISP2 消息记录 ---\n{t}\n-----------------------"))
                                log_found = True
                            
                            if not log_found:
                                self.root.after(0, lambda: self.log("未抓取到消息记录 (可能为空或未找到控件)"))
                                
                        except Exception as e:
                            self.root.after(0, lambda: self.log(f"抓取日志出错: {e}"))

                    else:
                        self.root.after(0, lambda: self.log("错误: 未找到 '自动编程' 按钮"))
                            
                except Exception as e:
                     self.root.after(0, lambda: self.log(f"按钮操作错误: {e}"))

            except Exception as e:
                self.root.after(0, lambda: self.log(f"自动化错误: {e}"))

        # 在独立线程中运行，避免卡住 GUI
        threading.Thread(target=_run, daemon=True).start()

    def set_chip_bits(self, chip_index, value):
        start_index = chip_index * BITS_PER_CHIP
        end_index = start_index + BITS_PER_CHIP
        for i in range(start_index, end_index):
            self.bit_vars[i].set(value)
        self.on_bit_change()

    def select_all(self):
        for var in self.bit_vars:
            var.set(1)
        self.on_bit_change()

    def clear_all(self):
        for var in self.bit_vars:
            var.set(0)
        self.on_bit_change()

    def calculate_checksum(self, cmd, data):
        total = cmd
        for b in data:
            total += b
        return total & 0xFF

    def send_data(self, silent=False):
        if not self.is_connected or not self.sock:
            # self.log("未连接，无法发送")
            return

        try:
            # 1. 将 48 个位打包成 6 个字节
            data_bytes = bytearray(NUM_CHIPS)
            
            for chip in range(NUM_CHIPS):
                byte_val = 0
                for bit in range(BITS_PER_CHIP):
                    # 获取对应的全局索引
                    idx = chip * BITS_PER_CHIP + bit
                    if self.bit_vars[idx].get():
                        # 注意：这里假设 Bit 0 是最低位 (LSB)
                        byte_val |= (1 << bit)
                data_bytes[chip] = byte_val

            # 2. 构建数据包
            # 协议: AA 55 01 [DATA x 6] CS
            head1 = 0xAA
            head2 = 0x55
            cmd = 0x01
            
            packet = bytearray([head1, head2, cmd])
            packet.extend(data_bytes)
            cs = self.calculate_checksum(cmd, data_bytes)
            packet.append(cs)
            
            # 3. 发送
            self.sock.sendall(packet)
            
            if not silent:
                hex_str = " ".join([f"{b:02X}" for b in data_bytes])
                self.log(f"发送数据: {hex_str}")
            
            # 4. 接收 ACK 由后台线程处理，这里不再阻塞读取

        except Exception as e:
            self.log(f"发送错误: {e}")
            messagebox.showwarning("发送失败", f"数据发送失败，连接似乎已断开。\n错误: {e}")
            self.disconnect()

if __name__ == "__main__":
    root = tk.Tk()
    app = WifiControlGUI(root)
    root.mainloop()
