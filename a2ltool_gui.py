#!/usr/bin/env python3
"""Tkinter GUI wrapper for a2ltool/a2ltool.exe.

This GUI is intended to expose all documented command line options in a single
visual tool and then execute the generated command safely via subprocess.
"""

from __future__ import annotations

import os
import queue
import shlex
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class A2lToolGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("a2ltool GUI")
        self.geometry("1300x900")

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.proc: subprocess.Popen[str] | None = None

        self._build_vars()
        self._build_ui()
        self._poll_log_queue()

    def _build_vars(self) -> None:
        self.exe_var = tk.StringVar(value="a2ltool.exe" if os.name == "nt" else "a2ltool")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.create_var = tk.BooleanVar(value=False)

        self.elf_var = tk.StringVar()
        self.pdb_var = tk.StringVar()

        self.strict_var = tk.BooleanVar(value=False)
        self.verbose_var = tk.IntVar(value=0)
        self.debug_print_var = tk.BooleanVar(value=False)
        self.check_var = tk.BooleanVar(value=False)
        self.cleanup_var = tk.BooleanVar(value=False)
        self.sort_var = tk.BooleanVar(value=False)
        self.ifdata_cleanup_var = tk.BooleanVar(value=False)
        self.show_xcp_var = tk.BooleanVar(value=False)
        self.insert_a2ml_var = tk.BooleanVar(value=False)
        self.merge_includes_var = tk.BooleanVar(value=False)
        self.enable_structures_var = tk.BooleanVar(value=False)
        self.old_arrays_var = tk.BooleanVar(value=False)

        self.merge_pref_var = tk.StringVar(value="BOTH")
        self.a2lversion_var = tk.StringVar()

        self.update_type_var = tk.StringVar(value="")
        self.update_mode_var = tk.StringVar(value="")

        self.target_group_var = tk.StringVar()

        self.from_source_var = tk.StringVar()
        self.extra_args_var = tk.StringVar()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        top = ttk.LabelFrame(root, text="基础")
        top.pack(fill=tk.X, pady=5)

        self._add_file_row(top, 0, "a2ltool 可执行文件", self.exe_var, self._choose_exe)
        self._add_file_row(top, 1, "输入 A2L", self.input_var, self._choose_input)
        self._add_file_row(top, 2, "输出 A2L", self.output_var, self._choose_output, save=True)

        ttk.Checkbutton(top, text="--create（新建A2L而非读取输入）", variable=self.create_var).grid(
            row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5
        )

        notebook = ttk.Notebook(root)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        tab_debug = ttk.Frame(notebook, padding=8)
        tab_merge_update = ttk.Frame(notebook, padding=8)
        tab_insert_remove = ttk.Frame(notebook, padding=8)
        tab_other = ttk.Frame(notebook, padding=8)

        notebook.add(tab_debug, text="调试信息")
        notebook.add(tab_merge_update, text="合并/更新")
        notebook.add(tab_insert_remove, text="插入/删除")
        notebook.add(tab_other, text="其他")

        self._build_debug_tab(tab_debug)
        self._build_merge_update_tab(tab_merge_update)
        self._build_insert_remove_tab(tab_insert_remove)
        self._build_other_tab(tab_other)

        preview_box = ttk.LabelFrame(root, text="命令预览")
        preview_box.pack(fill=tk.BOTH, expand=False, pady=5)
        self.preview_text = tk.Text(preview_box, height=5)
        self.preview_text.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(root)
        btns.pack(fill=tk.X, pady=5)
        ttk.Button(btns, text="生成命令", command=self.update_preview).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="执行", command=self.run_command).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="停止", command=self.stop_command).pack(side=tk.LEFT, padx=4)

        log_box = ttk.LabelFrame(root, text="日志")
        log_box.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = tk.Text(log_box, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.update_preview()

    def _build_debug_tab(self, tab: ttk.Frame) -> None:
        self._add_file_row(tab, 0, "ELF 文件（--elffile）", self.elf_var, self._choose_elf)
        self._add_file_row(tab, 1, "PDB 文件（--pdbfile）", self.pdb_var, self._choose_pdb)

        ttk.Label(tab, text="提示：ELF 与 PDB 二选一。").grid(row=2, column=0, columnspan=3, sticky=tk.W)

    def _build_merge_update_tab(self, tab: ttk.Frame) -> None:
        left = ttk.Frame(tab)
        right = ttk.Frame(tab)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        ttk.Label(left, text="--merge（每行一个A2L）").pack(anchor=tk.W)
        self.merge_text = tk.Text(left, height=8)
        self.merge_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(left, text="--merge-project（每行一个A2L）").pack(anchor=tk.W, pady=(8, 0))
        self.merge_project_text = tk.Text(left, height=8)
        self.merge_project_text.pack(fill=tk.BOTH, expand=True)

        pref_row = ttk.Frame(left)
        pref_row.pack(fill=tk.X, pady=5)
        ttk.Label(pref_row, text="--merge-preference").pack(side=tk.LEFT)
        ttk.Combobox(pref_row, textvariable=self.merge_pref_var, values=["BOTH", "EXISTING", "NEW"], width=12).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(pref_row, text="--merge-includes", variable=self.merge_includes_var, command=self.update_preview).pack(side=tk.LEFT, padx=8)

        ttk.Label(right, text="--update（留空表示不启用）").pack(anchor=tk.W)
        ttk.Combobox(right, textvariable=self.update_type_var, values=["", "FULL", "ADDRESSES"], width=15).pack(anchor=tk.W)

        ttk.Label(right, text="--update-mode（留空表示不启用）").pack(anchor=tk.W, pady=(10, 0))
        ttk.Combobox(right, textvariable=self.update_mode_var, values=["", "DEFAULT", "STRICT", "PRESERVE"], width=15).pack(anchor=tk.W)

        ttk.Label(right, text="--a2lversion").pack(anchor=tk.W, pady=(10, 0))
        ttk.Combobox(right, textvariable=self.a2lversion_var, values=["", "1.5.0", "1.5.1", "1.6.0", "1.6.1", "1.7.0", "1.7.1"], width=15).pack(anchor=tk.W)

    def _build_insert_remove_tab(self, tab: ttk.Frame) -> None:
        paned = ttk.Panedwindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=1)

        ttk.Label(left, text="--characteristic（每行一个VAR）").pack(anchor=tk.W)
        self.char_text = tk.Text(left, height=6)
        self.char_text.pack(fill=tk.BOTH, expand=False)

        ttk.Label(left, text="--characteristic-regex（每行一个REGEX）").pack(anchor=tk.W)
        self.char_regex_text = tk.Text(left, height=4)
        self.char_regex_text.pack(fill=tk.BOTH, expand=False)

        ttk.Label(left, text="--characteristic-section（每行一个SECTION）").pack(anchor=tk.W)
        self.char_section_text = tk.Text(left, height=4)
        self.char_section_text.pack(fill=tk.BOTH, expand=False)

        ttk.Label(left, text="--characteristic-range（每行: 起始 结束）").pack(anchor=tk.W)
        self.char_range_text = tk.Text(left, height=4)
        self.char_range_text.pack(fill=tk.BOTH, expand=False)

        ttk.Label(right, text="--measurement（每行一个VAR）").pack(anchor=tk.W)
        self.meas_text = tk.Text(right, height=6)
        self.meas_text.pack(fill=tk.BOTH, expand=False)

        ttk.Label(right, text="--measurement-regex（每行一个REGEX）").pack(anchor=tk.W)
        self.meas_regex_text = tk.Text(right, height=4)
        self.meas_regex_text.pack(fill=tk.BOTH, expand=False)

        ttk.Label(right, text="--measurement-section（每行一个SECTION）").pack(anchor=tk.W)
        self.meas_section_text = tk.Text(right, height=4)
        self.meas_section_text.pack(fill=tk.BOTH, expand=False)

        ttk.Label(right, text="--measurement-range（每行: 起始 结束）").pack(anchor=tk.W)
        self.meas_range_text = tk.Text(right, height=4)
        self.meas_range_text.pack(fill=tk.BOTH, expand=False)

        bottom = ttk.LabelFrame(tab, text="删除")
        bottom.pack(fill=tk.BOTH, expand=False, pady=8)

        ttk.Label(bottom, text="--remove（每行一个REGEX）").grid(row=0, column=0, sticky=tk.W)
        self.remove_text = tk.Text(bottom, height=4, width=45)
        self.remove_text.grid(row=1, column=0, sticky=tk.NSEW, padx=4, pady=4)

        ttk.Label(bottom, text="--remove-range（每行: 起始 结束）").grid(row=0, column=1, sticky=tk.W)
        self.remove_range_text = tk.Text(bottom, height=4, width=45)
        self.remove_range_text.grid(row=1, column=1, sticky=tk.NSEW, padx=4, pady=4)

        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="--target-group").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.target_group_var, width=30).pack(side=tk.LEFT, padx=6)

    def _build_other_tab(self, tab: ttk.Frame) -> None:
        options = ttk.LabelFrame(tab, text="开关")
        options.pack(fill=tk.X, pady=4)

        flags = [
            ("--strict", self.strict_var),
            ("--check", self.check_var),
            ("--cleanup", self.cleanup_var),
            ("--sort", self.sort_var),
            ("--ifdata-cleanup", self.ifdata_cleanup_var),
            ("--show-xcp", self.show_xcp_var),
            ("--insert-a2ml", self.insert_a2ml_var),
            ("--enable-structures", self.enable_structures_var),
            ("--old-arrays", self.old_arrays_var),
            ("--debug-print", self.debug_print_var),
        ]
        for idx, (label, var) in enumerate(flags):
            ttk.Checkbutton(options, text=label, variable=var, command=self.update_preview).grid(
                row=idx // 3, column=idx % 3, sticky=tk.W, padx=8, pady=4
            )

        vrow = ttk.Frame(tab)
        vrow.pack(fill=tk.X, pady=5)
        ttk.Label(vrow, text="--verbose 次数（0/1/2/3）").pack(side=tk.LEFT)
        ttk.Spinbox(vrow, from_=0, to=3, textvariable=self.verbose_var, width=6).pack(side=tk.LEFT, padx=6)

        ttk.Label(tab, text="--from-source（每行一个文件或通配符）").pack(anchor=tk.W, pady=(8, 0))
        self.from_source_text = tk.Text(tab, height=5)
        self.from_source_text.pack(fill=tk.BOTH, expand=False)

        ttk.Label(tab, text="额外参数（高级，按命令行语法填写）").pack(anchor=tk.W, pady=(8, 0))
        ttk.Entry(tab, textvariable=self.extra_args_var).pack(fill=tk.X)

    def _add_file_row(self, parent: tk.Widget, row: int, label: str, var: tk.StringVar, cb, save: bool = False) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(parent, textvariable=var, width=100).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(parent, text="浏览", command=cb).grid(row=row, column=2, padx=5, pady=5)
        parent.grid_columnconfigure(1, weight=1)

    def _choose_exe(self) -> None:
        p = filedialog.askopenfilename(title="选择 a2ltool 可执行文件")
        if p:
            self.exe_var.set(p)
            self.update_preview()

    def _choose_input(self) -> None:
        p = filedialog.askopenfilename(title="选择输入 A2L", filetypes=[("A2L", "*.a2l"), ("All", "*.*")])
        if p:
            self.input_var.set(p)
            self.update_preview()

    def _choose_output(self) -> None:
        p = filedialog.asksaveasfilename(title="选择输出 A2L", defaultextension=".a2l", filetypes=[("A2L", "*.a2l"), ("All", "*.*")])
        if p:
            self.output_var.set(p)
            self.update_preview()

    def _choose_elf(self) -> None:
        p = filedialog.askopenfilename(title="选择 ELF", filetypes=[("ELF/EXE", "*.elf *.exe"), ("All", "*.*")])
        if p:
            self.elf_var.set(p)
            self.update_preview()

    def _choose_pdb(self) -> None:
        p = filedialog.askopenfilename(title="选择 PDB", filetypes=[("PDB", "*.pdb"), ("All", "*.*")])
        if p:
            self.pdb_var.set(p)
            self.update_preview()

    @staticmethod
    def _split_lines(text: tk.Text) -> list[str]:
        return [x.strip() for x in text.get("1.0", tk.END).splitlines() if x.strip()]

    @staticmethod
    def _pairs_from_lines(lines: list[str], option_name: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for line in lines:
            parts = shlex.split(line)
            if len(parts) != 2:
                raise ValueError(f"{option_name} 每行必须是两个值: {line}")
            out.append((parts[0], parts[1]))
        return out

    def build_command(self) -> list[str]:
        exe = self.exe_var.get().strip() or "a2ltool.exe"
        args: list[str] = [exe]

        if self.create_var.get():
            args.append("--create")
        else:
            inp = self.input_var.get().strip()
            if not inp:
                raise ValueError("未勾选 --create 时，必须提供输入 A2L")
            args.append(inp)

        if self.output_var.get().strip():
            args.extend(["--output", self.output_var.get().strip()])

        elf = self.elf_var.get().strip()
        pdb = self.pdb_var.get().strip()
        if elf and pdb:
            raise ValueError("ELF 与 PDB 只能二选一")
        if elf:
            args.extend(["--elffile", elf])
        elif pdb:
            args.extend(["--pdbfile", pdb])

        # merge/update
        merge_items = self._split_lines(self.merge_text)
        merge_project_items = self._split_lines(self.merge_project_text)
        for item in merge_items:
            args.extend(["--merge", item])
        if merge_items:
            args.extend(["--merge-preference", self.merge_pref_var.get().strip() or "BOTH"])
        for item in merge_project_items:
            args.extend(["--merge-project", item])
        if self.merge_includes_var.get():
            args.append("--merge-includes")

        if self.update_type_var.get().strip():
            args.extend(["--update", self.update_type_var.get().strip()])
        if self.update_mode_var.get().strip():
            args.extend(["--update-mode", self.update_mode_var.get().strip()])

        if self.a2lversion_var.get().strip():
            args.extend(["--a2lversion", self.a2lversion_var.get().strip()])

        # inserts
        for var in self._split_lines(self.char_text):
            args.extend(["--characteristic", var])
        for regex in self._split_lines(self.char_regex_text):
            args.extend(["--characteristic-regex", regex])
        for section in self._split_lines(self.char_section_text):
            args.extend(["--characteristic-section", section])
        for lo, hi in self._pairs_from_lines(self._split_lines(self.char_range_text), "--characteristic-range"):
            args.extend(["--characteristic-range", lo, hi])

        for var in self._split_lines(self.meas_text):
            args.extend(["--measurement", var])
        for regex in self._split_lines(self.meas_regex_text):
            args.extend(["--measurement-regex", regex])
        for section in self._split_lines(self.meas_section_text):
            args.extend(["--measurement-section", section])
        for lo, hi in self._pairs_from_lines(self._split_lines(self.meas_range_text), "--measurement-range"):
            args.extend(["--measurement-range", lo, hi])

        if self.target_group_var.get().strip():
            args.extend(["--target-group", self.target_group_var.get().strip()])

        # remove
        for regex in self._split_lines(self.remove_text):
            args.extend(["--remove", regex])
        for lo, hi in self._pairs_from_lines(self._split_lines(self.remove_range_text), "--remove-range"):
            args.extend(["--remove-range", lo, hi])

        # other flags
        if self.strict_var.get():
            args.append("--strict")
        if self.check_var.get():
            args.append("--check")
        if self.cleanup_var.get():
            args.append("--cleanup")
        if self.sort_var.get():
            args.append("--sort")
        if self.ifdata_cleanup_var.get():
            args.append("--ifdata-cleanup")
        if self.show_xcp_var.get():
            args.append("--show-xcp")
        if self.insert_a2ml_var.get():
            args.append("--insert-a2ml")
        if self.enable_structures_var.get():
            args.append("--enable-structures")
        if self.old_arrays_var.get():
            args.append("--old-arrays")
        if self.debug_print_var.get():
            args.append("--debug-print")

        for _ in range(max(0, int(self.verbose_var.get()))):
            args.append("-v")

        for src in self._split_lines(self.from_source_text):
            args.extend(["--from-source", src])

        extra = self.extra_args_var.get().strip()
        if extra:
            args.extend(shlex.split(extra))

        return args

    def update_preview(self) -> None:
        try:
            cmd = self.build_command()
            rendered = " ".join(shlex.quote(x) for x in cmd)
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert(tk.END, rendered)
        except Exception as exc:
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert(tk.END, f"命令构建错误: {exc}")

    def _append_log(self, msg: str) -> None:
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)

    def _poll_log_queue(self) -> None:
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.after(120, self._poll_log_queue)

    def run_command(self) -> None:
        if self.proc and self.proc.poll() is None:
            messagebox.showwarning("提示", "已有任务正在运行")
            return

        self.update_preview()
        try:
            cmd = self.build_command()
        except Exception as exc:
            messagebox.showerror("命令错误", str(exc))
            return

        self.log_queue.put(f"\n>>> 执行: {' '.join(shlex.quote(x) for x in cmd)}\n")

        def worker() -> None:
            try:
                self.proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except Exception as exc:
                self.log_queue.put(f"启动失败: {exc}\n")
                return

            assert self.proc.stdout is not None
            for line in self.proc.stdout:
                self.log_queue.put(line)

            rc = self.proc.wait()
            self.log_queue.put(f"\n<<< 结束，退出码: {rc}\n")
            self.proc = None

        threading.Thread(target=worker, daemon=True).start()

    def stop_command(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.log_queue.put("\n>>> 已发送终止信号\n")
        else:
            self.log_queue.put("\n>>> 当前无运行中的进程\n")


def main() -> None:
    app = A2lToolGui()
    app.mainloop()


if __name__ == "__main__":
    main()
