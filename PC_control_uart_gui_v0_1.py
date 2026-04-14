import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import serial
import serial.tools.list_ports
from pywinauto import Application

# 常量定义
NUM_CHIPS = 6
BITS_PER_CHIP = 8
TOTAL_BITS = NUM_CHIPS * BITS_PER_CHIP

class UartControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PC 串口控制  v0.1")
        self.root.geometry("900x750")
        
        self.ser = None
        self.is_connected = False
        self.is_programming = False
        self.last_active_time = 0
        
        # UI 变量
        self.bit_vars = [tk.IntVar(value=0) for _ in range(TOTAL_BITS)]
        self.bit_names = [tk.StringVar(value=f"B{i%8}") for i in range(TOTAL_BITS)]
        
        self._setup_ui()
        self._start_port_scan()

    def _setup_ui(self):
        # 1. 连接设置区域
        conn_frame = ttk.LabelFrame(self.root, text="串口连接设置", padding="10")
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(conn_frame, text="串口号:").pack(side="left", padx=5)
        self.port_combo = ttk.Combobox(conn_frame, width=15)
        self.port_combo.pack(side="left", padx=5)
        
        ttk.Label(conn_frame, text="波特率:").pack(side="left", padx=5)
        self.baud_combo = ttk.Combobox(conn_frame, values=["9600", "19200", "38400", "57600", "115200"], width=10)
        self.baud_combo.set("115200")
        self.baud_combo.pack(side="left", padx=5)
        
        self.btn_connect = ttk.Button(conn_frame, text="连接", command=self.toggle_connection)
        self.btn_connect.pack(side="left", padx=10)
        
        self.status_lbl = ttk.Label(conn_frame, text="状态: 未连接", foreground="red")
        self.status_lbl.pack(side="left", padx=10)

        # 2. 芯片控制矩阵
        matrix_frame = ttk.LabelFrame(self.root, text="48路输出控制 (Bit 0-7)", padding="10")
        matrix_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        for chip in range(NUM_CHIPS):
            chip_frame = ttk.Frame(matrix_frame)
            chip_frame.pack(fill="x", pady=2)
            
            ttk.Label(chip_frame, text=f"芯片 {chip+1}:", width=8).pack(side="left")
            
            for bit in range(BITS_PER_CHIP):
                idx = chip * BITS_PER_CHIP + bit
                cb = tk.Checkbutton(chip_frame, textvariable=self.bit_names[idx], variable=self.bit_vars[idx],
                                   command=lambda c=chip, b=bit: self.on_bit_change(c, b))
                cb.pack(side="left", padx=2)
            
            ttk.Button(chip_frame, text="全开", width=5, 
                       command=lambda c=chip: self.set_chip_bits(c, 1)).pack(side="left", padx=5)
            ttk.Button(chip_frame, text="全清", width=5, 
                       command=lambda c=chip: self.set_chip_bits(c, 0)).pack(side="left", padx=2)

        # 3. 操作区域
        action_frame = ttk.Frame(self.root, padding="10")
        action_frame.pack(fill="x", padx=10, pady=5)
        
        self.auto_send_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(action_frame, text="自动发送", variable=self.auto_send_var).pack(side="left", padx=10)
        
        self.auto_program_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(action_frame, text="自动烧录", variable=self.auto_program_var).pack(side="left", padx=10)
        
        ttk.Button(action_frame, text="立即发送数据", command=self.send_data).pack(side="left", padx=10)
        ttk.Button(action_frame, text="全选", command=self.select_all).pack(side="left", padx=5)
        ttk.Button(action_frame, text="全清", command=self.clear_all).pack(side="left", padx=5)
        ttk.Button(action_frame, text="通道重命名", command=self.open_rename_window).pack(side="left", padx=5)

        # 3.5 汉字发送区域
        send_text_frame = ttk.Frame(self.root, padding="10")
        send_text_frame.pack(fill="x", padx=10, pady=0)
        ttk.Label(send_text_frame, text="发送汉字/文本:").pack(side="left", padx=5)
        self.text_to_send = ttk.Entry(send_text_frame)
        self.text_to_send.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(send_text_frame, text="发送(GBK)", command=self.send_custom_text).pack(side="left", padx=5)

        # 4. 日志区域
        log_frame = ttk.LabelFrame(self.root, text="通讯日志", padding="5")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=10)
        self.log_area.pack(fill="both", expand=True)

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_area.see(tk.END)

    def _start_port_scan(self):
        """自动扫描可用串口"""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
        self.root.after(3000, self._start_port_scan) # 每3秒刷新一次列表

    def toggle_connection(self):
        if not self.is_connected:
            self.connect_serial()
        else:
            self.disconnect_serial()

    def connect_serial(self):
        port = self.port_combo.get()
        baud = self.baud_combo.get()
        
        if not port:
            messagebox.showerror("错误", "请选择串口号")
            return
            
        try:
            self.ser = serial.Serial(port, int(baud), timeout=0.1)
            self.is_connected = True
            self.last_active_time = time.time()
            
            self.btn_connect.config(text="断开连接")
            self.status_lbl.config(text=f"状态: 已连接 ({port})", foreground="green")
            self.log(f"成功打开串口 {port}, 波特率 {baud}")
            
            # 启动接收线程
            threading.Thread(target=self._receive_thread, daemon=True).start()
            # 启动看门狗线程
            threading.Thread(target=self._watchdog_thread, daemon=True).start()
            
            self.send_data() # 连接后同步一次状态
            
        except Exception as e:
            self.log(f"串口打开失败: {e}")
            messagebox.showerror("连接失败", str(e))

    def disconnect_serial(self):
        self.is_connected = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.btn_connect.config(text="连接")
        self.status_lbl.config(text="状态: 未连接", foreground="red")
        self.log("串口已关闭")

    def _receive_thread(self):
        """后台接收线程"""
        while self.is_connected and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    self.last_active_time = time.time()
                    
                    if b'\x06' in data:
                        self.root.after(0, lambda: self.log("收到应答: ACK (成功)"))
                    else:
                        hex_str = " ".join([f"{b:02X}" for b in data])
                        try:
                            # 尝试按 GBK 解码（串口嵌入式设备常用编码）
                            text_str = data.decode('gbk').strip()
                            if text_str:
                                self.root.after(0, lambda h=hex_str, t=text_str: self.log(f"收到数据: {h} (文本: {t})"))
                            else:
                                self.root.after(0, lambda h=hex_str: self.log(f"收到数据: {h}"))
                        except:
                            self.root.after(0, lambda h=hex_str: self.log(f"收到数据: {h}"))
                else:
                    time.sleep(0.01)
            except Exception as e:
                if self.is_connected:
                    self.root.after(0, lambda: self.log(f"接收异常: {e}"))
                    self.root.after(0, self.disconnect_serial)
                break

    def _watchdog_thread(self):
        """看门狗线程"""
        while self.is_connected:
            time.sleep(1.0)
            if not self.is_connected: break
            
            diff = time.time() - self.last_active_time
            if diff > 6.0:
                self.root.after(0, lambda: self.log(f"系统提示: 通讯超时 ({int(diff)}s > 6s)"))
                self.root.after(0, self.disconnect_serial)
                break
            if diff > 2.0:
                self.send_data(silent=True)

    def on_bit_change(self, chip_index=None, bit_index=None):
        if self.is_connected and self.auto_send_var.get():
            self.send_data()
        
        if chip_index is not None and bit_index is not None:
            idx = chip_index * BITS_PER_CHIP + bit_index
            if self.bit_vars[idx].get() == 1:
                if not self.auto_program_var.get():
                    return
                if getattr(self, 'is_programming', False):
                    self.log("提示: 烧录中，忽略本次触发")
                    return
                if not self.is_connected:
                    messagebox.showwarning("警告", "串口未连接，无法触发烧录")
                    return
                    
                self.log("提示: 准备烧录，强制同步状态...")
                self.send_data()
                self.is_programming = True
                self.trigger_programmer()

    def set_chip_bits(self, chip_index, value):
        start = chip_index * BITS_PER_CHIP
        for i in range(start, start + BITS_PER_CHIP):
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

    def send_data(self, silent=False):
        if not self.is_connected or not self.ser or not self.ser.is_open:
            return

        try:
            data_bytes = bytearray(NUM_CHIPS)
            for chip in range(NUM_CHIPS):
                byte_val = 0
                for bit in range(BITS_PER_CHIP):
                    idx = chip * BITS_PER_CHIP + bit
                    if self.bit_vars[idx].get():
                        byte_val |= (1 << bit)
                data_bytes[chip] = byte_val

            # 协议包: AA 55 01 [DATA x 6] CS
            cmd = 0x01
            packet = bytearray([0xAA, 0x55, cmd])
            packet.extend(data_bytes)
            
            # 校验和
            total = cmd
            for b in data_bytes:
                total += b
            packet.append(total & 0xFF)
            
            self.ser.write(packet)
            
            if not silent:
                hex_str = " ".join([f"{b:02X}" for b in data_bytes])
                self.log(f"发送串口数据: {hex_str}")
        except Exception as e:
            self.log(f"发送错误: {e}")
            self.disconnect_serial()

    def send_custom_text(self):
        """发送自定义汉字/文本（GBK编码）"""
        if not self.is_connected or not self.ser or not self.ser.is_open:
            messagebox.showwarning("警告", "串口未连接")
            return
        
        text = self.text_to_send.get()
        if not text:
            return
            
        try:
            # 串口嵌入式设备通常使用 GBK 编码汉字
            encoded_data = text.encode('gbk')
            self.ser.write(encoded_data)
            self.log(f"发送文本: {text} (GBK: {encoded_data.hex().upper()})")
        except Exception as e:
            self.log(f"发送文本失败: {e}")

    def open_rename_window(self):
        """打开通道重命名窗口"""
        rename_win = tk.Toplevel(self.root)
        rename_win.title("通道重命名")
        rename_win.geometry("600x500")
        
        canvas = tk.Canvas(rename_win)
        scrollbar = ttk.Scrollbar(rename_win, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for i in range(TOTAL_BITS):
            row = i // 4
            col = i % 4
            f = ttk.Frame(scrollable_frame, padding=5)
            f.grid(row=row, column=col)
            ttk.Label(f, text=f"B{i}:").pack(side="left")
            ttk.Entry(f, textvariable=self.bit_names[i], width=10).pack(side="left")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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
                        popup_found = False
                        for _ in range(5):
                            time.sleep(0.5)
                            try:
                                dialogs = app.windows()
                                for d in dialogs:
                                    if d.handle == dlg.handle:
                                        continue
                                    try:
                                        texts = [c.window_text() for c in d.descendants(control_type="Text")]
                                        full_text = " ".join(texts)
                                        if "未检测到烧录器" in full_text or "连接后重试" in full_text:
                                            self.root.after(0, lambda t=full_text: self.log(f"!!! 警告: 检测到弹窗 !!!\n{t}"))
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
                            return
                        
                        # 4. 抓取日志
                        time.sleep(2) 
                        try:
                            log_found = False
                            try:
                                tab_item = dlg.child_window(title="消息记录", control_type="TabItem")
                                if tab_item.exists():
                                    tab_item.select()
                                    time.sleep(0.5)
                            except:
                                pass

                            edits = dlg.descendants(control_type="Edit") + dlg.descendants(control_type="Document") + dlg.descendants(control_type="Pane")
                            candidate_logs = []
                            for ctrl in edits:
                                try:
                                    text = ctrl.window_text()
                                    if text and len(text.strip()) > 0:
                                        candidate_logs.append(text)
                                except:
                                    pass
                            
                            if candidate_logs:
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

        def _wrapper():
            try:
                time.sleep(0.5)
                _run()
            finally:
                self.is_programming = False

        threading.Thread(target=_wrapper, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = UartControlGUI(root)
    root.mainloop()
