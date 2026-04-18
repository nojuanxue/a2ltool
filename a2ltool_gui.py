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
import json
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk


class A2lToolGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("a2ltool GUI")
        self.geometry("1300x900")
        self.minsize(980, 700)
        self.tk.call("tk", "scaling", 1.0)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.proc: subprocess.Popen[str] | None = None
        self.status_var = tk.StringVar(value="状态：就绪")
        self.config_path = os.path.join(os.getcwd(), "a2ltool_gui_defaults.json")

        self._build_vars()
        self._configure_ui_style()
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
        self.char_file_var = tk.StringVar()
        self.meas_file_var = tk.StringVar()
        self.use_rsp_var = tk.BooleanVar(value=False)
        self.rsp_file_var = tk.StringVar(value="a2ltool_args.rsp")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True)

        self.main_canvas = tk.Canvas(outer, highlightthickness=0)
        self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.main_scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=self.main_canvas.yview)
        self.main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

        root = ttk.Frame(self.main_canvas, padding=10)
        self._canvas_window_id = self.main_canvas.create_window((0, 0), window=root, anchor="nw")
        self.main_canvas.bind("<Configure>", self._on_canvas_configure)
        root.bind("<Configure>", self._on_frame_configure)
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

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

        self.vertical_pane = tk.PanedWindow(
            root,
            orient=tk.VERTICAL,
            sashwidth=10,
            sashrelief=tk.RAISED,
            showhandle=True,
            opaqueresize=True,
            bd=0,
            relief=tk.FLAT,
        )
        self.vertical_pane.pack(fill=tk.BOTH, expand=True, pady=5)

        preview_box = ttk.LabelFrame(self.vertical_pane, text="命令预览（可拖动分隔条上下调整高度）")
        self.preview_text = tk.Text(preview_box, height=5)
        self.preview_text.pack(fill=tk.BOTH, expand=True)

        lower_area = ttk.Frame(self.vertical_pane)
        self.vertical_pane.add(preview_box, minsize=45, stretch="never")
        self.vertical_pane.add(lower_area, minsize=120, stretch="always")

        btns = ttk.Frame(lower_area)
        btns.pack(fill=tk.X, pady=5)
        ttk.Button(btns, text="生成命令", command=self.update_preview).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="保存为默认配置", command=self.save_as_default_config).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="导出 RSP", command=self.export_rsp).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="执行", command=self.run_command).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="停止", command=self.stop_command).pack(side=tk.LEFT, padx=4)
        ttk.Label(btns, textvariable=self.status_var).pack(side=tk.LEFT, padx=16)

        log_box = ttk.LabelFrame(lower_area, text="日志")
        log_box.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = tk.Text(log_box, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.load_default_config()
        self.update_preview()
        self.after(120, self._set_initial_sash_position)

    def _set_initial_sash_position(self) -> None:
        try:
            self.vertical_pane.sash_place(0, 0, 80)
        except Exception:
            pass

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.main_canvas.itemconfigure(self._canvas_window_id, width=event.width)

    def _on_frame_configure(self, _event: tk.Event) -> None:
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.main_canvas.winfo_exists():
            self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _configure_ui_style(self) -> None:
        default_font = tkfont.nametofont("TkDefaultFont")
        text_font = tkfont.nametofont("TkTextFont")
        heading_font = tkfont.nametofont("TkHeadingFont")

        preferred = ["Microsoft YaHei UI", "Segoe UI", "Noto Sans CJK SC", default_font.cget("family")]
        family = preferred[-1]
        try:
            available = set(tkfont.families())
            for name in preferred:
                if name in available:
                    family = name
                    break
        except Exception:
            pass

        default_font.configure(family=family, size=11)
        text_font.configure(family=family, size=11)
        heading_font.configure(family=family, size=11, weight="bold")

        style = ttk.Style(self)
        style.configure(".", font=default_font)
        style.configure("TButton", padding=(10, 4))
        style.configure("TLabel", padding=(1, 1))
        style.configure("TLabelframe.Label", font=heading_font)

    def _build_debug_tab(self, tab: ttk.Frame) -> None:
        self._add_file_row(tab, 0, "ELF 文件（--elffile）", self.elf_var, self._choose_elf)
        self._add_file_row(tab, 1, "PDB 文件（--pdbfile）", self.pdb_var, self._choose_pdb)

        ttk.Label(tab, text="提示：ELF 与 PDB 二选一。").grid(row=2, column=0, columnspan=3, sticky=tk.W)

    def _build_merge_update_tab(self, tab: ttk.Frame) -> None:
        left = ttk.Frame(tab)
        right = ttk.Frame(tab)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        ttk.Label(left, text="--merge（请用浏览按钮添加）").pack(anchor=tk.W)
        self.merge_list = tk.Listbox(left, height=7)
        self.merge_list.pack(fill=tk.BOTH, expand=True)
        merge_btn_row = ttk.Frame(left)
        merge_btn_row.pack(fill=tk.X, pady=3)
        ttk.Button(merge_btn_row, text="添加 A2L", command=self._add_merge_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(merge_btn_row, text="移除选中", command=self._remove_selected_merge).pack(side=tk.LEFT, padx=2)
        ttk.Button(merge_btn_row, text="清空", command=self._clear_merge).pack(side=tk.LEFT, padx=2)

        ttk.Label(left, text="--merge-project（请用浏览按钮添加）").pack(anchor=tk.W, pady=(8, 0))
        self.merge_project_list = tk.Listbox(left, height=7)
        self.merge_project_list.pack(fill=tk.BOTH, expand=True)
        merge_project_btn_row = ttk.Frame(left)
        merge_project_btn_row.pack(fill=tk.X, pady=3)
        ttk.Button(merge_project_btn_row, text="添加 Project A2L", command=self._add_merge_project_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(merge_project_btn_row, text="移除选中", command=self._remove_selected_merge_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(merge_project_btn_row, text="清空", command=self._clear_merge_project).pack(side=tk.LEFT, padx=2)

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
        import_box = ttk.LabelFrame(tab, text="批量导入（外部文件）")
        import_box.pack(fill=tk.X, pady=(0, 8))
        self._add_file_row(
            import_box,
            0,
            "标定量文件（每行一个变量名）",
            self.char_file_var,
            self._choose_char_file,
        )
        self._add_file_row(
            import_box,
            1,
            "观测量文件（每行一个变量名）",
            self.meas_file_var,
            self._choose_meas_file,
        )
        row_btn = ttk.Frame(import_box)
        row_btn.grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        ttk.Button(row_btn, text="载入标定量（覆盖）", command=lambda: self._load_symbols_to_text(self.char_file_var, self.char_text, append=False)).pack(side=tk.LEFT, padx=3)
        ttk.Button(row_btn, text="载入标定量（追加）", command=lambda: self._load_symbols_to_text(self.char_file_var, self.char_text, append=True)).pack(side=tk.LEFT, padx=3)
        ttk.Button(row_btn, text="载入观测量（覆盖）", command=lambda: self._load_symbols_to_text(self.meas_file_var, self.meas_text, append=False)).pack(side=tk.LEFT, padx=3)
        ttk.Button(row_btn, text="载入观测量（追加）", command=lambda: self._load_symbols_to_text(self.meas_file_var, self.meas_text, append=True)).pack(side=tk.LEFT, padx=3)

        paned = ttk.Panedwindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=1)

        ttk.Label(left, text="--characteristic（每行一个VAR）").pack(anchor=tk.W)
        self.char_text = tk.Text(left, height=6)
        self.char_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(left, text="--characteristic-regex（每行一个REGEX）").pack(anchor=tk.W)
        self.char_regex_text = tk.Text(left, height=4)
        self.char_regex_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(left, text="--characteristic-section（每行一个SECTION）").pack(anchor=tk.W)
        self.char_section_text = tk.Text(left, height=4)
        self.char_section_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(left, text="--characteristic-range（每行: 起始 结束）").pack(anchor=tk.W)
        self.char_range_text = tk.Text(left, height=4)
        self.char_range_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(right, text="--measurement（每行一个VAR）").pack(anchor=tk.W)
        self.meas_text = tk.Text(right, height=6)
        self.meas_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(right, text="--measurement-regex（每行一个REGEX）").pack(anchor=tk.W)
        self.meas_regex_text = tk.Text(right, height=4)
        self.meas_regex_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(right, text="--measurement-section（每行一个SECTION）").pack(anchor=tk.W)
        self.meas_section_text = tk.Text(right, height=4)
        self.meas_section_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(right, text="--measurement-range（每行: 起始 结束）").pack(anchor=tk.W)
        self.meas_range_text = tk.Text(right, height=4)
        self.meas_range_text.pack(fill=tk.BOTH, expand=True)

        bottom = ttk.LabelFrame(tab, text="删除")
        bottom.pack(fill=tk.BOTH, expand=False, pady=8)

        ttk.Label(bottom, text="--remove（每行一个REGEX）").grid(row=0, column=0, sticky=tk.W)
        self.remove_text = tk.Text(bottom, height=4, width=45)
        self.remove_text.grid(row=1, column=0, sticky=tk.NSEW, padx=4, pady=4)

        ttk.Label(bottom, text="--remove-range（每行: 起始 结束）").grid(row=0, column=1, sticky=tk.W)
        self.remove_range_text = tk.Text(bottom, height=4, width=45)
        self.remove_range_text.grid(row=1, column=1, sticky=tk.NSEW, padx=4, pady=4)
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=1)

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
        self.from_source_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(tab, text="额外参数（高级，按命令行语法填写）").pack(anchor=tk.W, pady=(8, 0))
        ttk.Entry(tab, textvariable=self.extra_args_var).pack(fill=tk.X)

        rsp_box = ttk.LabelFrame(tab, text="RSP 响应文件")
        rsp_box.pack(fill=tk.X, pady=8)
        ttk.Checkbutton(
            rsp_box,
            text="执行时优先通过 @rsp 方式调用（先自动导出）",
            variable=self.use_rsp_var,
            command=self.update_preview,
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        self._add_file_row(rsp_box, 1, "RSP 文件路径", self.rsp_file_var, self._choose_rsp_path, save=True)

    def _add_file_row(self, parent: tk.Widget, row: int, label: str, var: tk.StringVar, cb, save: bool = False) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
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

    def _choose_char_file(self) -> None:
        p = filedialog.askopenfilename(title="选择标定量文件", filetypes=[("Text", "*.txt *.lst *.csv"), ("All", "*.*")])
        if p:
            self.char_file_var.set(p)

    def _choose_meas_file(self) -> None:
        p = filedialog.askopenfilename(title="选择观测量文件", filetypes=[("Text", "*.txt *.lst *.csv"), ("All", "*.*")])
        if p:
            self.meas_file_var.set(p)

    def _choose_rsp_path(self) -> None:
        p = filedialog.asksaveasfilename(title="保存 RSP 文件", defaultextension=".rsp", filetypes=[("Response file", "*.rsp"), ("All", "*.*")])
        if p:
            self.rsp_file_var.set(p)
            self.update_preview()

    @staticmethod
    def _split_lines(text: tk.Text) -> list[str]:
        return [x.strip() for x in text.get("1.0", tk.END).splitlines() if x.strip()]

    @staticmethod
    def _listbox_items(listbox: tk.Listbox) -> list[str]:
        return [str(item).strip() for item in listbox.get(0, tk.END) if str(item).strip()]

    @staticmethod
    def _set_text_content(widget: tk.Text, lines: list[str]) -> None:
        widget.delete("1.0", tk.END)
        if lines:
            widget.insert(tk.END, "\n".join(lines) + "\n")

    @staticmethod
    def _pairs_from_lines(lines: list[str], option_name: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for line in lines:
            parts = shlex.split(line)
            if len(parts) != 2:
                raise ValueError(f"{option_name} 每行必须是两个值: {line}")
            out.append((parts[0], parts[1]))
        return out

    @staticmethod
    def _read_symbols_file(path: str) -> list[str]:
        items: list[str] = []
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                items.append(line)
        return items

    def _load_symbols_to_text(self, path_var: tk.StringVar, text_widget: tk.Text, append: bool) -> None:
        path = path_var.get().strip()
        if not path:
            messagebox.showwarning("提示", "请先选择外部文件")
            return
        if not os.path.exists(path):
            messagebox.showerror("错误", f"文件不存在: {path}")
            return
        try:
            symbols = self._read_symbols_file(path)
        except Exception as exc:
            messagebox.showerror("错误", f"读取文件失败: {exc}")
            return

        if not append:
            text_widget.delete("1.0", tk.END)
        if symbols:
            existing = text_widget.get("1.0", tk.END).strip()
            prefix = "\n" if append and existing else ""
            text_widget.insert(tk.END, prefix + "\n".join(symbols) + "\n")
        self.update_preview()
        messagebox.showinfo("完成", f"已加载 {len(symbols)} 条记录")

    @staticmethod
    def _write_rsp_file(path: str, args_without_exe: list[str]) -> None:
        path_obj = os.path.abspath(path)
        parent = os.path.dirname(path_obj)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path_obj, "w", encoding="utf-8") as f:
            for arg in args_without_exe:
                f.write(shlex.quote(arg))
                f.write("\n")

    @staticmethod
    def _remove_selected(listbox: tk.Listbox) -> None:
        selected = listbox.curselection()
        for idx in reversed(selected):
            listbox.delete(idx)

    def _add_merge_file(self) -> None:
        files = filedialog.askopenfilenames(title="选择用于 --merge 的 A2L 文件", filetypes=[("A2L", "*.a2l"), ("All", "*.*")])
        if not files:
            return
        existing = set(self._listbox_items(self.merge_list))
        for file in files:
            if file not in existing:
                self.merge_list.insert(tk.END, file)
        self.update_preview()

    def _add_merge_project_file(self) -> None:
        files = filedialog.askopenfilenames(title="选择用于 --merge-project 的 A2L 文件", filetypes=[("A2L", "*.a2l"), ("All", "*.*")])
        if not files:
            return
        existing = set(self._listbox_items(self.merge_project_list))
        for file in files:
            if file not in existing:
                self.merge_project_list.insert(tk.END, file)
        self.update_preview()

    def _remove_selected_merge(self) -> None:
        self._remove_selected(self.merge_list)
        self.update_preview()

    def _remove_selected_merge_project(self) -> None:
        self._remove_selected(self.merge_project_list)
        self.update_preview()

    def _clear_merge(self) -> None:
        self.merge_list.delete(0, tk.END)
        self.update_preview()

    def _clear_merge_project(self) -> None:
        self.merge_project_list.delete(0, tk.END)
        self.update_preview()

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
        merge_items = self._listbox_items(self.merge_list)
        merge_project_items = self._listbox_items(self.merge_project_list)
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
            if self.use_rsp_var.get():
                rsp_file = self.rsp_file_var.get().strip() or "a2ltool_args.rsp"
                cmd = [cmd[0], f"@{rsp_file}"]
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

        if self.use_rsp_var.get():
            rsp_file = self.rsp_file_var.get().strip() or "a2ltool_args.rsp"
            try:
                self._write_rsp_file(rsp_file, cmd[1:])
            except Exception as exc:
                messagebox.showerror("RSP 导出失败", str(exc))
                return
            cmd = [cmd[0], f"@{rsp_file}"]

        self._set_status("状态：运行中...")
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
            self.after(0, lambda: self._on_process_finished(rc))

        threading.Thread(target=worker, daemon=True).start()

    def stop_command(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self._set_status("状态：停止中...")
            self.log_queue.put("\n>>> 已发送终止信号\n")
        else:
            self.log_queue.put("\n>>> 当前无运行中的进程\n")

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _on_process_finished(self, rc: int) -> None:
        if rc == 0:
            self._set_status("状态：运行成功")
            messagebox.showinfo("运行完成", "运行成功")
        else:
            self._set_status(f"状态：运行失败（退出码 {rc}）")
            messagebox.showwarning("运行结束", f"运行结束，退出码: {rc}")

    def export_rsp(self) -> None:
        try:
            cmd = self.build_command()
        except Exception as exc:
            messagebox.showerror("命令错误", str(exc))
            return

        rsp_file = self.rsp_file_var.get().strip()
        if not rsp_file:
            p = filedialog.asksaveasfilename(
                title="导出 RSP 文件",
                defaultextension=".rsp",
                filetypes=[("Response file", "*.rsp"), ("All", "*.*")],
            )
            if not p:
                return
            rsp_file = p
            self.rsp_file_var.set(p)

        try:
            self._write_rsp_file(rsp_file, cmd[1:])
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
            return
        self.log_queue.put(f"\n>>> 已导出 RSP: {rsp_file}\n")
        self.update_preview()

    def _collect_current_state(self) -> dict:
        return {
            "exe": self.exe_var.get(),
            "input": self.input_var.get(),
            "output": self.output_var.get(),
            "create": bool(self.create_var.get()),
            "elf": self.elf_var.get(),
            "pdb": self.pdb_var.get(),
            "strict": bool(self.strict_var.get()),
            "verbose": int(self.verbose_var.get()),
            "debug_print": bool(self.debug_print_var.get()),
            "check": bool(self.check_var.get()),
            "cleanup": bool(self.cleanup_var.get()),
            "sort": bool(self.sort_var.get()),
            "ifdata_cleanup": bool(self.ifdata_cleanup_var.get()),
            "show_xcp": bool(self.show_xcp_var.get()),
            "insert_a2ml": bool(self.insert_a2ml_var.get()),
            "merge_includes": bool(self.merge_includes_var.get()),
            "enable_structures": bool(self.enable_structures_var.get()),
            "old_arrays": bool(self.old_arrays_var.get()),
            "merge_pref": self.merge_pref_var.get(),
            "a2lversion": self.a2lversion_var.get(),
            "update_type": self.update_type_var.get(),
            "update_mode": self.update_mode_var.get(),
            "target_group": self.target_group_var.get(),
            "extra_args": self.extra_args_var.get(),
            "char_file": self.char_file_var.get(),
            "meas_file": self.meas_file_var.get(),
            "use_rsp": bool(self.use_rsp_var.get()),
            "rsp_file": self.rsp_file_var.get(),
            "merge_list": self._listbox_items(self.merge_list),
            "merge_project_list": self._listbox_items(self.merge_project_list),
            "characteristic_lines": self._split_lines(self.char_text),
            "characteristic_regex_lines": self._split_lines(self.char_regex_text),
            "characteristic_section_lines": self._split_lines(self.char_section_text),
            "characteristic_range_lines": self._split_lines(self.char_range_text),
            "measurement_lines": self._split_lines(self.meas_text),
            "measurement_regex_lines": self._split_lines(self.meas_regex_text),
            "measurement_section_lines": self._split_lines(self.meas_section_text),
            "measurement_range_lines": self._split_lines(self.meas_range_text),
            "remove_lines": self._split_lines(self.remove_text),
            "remove_range_lines": self._split_lines(self.remove_range_text),
            "from_source_lines": self._split_lines(self.from_source_text),
        }

    def _apply_state(self, state: dict) -> None:
        self.exe_var.set(state.get("exe", self.exe_var.get()))
        self.input_var.set(state.get("input", ""))
        self.output_var.set(state.get("output", ""))
        self.create_var.set(bool(state.get("create", False)))
        self.elf_var.set(state.get("elf", ""))
        self.pdb_var.set(state.get("pdb", ""))
        self.strict_var.set(bool(state.get("strict", False)))
        self.verbose_var.set(int(state.get("verbose", 0)))
        self.debug_print_var.set(bool(state.get("debug_print", False)))
        self.check_var.set(bool(state.get("check", False)))
        self.cleanup_var.set(bool(state.get("cleanup", False)))
        self.sort_var.set(bool(state.get("sort", False)))
        self.ifdata_cleanup_var.set(bool(state.get("ifdata_cleanup", False)))
        self.show_xcp_var.set(bool(state.get("show_xcp", False)))
        self.insert_a2ml_var.set(bool(state.get("insert_a2ml", False)))
        self.merge_includes_var.set(bool(state.get("merge_includes", False)))
        self.enable_structures_var.set(bool(state.get("enable_structures", False)))
        self.old_arrays_var.set(bool(state.get("old_arrays", False)))
        self.merge_pref_var.set(state.get("merge_pref", "BOTH"))
        self.a2lversion_var.set(state.get("a2lversion", ""))
        self.update_type_var.set(state.get("update_type", ""))
        self.update_mode_var.set(state.get("update_mode", ""))
        self.target_group_var.set(state.get("target_group", ""))
        self.extra_args_var.set(state.get("extra_args", ""))
        self.char_file_var.set(state.get("char_file", ""))
        self.meas_file_var.set(state.get("meas_file", ""))
        self.use_rsp_var.set(bool(state.get("use_rsp", False)))
        self.rsp_file_var.set(state.get("rsp_file", "a2ltool_args.rsp"))

        self.merge_list.delete(0, tk.END)
        for item in state.get("merge_list", []):
            self.merge_list.insert(tk.END, item)

        self.merge_project_list.delete(0, tk.END)
        for item in state.get("merge_project_list", []):
            self.merge_project_list.insert(tk.END, item)

        self._set_text_content(self.char_text, state.get("characteristic_lines", []))
        self._set_text_content(self.char_regex_text, state.get("characteristic_regex_lines", []))
        self._set_text_content(self.char_section_text, state.get("characteristic_section_lines", []))
        self._set_text_content(self.char_range_text, state.get("characteristic_range_lines", []))
        self._set_text_content(self.meas_text, state.get("measurement_lines", []))
        self._set_text_content(self.meas_regex_text, state.get("measurement_regex_lines", []))
        self._set_text_content(self.meas_section_text, state.get("measurement_section_lines", []))
        self._set_text_content(self.meas_range_text, state.get("measurement_range_lines", []))
        self._set_text_content(self.remove_text, state.get("remove_lines", []))
        self._set_text_content(self.remove_range_text, state.get("remove_range_lines", []))
        self._set_text_content(self.from_source_text, state.get("from_source_lines", []))

    def save_as_default_config(self) -> None:
        try:
            state = self._collect_current_state()
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            messagebox.showerror("保存失败", f"默认配置保存失败: {exc}")
            return
        messagebox.showinfo("保存成功", f"默认配置已保存：\n{self.config_path}")

    def load_default_config(self) -> None:
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            if isinstance(state, dict):
                self._apply_state(state)
                self.log_queue.put(f"\n>>> 已加载默认配置: {self.config_path}\n")
        except Exception as exc:
            self.log_queue.put(f"\n>>> 默认配置加载失败: {exc}\n")


def main() -> None:
    app = A2lToolGui()
    app.mainloop()


if __name__ == "__main__":
    main()
