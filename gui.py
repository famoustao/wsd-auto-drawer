#!/usr/bin/env python3
"""
WSD Auto Drawer - 桌面 GUI
使用 tkinter 构建跨平台图形界面
支持单文件和批量转换模式
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
        self.root.title("WSD Auto Drawer - SVG/WSD 批量转换器")
        self.root.geometry("750x580")
        self.root.minsize(650, 450)

        self.style = ttk.Style()
        self.style.theme_use('clam')

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
            bg=self.bg_color, fg="#333333"
        )
        self.subtitle_label = tk.Label(
            self.root,
            text="SVG 与 EduEditor WSD 格式批量转换工具",
            font=("Microsoft YaHei", 11),
            bg=self.bg_color, fg="#666666"
        )

        # 模式选择
        self.mode_frame = tk.LabelFrame(
            self.root, text="转换模式", font=("Microsoft YaHei", 11),
            bg=self.bg_color, fg="#333333", padx=10, pady=8
        )
        self.mode_var = tk.StringVar(value="svg2wsd")
        self.svg2wsd_radio = tk.Radiobutton(
            self.mode_frame, text="SVG → WSD", variable=self.mode_var,
            value="svg2wsd", font=("Microsoft YaHei", 10),
            bg=self.bg_color, fg="#333333", selectcolor="white"
        )
        self.wsd2svg_radio = tk.Radiobutton(
            self.mode_frame, text="WSD → SVG", variable=self.mode_var,
            value="wsd2svg", font=("Microsoft YaHei", 10),
            bg=self.bg_color, fg="#333333", selectcolor="white"
        )

        # 批量模式选择
        self.batch_var = tk.BooleanVar(value=False)
        self.batch_check = tk.Checkbutton(
            self.mode_frame, text="批量模式", variable=self.batch_var,
            font=("Microsoft YaHei", 10), bg=self.bg_color, fg="#333333",
            selectcolor="white", command=self._on_batch_toggle
        )

        # 输入区域
        self.input_frame = tk.LabelFrame(
            self.root, text="输入", font=("Microsoft YaHei", 11),
            bg=self.bg_color, fg="#333333", padx=10, pady=8
        )
        self.input_label = tk.Label(
            self.input_frame, text="文件/文件夹:", font=("Microsoft YaHei", 10),
            bg=self.bg_color, fg="#333333", width=12, anchor="w"
        )
        self.input_entry = tk.Entry(
            self.input_frame, font=("Microsoft YaHei", 10), width=40
        )
        self.input_file_btn = tk.Button(
            self.input_frame, text="选择文件", font=("Microsoft YaHei", 9),
            command=self._browse_input_file, bg=self.accent_color, fg="white",
            activebackground="#1976D2", relief=tk.FLAT, cursor="hand2"
        )
        self.input_folder_btn = tk.Button(
            self.input_frame, text="选择文件夹", font=("Microsoft YaHei", 9),
            command=self._browse_input_folder, bg=self.accent_color, fg="white",
            activebackground="#1976D2", relief=tk.FLAT, cursor="hand2"
        )

        # 输出区域
        self.output_frame = tk.LabelFrame(
            self.root, text="输出", font=("Microsoft YaHei", 11),
            bg=self.bg_color, fg="#333333", padx=10, pady=8
        )
        self.output_label = tk.Label(
            self.output_frame, text="输出目录:", font=("Microsoft YaHei", 10),
            bg=self.bg_color, fg="#333333", width=12, anchor="w"
        )
        self.output_entry = tk.Entry(
            self.output_frame, font=("Microsoft YaHei", 10), width=40
        )
        self.output_btn = tk.Button(
            self.output_frame, text="浏览...", font=("Microsoft YaHei", 9),
            command=self._browse_output, bg=self.accent_color, fg="white",
            activebackground="#1976D2", relief=tk.FLAT, cursor="hand2"
        )

        # 进度条（批量模式用确定进度）
        self.progress_frame = tk.Frame(self.root, bg=self.bg_color)
        self.progress = ttk.Progressbar(
            self.progress_frame, orient=tk.HORIZONTAL,
            length=400, mode='determinate'
        )
        self.progress_label = tk.Label(
            self.progress_frame, text="0/0", font=("Microsoft YaHei", 10),
            bg=self.bg_color, fg="#333333", width=8
        )

        # 转换按钮
        self.convert_btn = tk.Button(
            self.root, text="开始转换", font=("Microsoft YaHei", 12, "bold"),
            command=self._start_conversion, bg="#4CAF50", fg="white",
            activebackground="#388E3C", relief=tk.FLAT, cursor="hand2", height=2
        )

        # 日志区域
        self.log_frame = tk.LabelFrame(
            self.root, text="转换日志", font=("Microsoft YaHei", 11),
            bg=self.bg_color, fg="#333333", padx=10, pady=8
        )
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, font=("Consolas", 10), width=75, height=10,
            bg="white", fg="#333333", state=tk.DISABLED
        )

        # 状态栏
        self.status_label = tk.Label(
            self.root, text="就绪", font=("Microsoft YaHei", 9),
            bg=self.bg_color, fg="#666666", anchor="w"
        )

    def _layout_widgets(self):
        """布局组件"""
        self.title_label.pack(pady=(12, 0))
        self.subtitle_label.pack(pady=(0, 10))

        self.mode_frame.pack(fill=tk.X, padx=20, pady=4)
        self.svg2wsd_radio.pack(side=tk.LEFT, padx=15)
        self.wsd2svg_radio.pack(side=tk.LEFT, padx=15)
        self.batch_check.pack(side=tk.RIGHT, padx=15)

        self.input_frame.pack(fill=tk.X, padx=20, pady=4)
        self.input_label.grid(row=0, column=0, sticky="w", pady=4)
        self.input_entry.grid(row=0, column=1, padx=5, pady=4)
        self.input_file_btn.grid(row=0, column=2, padx=3, pady=4)
        self.input_folder_btn.grid(row=0, column=3, padx=3, pady=4)

        self.output_frame.pack(fill=tk.X, padx=20, pady=4)
        self.output_label.grid(row=0, column=0, sticky="w", pady=4)
        self.output_entry.grid(row=0, column=1, padx=5, pady=4)
        self.output_btn.grid(row=0, column=2, padx=5, pady=4)

        self.progress_frame.pack(fill=tk.X, padx=20, pady=(4, 0))
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progress_label.pack(side=tk.RIGHT, padx=(8, 0))

        self.convert_btn.pack(fill=tk.X, padx=20, pady=8)

        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=4)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.status_label.pack(fill=tk.X, padx=20, pady=(0, 8))

    def _on_batch_toggle(self):
        """批量模式切换回调"""
        if self.batch_var.get():
            self.input_label.configure(text="输入文件夹:")
        else:
            self.input_label.configure(text="文件/文件夹:")

    def _log(self, message: str):
        """添加日志"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _browse_input_file(self):
        """选择输入文件（支持多选）"""
        mode = self.mode_var.get()
        ext = "*.svg" if mode == "svg2wsd" else "*.wsd"
        name = "SVG" if mode == "svg2wsd" else "WSD"

        if self.batch_var.get():
            filepaths = filedialog.askopenfilenames(
                title=f"选择 {name} 文件（可多选）",
                filetypes=[(f"{name} 文件", ext), ("所有文件", "*.*")]
            )
            if filepaths:
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, ";".join(filepaths))
        else:
            filepath = filedialog.askopenfilename(
                title=f"选择 {name} 文件",
                filetypes=[(f"{name} 文件", ext), ("所有文件", "*.*")]
            )
            if filepath:
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, filepath)
                if not self.output_entry.get():
                    self.output_entry.delete(0, tk.END)
                    self.output_entry.insert(0, os.path.dirname(filepath))

    def _browse_input_folder(self):
        """选择输入文件夹"""
        directory = filedialog.askdirectory(title="选择输入文件夹")
        if directory:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, directory)
            if not self.output_entry.get():
                self.output_entry.delete(0, tk.END)
                self.output_entry.insert(0, directory + "_output")

    def _browse_output(self):
        """选择输出目录"""
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)

    def _get_input_files(self) -> list:
        """获取所有输入文件路径"""
        raw = self.input_entry.get().strip()
        if not raw:
            return []

        # 多文件用分号分隔
        if ";" in raw:
            return [p.strip() for p in raw.split(";") if os.path.exists(p.strip())]

        # 文件夹
        if os.path.isdir(raw):
            mode = self.mode_var.get()
            ext = ".svg" if mode == "svg2wsd" else ".wsd"
            files = []
            for f in os.listdir(raw):
                if f.lower().endswith(ext):
                    files.append(os.path.join(raw, f))
            return sorted(files)

        # 单文件
        if os.path.isfile(raw):
            return [raw]

        return []

    def _start_conversion(self):
        """开始转换"""
        input_files = self._get_input_files()
        output_dir = self.output_entry.get().strip()
        mode = self.mode_var.get()

        if not input_files:
            messagebox.showerror("错误", "请选择有效的输入文件或文件夹")
            return

        if not output_dir:
            output_dir = os.path.dirname(input_files[0]) or "."

        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建输出目录:\n{e}")
                return

        # 界面状态更新
        self.convert_btn.configure(state=tk.DISABLED)
        self.progress["maximum"] = len(input_files)
        self.progress["value"] = 0
        self.progress_label.configure(text=f"0/{len(input_files)}")
        self.status_label.configure(text=f"准备转换 {len(input_files)} 个文件...", fg=self.accent_color)

        thread = Thread(
            target=self._do_batch_conversion,
            args=(mode, input_files, output_dir)
        )
        thread.daemon = True
        thread.start()

    def _do_batch_conversion(self, mode: str, input_files: list, output_dir: str):
        """执行批量转换"""
        success_count = 0
        fail_count = 0
        self._log(f"\n{'='*50}")
        self._log(f"[批量转换] 共 {len(input_files)} 个文件")
        self._log(f"输出目录: {output_dir}")
        self._log(f"{'='*50}")

        for idx, input_path in enumerate(input_files, 1):
            basename = os.path.splitext(os.path.basename(input_path))[0]
            output_ext = ".wsd" if mode == "svg2wsd" else ".svg"
            output_path = os.path.join(output_dir, f"{basename}{output_ext}")

            self._log(f"[{idx}/{len(input_files)}] {basename}")

            try:
                if mode == "svg2wsd":
                    svg_to_wsd(input_path, output_path)
                else:
                    wsd_to_svg(input_path, output_path)
                success_count += 1
                self._log(f"  ✓ 成功")
            except Exception as e:
                fail_count += 1
                self._log(f"  ✗ 失败: {e}")

            # 更新进度
            self.root.after(0, lambda v=idx, t=len(input_files): self._update_progress(v, t))

        self.root.after(0, lambda s=success_count, f=fail_count, d=output_dir: self._batch_done(s, f, d))

    def _update_progress(self, current: int, total: int):
        """更新进度条"""
        self.progress["value"] = current
        self.progress_label.configure(text=f"{current}/{total}")
        self.status_label.configure(text=f"处理中: {current}/{total}")

    def _batch_done(self, success: int, fail: int, output_dir: str):
        """批量转换完成回调"""
        self.convert_btn.configure(state=tk.NORMAL, text="开始转换")
        total = success + fail
        self._log(f"\n{'='*50}")
        self._log(f"转换完成: 成功 {success} / 失败 {fail} / 总计 {total}")
        self._log(f"{'='*50}\n")

        if fail == 0:
            self.status_label.configure(text=f"全部完成 ({success}/{total})", fg="#4CAF50")
        else:
            self.status_label.configure(text=f"完成: 成功 {success}, 失败 {fail}", fg="#FF9800")

        if messagebox.askyesno(
            "批量转换完成",
            f"处理完成:\n成功: {success}\n失败: {fail}\n总计: {total}\n\n是否打开输出文件夹?"
        ):
            self._open_folder(output_dir)

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
