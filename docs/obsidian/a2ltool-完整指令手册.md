---
title: a2ltool 完整指令手册
tags: [a2ltool, a2l, calibration, elf, xcp, obsidian]
created: 2026-04-18
---

# a2ltool 完整指令手册

> [!summary]
> 本文档面向 **Obsidian** 使用，按“从零到实战”的方式整理 `a2ltool.exe` 的全部核心参数、约束、组合规则与命令模板。
> 你可以直接复制每个代码块到终端使用。

---

## 1. 快速开始

## 1.1 基础调用形态

```bash
a2ltool.exe [OPTIONS] <input.a2l>
```

或新建文件：

```bash
a2ltool.exe --create [OPTIONS]
```

> [!important]
> `<input.a2l>` 与 `--create` 必须二选一。

## 1.2 最小可用命令

### A) 更新地址与类型（最常见）
```bash
a2ltool.exe input.a2l --elffile app.elf --update --output output.a2l
```

### B) 仅检查一致性
```bash
a2ltool.exe input.a2l --check --strict
```

### C) 新建 A2L 并插入一个标定量
```bash
a2ltool.exe --create --elffile app.elf --characteristic MyParam --output new.a2l
```

---

## 2. 参数总览（按功能分组）

## 2.1 输入/输出与基础行为

- `--create`：创建新 A2L。
- `-o, --output <A2LFILE>`：输出文件路径。
- `-s, --strict`：严格解析。
- `-v, --verbose`：增加日志详细程度（可重复）。
- `-h, --help`：查看帮助。
- `-V, --version`：查看版本。

### 示例
```bash
a2ltool.exe input.a2l -o out.a2l -v
```

---

## 2.2 调试信息输入（ELF/PDB）

- `-e, --elffile <ELFFILE>`：使用 DWARF 调试信息（ELF / MinGW EXE）。
- `--pdbfile <PDBFILE>`：使用 PDB 调试信息（Visual Studio）。

> [!warning]
> `--elffile` 与 `--pdbfile` 一般应二选一。

---

## 2.3 合并类

- `-m, --merge <A2LFILE>`：模块级合并（可多次）。
- `--merge-preference <EXISTING|NEW|BOTH>`：冲突策略。
  - `EXISTING`：保留已有项
  - `NEW`：用新文件项覆盖
  - `BOTH`：两者都保留，必要时重命名（默认）
- `--merge-project <A2LFILE>`：项目级合并（模块总数相加）。
- `-i, --merge-includes`：把 include 文件内容并入主文件。

### 示例
```bash
a2ltool.exe base.a2l --merge x1.a2l --merge x2.a2l --merge-preference BOTH -o merged.a2l
```

---

## 2.4 更新类

- `-u, --update [FULL|ADDRESSES]`
  - `FULL`：更新地址 + 类型信息（默认）
  - `ADDRESSES`：仅更新地址
- `--update-mode [DEFAULT|STRICT|PRESERVE]`
  - `DEFAULT`：未知对象删除、非法设置自动纠正
  - `STRICT`：未知对象/非法设置即报错
  - `PRESERVE`：未知对象保留但地址设为 0

> [!important]
> 使用 `--update` 时需要提供调试信息（`--elffile` 或 `--pdbfile`）。

### 示例
```bash
a2ltool.exe input.a2l --elffile app.elf --update ADDRESSES --update-mode STRICT -o checked.a2l
```

---

## 2.5 插入类（CHARACTERISTIC / MEASUREMENT）

### 2.5.1 CHARACTERISTIC
- `-C, --characteristic <VAR>`：插入单个变量。
- `--characteristic-regex <REGEX>`：按正则批量插入。
- `--characteristic-range <ADDR> <ADDR>`：按地址范围批量插入。
- `--characteristic-section <SECTION>`：按段名批量插入。

### 2.5.2 MEASUREMENT
- `-M, --measurement <VAR>`：插入单个变量。
- `--measurement-regex <REGEX>`：按正则批量插入。
- `--measurement-range <ADDR> <ADDR>`：按地址范围批量插入。
- `--measurement-section <SECTION>`：按段名批量插入。

### 2.5.3 目标分组
- `--target-group <GROUP>`：插入后放入指定 group（无则创建）。

### 示例
```bash
a2ltool.exe input.a2l --elffile app.elf \
  --characteristic-regex "CCP_.*" \
  --measurement-section .bss \
  --target-group Calibration \
  -o inserted.a2l
```

---

## 2.6 删除/清理类

- `-R, --remove <REGEX>`：按名称正则删除。
- `--remove-range <ADDR> <ADDR>`：按地址范围删除。
- `-c, --cleanup`：清理空或无引用项。
- `--ifdata-cleanup`：清理无法按 A2ML 解析的 IF_DATA。
- `--insert-a2ml`：缺失时插入内置 A2ML。

### 示例
```bash
a2ltool.exe input.a2l --remove "^TMP_.*" --remove-range 0x1000 0x1FFF --cleanup -o clean.a2l
```

---

## 2.7 版本与结构控制

