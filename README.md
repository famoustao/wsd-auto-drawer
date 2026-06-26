# WSD Auto Drawer

[![CI](https://github.com/famoustao/wsd-auto-drawer/actions/workflows/ci.yml/badge.svg)](https://github.com/famoustao/wsd-auto-drawer/actions/workflows/ci.yml)

SVG 与 WSD 双向转换工具，基于 EduEditor WStudio7 格式的逆向工程实现。

## 功能特性

- **SVG 转 WSD**：将标准 SVG 矢量图转换为 EduEditor 的 `.wsd` 格式
- **WSD 转 SVG**：将 `.wsd` 文件还原为 SVG 矢量图
- **批量转换**：支持目录级别的批量处理
- **双向无损**：基于逆向分析的精确格式还原

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

### 命令行

```bash
# SVG 转 WSD
python main.py svg2wsd input.svg output.wsd

# WSD 转 SVG
python main.py wsd2svg input.wsd output.svg

# 批量转换
python main.py batch ./svg_dir ./wsd_dir --mode svg2wsd
```

### 作为模块使用

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
├── main.py              # 主程序入口
├── svg_to_wsd.py        # SVG 转 WSD 转换器
├── wsd_to_svg.py        # WSD 转 SVG 转换器
├── tests/
│   └── test_conversion.py  # 单元测试
├── .github/
│   └── workflows/
│       └── ci.yml       # GitHub Actions 自动编译
├── setup.py             # Python 包配置
├── requirements.txt     # 依赖（纯 Python，无外部依赖）
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

## 许可证

MIT License
