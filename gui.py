#!/usr/bin/env python3
"""
WSD Auto Drawer - 桌面 GUI
使用 tkinter 构建跨平台图形界面
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from threading import Thread

from svg_to_wsd import svg_to_wsd
from wsd_to_svg import wsd_to_svg


class WSDConverterGUI:
    """WSD 转换器图形界面"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("WSD Auto Drawer - SVG/WSD 转换器")
        self.root.geometry("700x500")
        self.root.minsize(600, 400)
        
        # 主题配置
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # 颜色配置
        self.bg_color = "#f5f5f5"
        self.accent_color = "#2196F3"
        self.root.configure(bg=self.bg_color)
        
        self._create_widgets()
        self._layout_widgets()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 标题
        self.title_label = tk.Label(
            self.root, 
            text="WSD Auto Drawer",
            font=("Microsoft YaHei", 20, "bold"),
            bg=self.bg_color,
            fg="#333333"
        )
        self.subtitle_label = tk.Label(
            self.root,
            text="SVG 与 EduEditor WSD 格式双向转换工具",
            font=("Microsoft YaHei", 11),
            bg=self.bg_color,
            fg="#666666"
        )
        
        # 模式选择
        self.mode_frame = tk.LabelFrame(
            self.root,
            text="转换模式",
            font=("Microsoft YaHei", 11),
            bg=self.bg_color,
            fg="#333333",
            padx=10,
            pady=10
        )
        
        self.mode_var = tk.StringVar(value="svg2wsd")
        self.svg2wsd_radio = tk.Radiobutton(
            self.mode_frame,
            text="SVG → WSD",
            variable=self.mode_var,
            value="svg2wsd",
            font=("Microsoft YaHei", 10),
            bg=self.bg_color,
            fg="#333333",
            selectcolor="white"
        )
        self.wsd2svg_radio = tk.Radiobutton(
            self.mode_frame,
            text="WSD → SVG",
            variable=self.mode_var,
            value="wsd2svg",
            font=("Microsoft YaHei", 10),
            bg=self.bg_color,
            fg="#333333",
            selectcolor="white"
        )
        
        # 文件选择
        self.file_frame = tk.LabelFrame(
            self.root,
            text="文件选择",
            font=("Microsoft YaHei", 11),
            bg=self.bg_color,
            fg="#333333",
            padx=10,
            pady=10
        )
        
        self.input_label = tk.Label(
            self.file_frame,
            text="输入文件:",
            font=("Microsoft YaHei", 10),
            bg=self.bg_color,
            fg="#333333",
            width=10,
            anchor="w"
        )
        self.input_entry = tk.Entry(
            self.file_frame,
            font=("Microsoft YaHei", 10),
            width=45
        )
        self.input_btn = tk.Button(
            self.file_frame,
            text="浏览...",
            font=("Microsoft YaHei", 9),
            command=self._browse_input,
            bg=self.accent_color,
            fg="white",
            activebackground="#1976D2",
            relief=tk.FLAT,
            cursor="hand2"
        )
        
        self.output_label = tk.Label(
            self.file_frame,
            text="输出目录:",
            font=("Microsoft YaHei", 10),
            bg=self.bg_color,
            fg="#333333",
            width=10,
            anchor="w"
        )
        self.output_entry = tk.Entry(
            self.file_frame,
            font=("Microsoft YaHei", 10),
            width=45
        )
        self.output_btn = tk.Button(
            self.file_frame,
            text="浏览...",
            font=("Microsoft YaHei", 9),
            command=self._browse_output,
            bg=self.accent_color,
            fg="white",
            activebackground="#1976D2",
            relief=tk.FLAT,
            cursor="hand2"
        )
        
        # 转换按钮
        self.convert_btn = tk.Button(
            self.root,
            text="开始转换",
            font=("Microsoft YaHei", 12, "bold"),
            command=self._start_conversion,
            bg="#4CAF50",
            fg="white",
            activebackground="#388E3C",
            relief=tk.FLAT,
            cursor="hand2",
            height=2
        )
        
        # 日志区域
        self.log_frame = tk.LabelFrame(
            self.root,
            text="转换日志",
            font=("Microsoft YaHei", 11),
            bg=self.bg_color,
            fg="#333333",
            padx=10,
            pady=10
        )
        
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame,
            font=("Consolas", 10),
            width=70,
            height=10,
            bg="white",
            fg="#333333",
            state=tk.DISABLED
        )
        
        # 进度条
        self.progress = ttk.Progressbar(
            self.root,
            orient=tk.HORIZONTAL,
            length=300,
            mode='indeterminate'
        )
        
        # 状态栏
        self.status_label = tk.Label(
            self.root,
            text="就绪",
            font=("Microsoft YaHei", 9),
            bg=self.bg_color,
            fg="#666666",
            anchor="w"
        )
    
    def _layout_widgets(self):
        """布局组件"""
        # 标题
        self.title_label.pack(pady=(15, 0))
        self.subtitle_label.pack(pady=(0, 15))
        
        # 模式选择
        self.mode_frame.pack(fill=tk.X, padx=20, pady=5)
        self.svg2wsd_radio.pack(side=tk.LEFT, padx=20)
        self.wsd2svg_radio.pack(side=tk.LEFT, padx=20)
        
        # 文件选择
        self.file_frame.pack(fill=tk.X, padx=20, pady=5)
        self.input_label.grid(row=0, column=0, sticky="w", pady=5)
        self.input_entry.grid(row=0, column=1, padx=5, pady=5)
        self.input_btn.grid(row=0, column=2, padx=5, pady=5)
        
        self.output_label.grid(row=1, column=0, sticky="w", pady=5)
        self.output_entry.grid(row=1, column=1, padx=5, pady=5)
        self.output_btn.grid(row=1, column=2, padx=5, pady=5)
        
        # 转换按钮
        self.convert_btn.pack(fill=tk.X, padx=20, pady=10)
        
        # 进度条
        self.progress.pack(fill=tk.X, padx=20, pady=5)
        
        # 日志
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status_label.pack(fill=tk.X, padx=20, pady=(0, 10))
    
    def _log(self, message: str):
        """添加日志"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
    
    def _browse_input(self):
        """选择输入文件"""
        mode = self.mode_var.get()
        if mode == "svg2wsd":
            filepath = filedialog.askopenfilename(
                title="选择 SVG 文件",
                filetypes=[("SVG 文件", "*.svg"), ("所有文件", "*.*")]
            )
        else:
            filepath = filedialog.askopenfilename(
                title="选择 WSD 文件",
                filetypes=[("WSD 文件", "*.wsd"), ("所有文件", "*.*")]
            )
        
        if filepath:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, filepath)
            
            # 自动设置输出目录
            if not self.output_entry.get():
                self.output_entry.delete(0, tk.END)
                self.output_entry.insert(0, os.path.dirname(filepath))
    
    def _browse_output(self):
        """选择输出目录"""
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)
    
    def _start_conversion(self):
        """开始转换"""
        input_path = self.input_entry.get().strip()
        output_dir = self.output_entry.get().strip()
        mode = self.mode_var.get()
        
        # 验证输入
        if not input_path:
            messagebox.showerror("错误", "请选择输入文件")
            return
        
        if not os.path.exists(input_path):
            messagebox.showerror("错误", f"输入文件不存在:\n{input_path}")
            return
        
        if not output_dir:
            output_dir = os.path.dirname(input_path) or "."
        
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建输出目录:\n{e}")
                return
        
        # 生成输出文件名
        basename = os.path.splitext(os.path.basename(input_path))[0]
        if mode == "svg2wsd":
            output_path = os.path.join(output_dir, f"{basename}.wsd")
        else:
            output_path = os.path.join(output_dir, f"{basename}.svg")
        
        # 在后台线程中执行转换
        self.convert_btn.configure(state=tk.DISABLED, text="转换中...")
        self.progress.start()
        self.status_label.configure(text="正在转换...", fg=self.accent_color)
        
        thread = Thread(
            target=self._do_conversion,
            args=(mode, input_path, output_path)
        )
        thread.daemon = True
        thread.start()
    
    def _do_conversion(self, mode: str, input_path: str, output_path: str):
        """执行转换"""
        try:
            self._log(f"[{mode}] 开始转换")
            self._log(f"输入: {input_path}")
            self._log(f"输出: {output_path}")
            
            if mode == "svg2wsd":
                svg_to_wsd(input_path, output_path)
            else:
                wsd_to_svg(input_path, output_path)
            
            self._log("转换完成!")
            
            self.root.after(0, lambda: self._conversion_done(True, output_path))
        
        except Exception as e:
            self._log(f"错误: {str(e)}")
            self.root.after(0, lambda: self._conversion_done(False, str(e)))
    
    def _conversion_done(self, success: bool, message: str):
        """转换完成回调"""
        self.progress.stop()
        self.convert_btn.configure(state=tk.NORMAL, text="开始转换")
        
        if success:
            self.status_label.configure(text="转换完成", fg="#4CAF50")
            if messagebox.askyesno(
                "转换完成",
                f"文件已保存到:\n{message}\n\n是否打开所在文件夹?"
            ):
                self._open_folder(os.path.dirname(message))
        else:
            self.status_label.configure(text="转换失败", fg="#F44336")
            messagebox.showerror("转换失败", f"发生错误:\n{message}")
    
    def _open_folder(self, path: str):
        """打开文件夹"""
        import platform
        import subprocess
        
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception:
            pass


def main():
    root = tk.Tk()
    app = WSDConverterGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