- `-a, --a2lversion <VER>`：转换版本（支持 1.5.0 ~ 1.7.1）。
- `-t, --enable-structures`：启用结构体相关对象（需 1.7.1）。
- `--old-arrays`：强制旧数组记法（如 `._2_`）。

### 示例
```bash
a2ltool.exe input.a2l --a2lversion 1.7.1 --enable-structures -o v171.a2l
```

---

## 2.8 其他能力

- `--check`：一致性检查。
- `--sort`：排序全部元素（稳定顺序）。
- `--debug-print`：打印内部调试信息。
- `--show-xcp`：显示 A2L 内 XCP 配置。
- `--from-source <SOURCE_FILE>`：从源码注释批量生成元素（可通配符）。

---

## 3. 参数组合与执行顺序

当你把多个参数放进同一条命令，a2ltool 会按固定顺序执行。建议理解这个顺序，避免结果与预期不一致。

1. 读取输入 A2L 或 `--create`
2. 版本转换 `--a2lversion`
3. 合并 `--merge`
4. 合并 include `--merge-includes`
5. 删除 `--remove*`
6. 从源码生成 `--from-source`
7. 更新 `--update`
8. 插入调试信息对象（`--characteristic*` / `--measurement*`）
9. 清理 `--cleanup`
10. 插入 A2ML `--insert-a2ml`
11. IF_DATA 清理 `--ifdata-cleanup`
12. 排序 `--sort`
13. 检查 `--check`
14. 输出 `--output`

> [!tip]
> 如果你既要“先删后插”，直接把删除和插入都放在同一条命令即可，顺序会自动正确。

---

## 4. RSP 响应文件（强烈推荐）

当命令很长时，把参数写入 `*.rsp` 文件，然后在命令行里通过 `@` 引用。

## 4.1 rsp 文件示例

文件：`release_update.rsp`
```txt
--elffile app.elf
--update FULL
--update-mode STRICT
--cleanup
--sort
--check
--strict
```

调用：
```bash
a2ltool.exe input.a2l @release_update.rsp --output output.a2l
```

## 4.2 书写建议

- 建议一行一个参数（或“参数 + 值”）。
- 地址范围参数仍写成两个值：
  - `--measurement-range 0x1000 0x3000`
- 正则有空格时使用引号。

---

## 5. 场景化命令模板

## 5.1 标定工程日常更新
```bash
a2ltool.exe in.a2l --elffile sw.elf --update --cleanup --sort -o out.a2l
```

## 5.2 CI 严格校验（不容错）
```bash
a2ltool.exe in.a2l --elffile sw.elf --update ADDRESSES --update-mode STRICT --check --strict
```

## 5.3 合并多个供应商文件
```bash
a2ltool.exe base.a2l \
  --merge supplier_a.a2l \
  --merge supplier_b.a2l \
  --merge-preference BOTH \
  --merge-includes \
  -o merged.a2l
```

## 5.4 先清理历史垃圾，再按规则重建对象
```bash
a2ltool.exe in.a2l --elffile sw.elf \
  --remove "^OLD_.*" \
  --cleanup \
  --characteristic-regex "^CCP_.*" \
  --measurement-section .data \
  --target-group NewCal \
  -o rebuilt.a2l
```

---

## 6. 常见报错与排查

- **报错：缺少输入**
  - 原因：未给 `<input.a2l>`，也没加 `--create`。
- **报错：更新失败**
  - 原因：用了 `--update`，但没有 `--elffile/--pdbfile`。
- **结果不含你想要的变量**
  - 先检查 regex / section / 地址范围是否匹配。
- **结构体选项无效**
  - 检查 A2L 版本是否已转到 `1.7.1`。

---

## 7. GUI 与命令行协同建议

如果你使用 GUI（`a2ltool_gui.py`），建议：

1. 在 GUI 里先调好参数并查看“命令预览”；
2. 对于大量变量，使用“批量导入（外部文件）”功能管理标定量和观测量（每行一个变量名，支持忽略空行和 `#` 注释行）；
3. 通过“导出 RSP”按钮落地响应文件，或勾选“执行时优先通过 @rsp 方式调用”；
4. `--merge` / `--merge-project` 建议使用“浏览添加 A2L”按钮管理列表（支持添加、移除选中、清空），避免手工输入路径；
5. 运行时关注状态栏（就绪/运行中/运行成功/运行失败），执行完成后会弹窗提示结果；
6. 把 `.rsp` 纳入版本管理，CI 直接调用。

### 7.1 外部文件格式建议

`characteristics.txt` 示例：

```txt
# 每行一个变量名
CCP_ABS_01
CCP_ABS_02
Engine.Kp[0]
```

`measurements.txt` 示例：

```txt
# 每行一个变量名
SpeedRaw
TorqueRaw
Vehicle.State.Speed
```

---

## 8. 个人笔记区（Obsidian）

- [ ] 我项目的标准更新流程命令
- [ ] 我项目常用 regex 列表
- [ ] 我项目固定 section 白名单
- [ ] CI 失败时的排查 checklist
