# WSD Auto Drawer

[![CI](https://github.com/famoustao/wsd-auto-drawer/actions/workflows/ci.yml/badge.svg)](https://github.com/famoustao/wsd-auto-drawer/actions/workflows/ci.yml)
[![Build C++](https://github.com/famoustao/wsd-auto-drawer/actions/workflows/build-cpp.yml/badge.svg)](https://github.com/famoustao/wsd-auto-drawer/actions/workflows/build-cpp.yml)

SVG 与 WSD 双向转换工具，基于 EduEditor WStudio7 格式的逆向工程实现。

提供 **Python** 和 **C++ (Qt6 GUI)** 两个版本。

## 功能特性

- **SVG 转 WSD**：将标准 SVG 矢量图转换为 EduEditor 的 `.wsd` 格式
- **WSD 转 SVG**：将 `.wsd` 文件还原为 SVG 矢量图
- **批量转换**：支持目录级别的批量处理
- **双向无损**：基于逆向分析的精确格式还原
- **Qt6 GUI**：C++ 版本提供原生桌面界面，自动编译为 Windows exe

## WSD 格式规范（逆向工程）

通过分析 EduEditor 的二进制 `.wsd` 文件，我们识别出以下结构：

| 字段 | 说明 |
|------|------|
| 文件头 | `WSTUDIO7` (8字节, 偏移1) |
| 对象头 | 41字节固定模板，以 `03 47` 结束 |
| 点数 | 2字节大端序无符号整数 |
| 坐标 | 每点8字节，低16位小端序有符号整数 (X,Y) |
| 颜色 | 4字节ARGB |
| 对象尾 | 2字节结束标记 |

## 安装

```bash
git clone https://github.com/famoustao/wsd-auto-drawer.git
cd wsd-auto-drawer
pip install -e .
```

## 使用方法

### 1. 桌面 GUI (推荐)

```bash
python gui.py
```

功能：
- 可视化文件选择（输入/输出目录）
- 转换模式切换（SVG → WSD / WSD → SVG）
- 实时日志显示
- 进度条动画
- 转换完成后自动打开文件夹

### 2. Web 界面

```bash
pip install flask
python web_ui.py
```

然后访问 http://127.0.0.1:5000

功能：
- 浏览器内拖拽上传
- 一键下载转换结果
- 响应式设计，支持移动端

### 3. 命令行

```bash
# SVG 转 WSD
python main.py svg2wsd input.svg output.wsd

# WSD 转 SVG
python main.py wsd2svg input.wsd output.svg

# 批量转换
python main.py batch ./svg_dir ./wsd_dir --mode svg2wsd
```

### 4. 作为模块使用

```python
from svg_to_wsd import svg_to_wsd
from wsd_to_svg import wsd_to_svg

# SVG -> WSD
svg_to_wsd("input.svg", "output.wsd")

# WSD -> SVG
wsd_to_svg("input.wsd", "output.svg")
```

## 文件结构

```
wsd-auto-drawer/
├── main.py              # 命令行入口
├── gui.py               # 桌面 GUI (tkinter)
├── web_ui.py            # Web 界面 (Flask)
├── svg_to_wsd.py        # SVG 转 WSD 转换器
├── wsd_to_svg.py        # WSD 转 SVG 转换器
├── tests/
│   └── test_conversion.py  # 单元测试
├── .github/
│   └── workflows/
│       └── ci.yml       # GitHub Actions 自动编译
├── setup.py             # Python 包配置
├── requirements.txt     # 依赖
└── README.md            # 本文件
```

## 技术栈

- Python 3.9+
- 纯标准库实现（`struct`, `xml.etree.ElementTree`, `re`）
- 无外部依赖

## 测试

```bash
python -m unittest tests.test_conversion -v
```

## CI/CD

本项目使用 GitHub Actions 自动编译和测试：
- 多版本 Python 测试（3.9, 3.10, 3.11, 3.12）
- 代码风格检查（flake8）
- 单元测试和集成测试
- 自动构建分发包

## C++ 版本 (Qt6 GUI)

提供高性能原生桌面应用，支持 Windows/Linux 自动编译。

### 下载预编译 exe

每次 push 后，GitHub Actions 自动编译 Windows exe 并上传 artifact：
- 进入 [Actions → Build C++ Exe](https://github.com/famoustao/wsd-auto-drawer/actions/workflows/build-cpp.yml)
- 下载最新的 `WSDAutoDrawer-Windows.zip`
- 解压后双击 `WSDAutoDrawer.exe` 即可使用（无需安装 Qt）

### 自行编译

```bash
cd cpp
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release
```

### C++ 版本特性

- **Qt6 Widgets 原生 GUI**：流畅的桌面体验
- **多线程批量转换**：后台 Worker 线程，UI 不卡顿
- **实时进度条**：显示当前处理文件和进度
- **批量日志**：每条转换结果实时显示
- **windeployqt 自动打包**：Windows 版本包含所有 Qt DLL，解压即用

### C++ 技术栈

- C++17
- Qt6 (Core, Gui, Widgets)
- CMake 3.20+
- tinyxml2 (内嵌)

## 文件结构

```
wsd-auto-drawer/
├── main.py              # Python 命令行入口
├── gui.py               # Python 桌面 GUI (tkinter)
├── web_ui.py            # Python Web 界面 (Flask)
├── cpp/                 # C++ 版本 (Qt6)
│   ├── CMakeLists.txt
│   └── src/
│       ├── main.cpp
│       ├── wsd_format.cpp/h
│       ├── wsd_parser.cpp/h
│       ├── wsd_writer.cpp/h
│       ├── svg_parser.cpp/h
│       ├── converter.cpp/h
│       └── gui/
│           ├── mainwindow.cpp/h/ui
│   └── third_party/
│       └── tinyxml2/
├── svg_to_wsd.py
├── wsd_to_svg.py
├── tests/
├── .github/workflows/
│   ├── ci.yml           # Python CI
│   └── build-cpp.yml    # C++ Windows/Linux 自动编译
└── README.md
```

## 许可证

MIT License
