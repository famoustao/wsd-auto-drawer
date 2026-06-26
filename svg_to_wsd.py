#!/usr/bin/env python3
"""
SVG to WSD Converter (Template Mode)
将 SVG 矢量图通过模板替换方式转换为 EduEditor WStudio7 (.wsd) 格式

核心原理：
- EduEditor 的 WSD 文件结构非常复杂，包含字体表、元数据对象、变体头对象等
- 从零生成的文件无法被 EduEditor 打开（显示"需要密码"或"打开失败"）
- 唯一可行方案：基于已有的可打开 WSD 文件作为模板，仅替换矢量坐标数据

使用方式：
  python svg_to_wsd.py <template.wsd> <input.svg> <output.wsd>

  template.wsd - 一个能被 EduEditor 正常打开的 WSD 文件（模板）
  input.svg   - 要转换的 SVG 矢量图
  output.wsd  - 输出的 WSD 文件
"""

import struct
import re
import math
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class WSDObject:
    """WSD 矢量对象"""
    points: List[Tuple[int, int]]
    color: Tuple[int, int, int, int] = (0, 0, 0, 255)
    is_closed: bool = False


# ============================================================
#  已验证的逆向工程常量 - WSD 记录表格式
# ============================================================

# 记录表标记: 0f 33 ff 00 07（5字节），位于文件尾部
RECORD_MARKER = bytes([0x0f, 0x33, 0xff, 0x00, 0x07])
# 字段标记: 04 ff ff（3字节），紧随记录标记之后
FIELD_MARKER = bytes([0x04, 0xff, 0xff])

# 颜色索引映射表（已验证）
COLOR_INDEX_MAP = {
    'red':    bytes([0x00, 0x00, 0xff, 0xff]),
    'green':  bytes([0x71, 0xb3, 0x3c, 0xff]),
    'blue':   bytes([0xf0, 0xb0, 0x00, 0xff]),
    'black':  bytes([0x01, 0xff, 0x00, 0x00]),
    'white':  bytes([0x02, 0xff, 0x00, 0x00]),
}
# 反向映射：4字节颜色索引 -> 颜色名
COLOR_INDEX_REVERSE = {v: k for k, v in COLOR_INDEX_MAP.items()}

# 记录表结构中各字段相对于标记的偏移量
COLOR_OFFSET     = 8    # 颜色索引: marker+8，4字节
PADDING_OFFSET   = 12   # 填充: marker+12，4字节 (00 00 00 00)
LINEWIDTH_OFFSET = 16   # 线宽: marker+16，uint32 LE (毫米 * 400)
COORD_DATA_START = 32   # 坐标数据起始: marker+32


class WSDTemplateParser:
    """WSD 模板文件解析器 - 提取矢量对象的坐标区域信息"""

    MARKER_B = b'\x64\x0f\x33\xff'  # 标准矢量对象标识

    def __init__(self, template_path: str):
        self.template_path = template_path
        with open(template_path, 'rb') as f:
            self.data = bytearray(f.read())
        self.objects = []  # [(coord_offset, coord_size, point_count), ...]

    def parse(self):
        """解析模板文件，定位所有矢量对象的坐标区域"""
        data = self.data
        self.objects = []

        i = 0
        while i < len(data) - 50:
            if data[i] == 0x01 and data[i + 1] == 0xff:
                if self.MARKER_B in bytes(data[i:i + 50]):
                    # 找到对象头，搜索 03 47 结束标记
                    hdr_end = -1
                    for j in range(min(60, len(data) - i - 2)):
                        if data[i + j] == 0x03 and data[i + j + 1] == 0x47:
                            hdr_end = i + j
                            break

                    if hdr_end < 0:
                        i += 1
                        continue

                    # 点数 (大端序 uint16)
                    point_count = struct.unpack('>H', data[hdr_end + 2:hdr_end + 4])[0]
                    if point_count == 0 or point_count > 10000:
                        i += 1
                        continue

                    # 坐标区域偏移和大小
                    coord_offset = hdr_end + 5  # +2 count, +1 padding
                    coord_size = point_count * 8  # 每点8字节

                    if coord_offset + coord_size > len(data):
                        i += 1
                        continue

                    self.objects.append({
                        'obj_start': i,
                        'coord_offset': coord_offset,
                        'coord_size': coord_size,
                        'point_count': point_count,
                    })
            i += 1

        return self.objects

    def get_total_points(self):
        """获取模板中所有对象的总点数"""
        return sum(obj['point_count'] for obj in self.objects)

    def get_object_count(self):
        """获取模板中矢量对象数量"""
        return len(self.objects)

    def replace_coordinates(self, new_coords: List[Tuple[int, int]], output_path: str):
        """
        用新的坐标数据替换模板中的矢量坐标

        策略：将 new_coords 中的点按比例分配到模板的各个对象中，
        每个对象的新点数必须等于模板中该对象的原始点数（通过重采样实现）。
        """
        # 构建点分配方案
        total_new = len(new_coords)
        total_template = self.get_total_points()

        if total_new == 0:
            print("错误: 没有新的坐标数据")
            return False

        if len(self.objects) == 0:
            print("错误: 模板中没有矢量对象")
            return False

        # 将新坐标按比例分配到各对象
        result_data = bytearray(self.data)  # 复制原始数据
        coord_idx = 0
        replaced = 0

        for obj in self.objects:
            count = obj['point_count']
            offset = obj['coord_offset']
            size = obj['coord_size']

            # 从 new_coords 中取 count 个点
            if coord_idx + count > total_new:
                # 新坐标不够，用最后一个点填充
                remaining = total_new - coord_idx
                if remaining <= 0:
                    remaining = 1
                points_to_use = new_coords[coord_idx:coord_idx + remaining]
                # 重复最后一个点
                while len(points_to_use) < count:
                    points_to_use.append(points_to_use[-1])
            else:
                points_to_use = new_coords[coord_idx:coord_idx + count]

            coord_idx += count

            # 将坐标写入模板
            for j, (x, y) in enumerate(points_to_use):
                pos = offset + j * 8
                # X 坐标 (低16位小端序)
                x_clamped = max(-32768, min(32767, int(x)))
                y_clamped = max(-32768, min(32767, int(y)))
                result_data[pos:pos + 2] = struct.pack('<h', x_clamped)
                result_data[pos + 2:pos + 4] = b'\x00\x00'
                # Y 坐标 (低16位小端序)
                result_data[pos + 4:pos + 6] = struct.pack('<h', y_clamped)
                result_data[pos + 6:pos + 8] = b'\x00\x00'

            replaced += 1

        # 写入输出文件
        with open(output_path, 'wb') as f:
            f.write(result_data)

        print(f"成功替换 {replaced}/{len(self.objects)} 个对象的坐标")
        print(f"  模板总点数: {total_template}")
        print(f"  新坐标总数: {total_new}")
        print(f"  输出文件: {output_path}")
        return True


class SVGParser:
    """SVG 路径解析器"""

    def __init__(self, svg_path: str):
        self.svg_path = svg_path
        self.paths: List[List[Tuple[float, float]]] = []
        self.colors: List[Tuple[int, int, int, int]] = []

    def parse(self) -> List[WSDObject]:
        """解析 SVG 文件"""
        tree = ET.parse(self.svg_path)
        root = tree.getroot()

        ns = {'svg': 'http://www.w3.org/2000/svg'}
        objects = []

        for path_elem in root.findall('.//svg:path', ns):
            d = path_elem.get('d', '')
            if not d:
                continue

            points = self._parse_path_data(d)
            if len(points) < 2:
                continue

            stroke = path_elem.get('stroke', '#000000')
            fill = path_elem.get('fill', 'none')
            color = self._parse_color(stroke)
            is_closed = fill != 'none' or d.strip().endswith('Z') or d.strip().endswith('z')

            objects.append(WSDObject(
                points=self._quantize_points(points),
                color=color,
                is_closed=is_closed
            ))

        if not objects:
            for path_elem in root.findall('.//path'):
                d = path_elem.get('d', '')
                if not d:
                    continue

                points = self._parse_path_data(d)
                if len(points) < 2:
                    continue

                stroke = path_elem.get('stroke', '#000000')
                color = self._parse_color(stroke)
                fill = path_elem.get('fill', 'none')
                is_closed = fill != 'none' or d.strip().endswith('Z') or d.strip().endswith('z')

                objects.append(WSDObject(
                    points=self._quantize_points(points),
                    color=color,
                    is_closed=is_closed
                ))

        return objects

    def _parse_path_data(self, d: str) -> List[Tuple[float, float]]:
        """解析 SVG path 的 d 属性"""
        points = []
        d = d.replace(',', ' ')
        tokens = re.findall(r'([MmLlHhVvCcSsQqTtAaZz])|(-?\d+\.?\d*)', d)

        current_cmd = None
        current_pos = (0.0, 0.0)
        start_pos = (0.0, 0.0)
        i = 0

        while i < len(tokens):
            token = tokens[i]

            if token[0]:
                current_cmd = token[0]
                i += 1

                if current_cmd in 'Mm':
                    x = float(tokens[i][1])
                    y = float(tokens[i + 1][1])
                    i += 2
                    if current_cmd == 'm':
                        x += current_pos[0]
                        y += current_pos[1]
                    current_pos = (x, y)
                    start_pos = current_pos
                    points.append(current_pos)
                    while i < len(tokens) and not tokens[i][0]:
                        x = float(tokens[i][1])
                        y = float(tokens[i + 1][1])
                        i += 2
                        if current_cmd == 'm':
                            x += current_pos[0]
                            y += current_pos[1]
                        current_pos = (x, y)
                        points.append(current_pos)

                elif current_cmd in 'Ll':
                    x = float(tokens[i][1])
                    y = float(tokens[i + 1][1])
                    i += 2
                    if current_cmd == 'l':
                        x += current_pos[0]
                        y += current_pos[1]
                    current_pos = (x, y)
                    points.append(current_pos)
                    while i < len(tokens) and not tokens[i][0]:
                        x = float(tokens[i][1])
                        y = float(tokens[i + 1][1])
                        i += 2
                        if current_cmd == 'l':
                            x += current_pos[0]
                            y += current_pos[1]
                        current_pos = (x, y)
                        points.append(current_pos)

                elif current_cmd == 'H':
                    x = float(tokens[i][1])
                    i += 1
                    current_pos = (x, current_pos[1])
                    points.append(current_pos)

                elif current_cmd == 'h':
                    dx = float(tokens[i][1])
                    i += 1
                    current_pos = (current_pos[0] + dx, current_pos[1])
                    points.append(current_pos)

                elif current_cmd == 'V':
                    y = float(tokens[i][1])
                    i += 1
                    current_pos = (current_pos[0], y)
                    points.append(current_pos)

                elif current_cmd == 'v':
                    dy = float(tokens[i][1])
                    i += 1
                    current_pos = (current_pos[0], current_pos[1] + dy)
                    points.append(current_pos)

                elif current_cmd in 'Zz':
                    if points and start_pos != points[-1]:
                        points.append(start_pos)
                    current_pos = start_pos

                elif current_cmd in 'Cc':
                    if i + 5 < len(tokens):
                        x1, y1 = float(tokens[i][1]), float(tokens[i + 1][1])
                        x2, y2 = float(tokens[i + 2][1]), float(tokens[i + 3][1])
                        x, y = float(tokens[i + 4][1]), float(tokens[i + 5][1])
                        i += 6
                        if current_cmd == 'c':
                            x1 += current_pos[0]; y1 += current_pos[1]
                            x2 += current_pos[0]; y2 += current_pos[1]
                            x += current_pos[0]; y += current_pos[1]
                        curve_pts = self._sample_cubic_bezier(
                            current_pos, (x1, y1), (x2, y2), (x, y), steps=8
                        )
                        points.extend(curve_pts[1:])
                        current_pos = (x, y)

                elif current_cmd in 'Qq':
                    if i + 3 < len(tokens):
                        x1, y1 = float(tokens[i][1]), float(tokens[i + 1][1])
                        x, y = float(tokens[i + 2][1]), float(tokens[i + 3][1])
                        i += 4
                        if current_cmd == 'q':
                            x1 += current_pos[0]; y1 += current_pos[1]
                            x += current_pos[0]; y += current_pos[1]
                        curve_pts = self._sample_quadratic_bezier(
                            current_pos, (x1, y1), (x, y), steps=6
                        )
                        points.extend(curve_pts[1:])
                        current_pos = (x, y)

                elif current_cmd in 'Ss':
                    # S/s: smooth cubic bezier
                    if i + 3 < len(tokens):
                        x2, y2 = float(tokens[i][1]), float(tokens[i + 1][1])
                        x, y = float(tokens[i + 2][1]), float(tokens[i + 3][1])
                        i += 4
                        if current_cmd == 's':
                            x2 += current_pos[0]; y2 += current_pos[1]
                            x += current_pos[0]; y += current_pos[1]
                        # 反射控制点
                        curve_pts = self._sample_cubic_bezier(
                            current_pos, current_pos, (x2, y2), (x, y), steps=8
                        )
                        points.extend(curve_pts[1:])
                        current_pos = (x, y)

                elif current_cmd in 'Tt':
                    if i + 1 < len(tokens):
                        x, y = float(tokens[i][1]), float(tokens[i + 1][1])
                        i += 2
                        if current_cmd == 't':
                            x += current_pos[0]; y += current_pos[1]
                        curve_pts = self._sample_quadratic_bezier(
                            current_pos, current_pos, (x, y), steps=6
                        )
                        points.extend(curve_pts[1:])
                        current_pos = (x, y)

                else:
                    i += 1
            else:
                i += 1

        return points

    def _sample_cubic_bezier(self, p0, p1, p2, p3, steps=8):
        points = []
        for i in range(steps + 1):
            t = i / steps
            t2 = t * t
            t3 = t2 * t
            x = (1-3*t+3*t2-t3)*p0[0] + (3*t-6*t2+3*t3)*p1[0] + (3*t2-3*t3)*p2[0] + t3*p3[0]
            y = (1-3*t+3*t2-t3)*p0[1] + (3*t-6*t2+3*t3)*p1[1] + (3*t2-3*t3)*p2[1] + t3*p3[1]
            points.append((x, y))
        return points

    def _sample_quadratic_bezier(self, p0, p1, p2, steps=6):
        points = []
        for i in range(steps + 1):
            t = i / steps
            t2 = t * t
            x = (1-2*t+t2)*p0[0] + (2*t-2*t2)*p1[0] + t2*p2[0]
            y = (1-2*t+t2)*p0[1] + (2*t-2*t2)*p1[1] + t2*p2[1]
            points.append((x, y))
        return points

    def _parse_color(self, color_str: str) -> Tuple[int, int, int, int]:
        color_str = color_str.strip()
        if color_str.startswith('#'):
            hex_str = color_str[1:]
            if len(hex_str) == 6:
                return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16), 255)
            elif len(hex_str) == 8:
                return (int(hex_str[2:4], 16), int(hex_str[4:6], 16), int(hex_str[6:8], 16), int(hex_str[0:2], 16))
        color_map = {
            'black': (0, 0, 0, 255), 'white': (255, 255, 255, 255),
            'red': (255, 0, 0, 255), 'green': (0, 128, 0, 255),
            'blue': (0, 0, 255, 255), 'orange': (255, 165, 0, 255),
            'pink': (255, 192, 203, 255), 'yellow': (255, 255, 0, 255),
            'purple': (128, 0, 128, 255), 'gray': (128, 128, 128, 255),
            'none': (0, 0, 0, 255),
        }
        return color_map.get(color_str.lower(), (0, 0, 0, 255))

    def _quantize_points(self, points: List[Tuple[float, float]]) -> List[Tuple[int, int]]:
        result = []
        for x, y in points:
            xi = max(-32768, min(32767, int(round(x))))
            yi = max(-32768, min(32767, int(round(y))))
            result.append((xi, yi))
        return result


def resample_points(points: List[Tuple[float, float]], target_count: int) -> List[Tuple[float, float]]:
    """
    将点集重采样到目标点数，保留形状特征。
    使用等弧长重采样。
    """
    if len(points) < 2:
        return points * target_count if target_count > 0 else points

    if len(points) == target_count:
        return list(points)

    # 计算累积弧长
    cum_lengths = [0.0]
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        cum_lengths.append(cum_lengths[-1] + math.sqrt(dx * dx + dy * dy))

    total_length = cum_lengths[-1]
    if total_length == 0:
        return [points[0]] * target_count

    # 等弧长采样
    result = []
    for k in range(target_count):
        target_len = k * total_length / (target_count - 1) if target_count > 1 else 0

        # 二分查找
        lo, hi = 0, len(cum_lengths) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if cum_lengths[mid] <= target_len:
                lo = mid
            else:
                hi = mid

        # 线性插值
        seg_len = cum_lengths[hi] - cum_lengths[lo]
        if seg_len > 0:
            t = (target_len - cum_lengths[lo]) / seg_len
        else:
            t = 0

        x = points[lo][0] + t * (points[hi][0] - points[lo][0])
        y = points[lo][1] + t * (points[hi][1] - points[lo][1])
        result.append((x, y))

    return result


# ============================================================
#  WSD 记录表修改器 - 基于逆向工程的记录表结构
# ============================================================
#
# 记录表结构（通过对比 2000.wsd / 2000+.wsd / line.wsd 破解）:
#
# 文件尾部包含记录表，每条线段/图形是一条"sub-record"。
# 多条 sub-record 共享同一个画布。
#
# [marker: 0f 33 ff 00 07]  <-- 记录表起始标记
# [sub-record 1]             <-- 可变长度
# [sub-record 2]             <-- 可选，多条线时重复
# ...
# [公共尾部: 31字节]         <-- 所有 sub-record 共享
# [画布共享数据: 变长]
# [文件尾: filesize_le32 + ffffffff]
#
# sub-record 结构:
#   [0-4]:   marker (0f 33 ff 00 07)
#   [5-7]:   field marker (04 ff ff)
#   [8-11]:  color (4字节颜色索引)
#   [12-15]: padding
#   [16-19]: line width (uint32 LE = mm × 400)
#   [20-27]: common flags
#   [28-31]: type header (byte 28-30=0x00, byte 31=类型)
#
# Type 0x01 (旋转矩阵格式, 共77字节):
#   [32-33]: format flag = 0x47 0x3f
#   [34-49]: 2D旋转矩阵 (4 floats, 2-byte aligned: cos, -sin, sin, cos)
#            编码线段方向角, cos^2+sin^2=1.0
#   [50-76]: 线段特定参数 (27字节, 含位置/尺寸 uint32)
#
# Type 0x04 (直接坐标格式, 共53字节):
#   [32-33]: format flag = 0x47 0x00
#   [34-35]: endpoint count (uint16 LE, 通常=2)
#   [36-39]: x1 (uint32 LE)
#   [40-43]: y1 (uint32 LE)
#   [44-47]: x2 (uint32 LE)
#   [48-51]: y2 (uint32 LE)
#   [52]:    terminator (0x64)
#
# 画布尺寸存储在记录表之前的 pre-record 区域:
#   [pre_offset+0..1]: canvas_width (uint16 LE, 1/400mm)
#   [pre_offset+2..3]: padding
#   [pre_offset+4..5]: canvas_height (uint16 LE, 1/400mm)
# ============================================================

@dataclass
class WSDRecord:
    """单个 WSD 记录（文件尾部记录表中的一条线段 sub-record）"""
    marker_offset: int      # 记录标记 (0f 33 ff 00 07) 在文件中的绝对偏移
    canvas_index: int       # 所属画布索引（支持多画布）
    color: bytes             # 4字节颜色索引
    line_width_raw: int     # uint32 LE 线宽原始值（毫米 * 400）
    record_type: int        # sub-record 类型: 0x01=旋转矩阵, 0x04=直接坐标
    coord_regions: List     # 坐标区域列表: [(offset, count, fmt), ...]
                            #   fmt: 'uint32' 或 'float'
    record_size: int        # 记录总大小（从标记到下一条记录或公共尾部）


class WSDRecordModifier:
    """
    WSD 记录表修改器
    
    基于逆向工程验证的记录表格式，可以：
    - 解析文件尾部的记录表（查找 0f 33 ff 00 07 标记）
    - 识别 Type 0x01（旋转矩阵）和 Type 0x04（直接坐标）两种格式
    - 修改记录的颜色、线宽、uint32 坐标
    - 支持多线段、多画布文件
    - 保持文件大小不变（关键要求！）
    
    记录表位于文件尾部，每条记录以 0f 33 ff 00 07 标记开始。
    文件末尾有校验和: filesize_le32 + ff ff ff ff
    """

    # Type 0x01 sub-record 大小
    TYPE01_SIZE = 77
    # Type 0x04 sub-record 大小
    TYPE04_SIZE = 53
    # 公共尾部大小（所有 sub-record 之后共享）
    COMMON_TAIL_SIZE = 31
    # 公共尾部签名（用于验证）
    COMMON_TAIL_SIGNATURE = bytes([
        0x88, 0x45, 0x00, 0x00, 0x38, 0x31, 0x00, 0x00,
        0x88, 0x45, 0x00, 0x00, 0x38, 0x31, 0x00, 0x00,
        0x00, 0x01, 0x00, 0x32, 0x00, 0x10, 0xf5, 0x00,
        0x00, 0x00, 0x00, 0x00, 0xff, 0xff, 0x01,
    ])

    def __init__(self, wsd_path: str):
        """
        加载 WSD 文件
        
        Args:
            wsd_path: WSD 文件路径
        """
        self.wsd_path = wsd_path
        with open(wsd_path, 'rb') as f:
            self.data = bytearray(f.read())
        self.original_size = len(self.data)
        self.records: List[WSDRecord] = []
        self._parsed = False

    def parseRecords(self) -> List[WSDRecord]:
        """
        解析记录表 - 在文件尾部查找所有 0f 33 ff 00 07 标记
        
        识别两种 sub-record 类型:
          - Type 0x01: 旋转矩阵格式（77字节，含方向角cos/sin编码）
          - Type 0x04: 直接坐标格式（53字节，含uint32端点 x1,y1,x2,y2）
        
        返回找到的记录列表。每条记录包含标记偏移、颜色、线宽、类型等信息。
        支持多画布文件（每条记录关联一个画布索引）。
        """
        self.records = []
        data = self.data
        file_size = len(data)

        # 从文件后半部分搜索记录标记
        search_start = max(0, file_size - file_size // 2)

        # 第一遍：找到所有标记位置
        markers = []
        i = search_start
        while i < file_size - 32:
            if (data[i] == 0x0f and data[i + 1] == 0x33 and
                data[i + 2] == 0xff and data[i + 3] == 0x00 and
                data[i + 4] == 0x07):
                # 验证字段标记: 04 ff ff
                if (i + 8 < file_size and
                    data[i + 5] == 0x04 and data[i + 6] == 0xff and
                    data[i + 7] == 0xff):
                    markers.append(i)
            i += 1

        if not markers:
            self._parsed = True
            print("[记录表解析] 未找到任何记录标记")
            return self.records

        # 第二遍：逐条解析记录
        for idx, marker_pos in enumerate(markers):
            if marker_pos + 53 > file_size:
                continue  # 至少需要 53 字节（type 0x04 最小大小）

            # 提取颜色索引 (marker+8, 4字节)
            color = bytes(data[marker_pos + COLOR_OFFSET:marker_pos + COLOR_OFFSET + 4])

            # 提取线宽 (marker+16, uint32 LE, 毫米 * 400)
            if marker_pos + LINEWIDTH_OFFSET + 4 <= file_size:
                lw_raw = struct.unpack('<I', data[marker_pos + LINEWIDTH_OFFSET:marker_pos + LINEWIDTH_OFFSET + 4])[0]
            else:
                lw_raw = 0

            # 识别 sub-record 类型 (byte 31)
            record_type = data[marker_pos + 31]

            # 解析坐标数据区域
            coord_regions = []

            if record_type == 0x04:
                # Type 0x04: 直接坐标格式
                # [34-35]: endpoint count (uint16 LE)
                if marker_pos + 52 <= file_size:
                    ep_count = struct.unpack('<H', data[marker_pos + 34:marker_pos + 36])[0]
                    # 坐标在 marker+36: x1(4B), y1(4B), x2(4B), y2(4B)
                    coord_regions.append((
                        marker_pos + 36,   # 数据偏移
                        ep_count,          # 端点数（通常=2）
                        'uint32'           # 格式
                    ))
                # Type 0x04 的大小 = 53 字节
                rec_size = self.TYPE04_SIZE

            elif record_type == 0x01:
                # Type 0x01: 旋转矩阵格式
                # [34-49]: 2D旋转矩阵 (4 floats, 2-byte aligned)
                # cos(marker+34), -sin(marker+38), sin(marker+42), cos(marker+46)
                # 这些是方向角编码，cos^2+sin^2=1.0
                # [50-76]: 位置/尺寸参数 (27字节 uint32 数据)
                #
                # 提取 uint32 坐标区域 (offset 56-76)
                # 这些值代表线段在页面上的位置参数
                for uoff in [56, 60, 64, 68, 72, 76]:
                    if marker_pos + uoff + 4 <= file_size:
                        coord_regions.append((
                            marker_pos + uoff,
                            1,  # 每个偏移一个 uint32 值
                            'uint32_type01'  # Type 0x01 的位置参数
                        ))
                # Type 0x01 的大小 = 77 字节
                rec_size = self.TYPE01_SIZE

            else:
                # 未知类型：使用启发式方法
                rec_size = 77  # 默认
                # 尝试在后续字节中查找 uint32 坐标对
                scan_pos = marker_pos + 32
                scan_end = min(scan_pos + 100, file_size)
                while scan_pos < scan_end:
                    if (data[scan_pos] == 0x0f and scan_pos + 4 < file_size and
                        data[scan_pos + 1] == 0x33):
                        break  # 下一条记录
                    scan_pos += 1
                if scan_pos > marker_pos + 32 + 16:
                    coord_regions.append((marker_pos + 32, (scan_pos - marker_pos - 32) // 8, 'uint32'))

            record = WSDRecord(
                marker_offset=marker_pos,
                canvas_index=idx,  # 临时值，后续由 _assign_canvas_indices 修正
                color=color,
                line_width_raw=lw_raw,
                record_type=record_type,
                coord_regions=coord_regions,
                record_size=rec_size,
            )
            self.records.append(record)

        # 按偏移排序（从文件头到尾的顺序）
        self.records.sort(key=lambda r: r.marker_offset)

        # 分配画布索引：基于记录间的间隔判断画布边界
        self._assign_canvas_indices()

        self._parsed = True
        print(f"[记录表解析] 找到 {len(self.records)} 条记录")
        for idx, rec in enumerate(self.records):
            color_name = COLOR_INDEX_REVERSE.get(rec.color, f'{rec.color.hex()}')
            lw_mm = rec.line_width_raw / 400.0 if rec.line_width_raw else 0
            type_name = {0x01: '旋转矩阵', 0x04: '直接坐标'}.get(rec.record_type, f'未知({rec.record_type:#x})')
            print(f"  记录 {idx}: 画布={rec.canvas_index}, "
                  f"偏移=0x{rec.marker_offset:x}, "
                  f"类型={type_name}, "
                  f"颜色={color_name}, "
                  f"线宽={lw_mm:.2f}mm, "
                  f"坐标区域={len(rec.coord_regions)}个")

        return self.records

    def _assign_canvas_indices(self):
        """
        分配画布索引
        
        根据记录间的距离判断是否属于同一画布。
        同一画布的记录通常紧密排列，不同画布之间有较大间隔。
        """
        if len(self.records) <= 1:
            return

        # 计算相邻记录间距
        gaps = []
        for i in range(1, len(self.records)):
            gap = self.records[i].marker_offset - self.records[i - 1].marker_offset
            gaps.append(gap)

        if not gaps:
            return

        # 使用间距中位数的 3 倍作为画布分隔阈值
        median_gap = sorted(gaps)[len(gaps) // 2]
        threshold = max(median_gap * 3, 1000)  # 至少 1000 字节

        canvas_idx = 0
        for i, rec in enumerate(self.records):
            if i > 0 and gaps[i - 1] > threshold:
                canvas_idx += 1
            rec.canvas_index = canvas_idx

    def modifyRecordColor(self, record_index: int, new_color: bytes) -> bool:
        """
        修改指定记录的颜色
        
        Args:
            record_index: 记录索引（0-based）
            new_color: 4字节颜色索引，如 COLOR_INDEX_MAP['red']
        
        Returns:
            成功返回 True
        """
        if not self._parsed:
            self.parseRecords()

        if record_index < 0 or record_index >= len(self.records):
            print(f"错误: 记录索引 {record_index} 超出范围 (0~{len(self.records) - 1})")
            return False

        if len(new_color) != 4:
            print("错误: 颜色必须是 4 字节")
            return False

        rec = self.records[record_index]
        offset = rec.marker_offset + COLOR_OFFSET
        self.data[offset:offset + 4] = new_color
        rec.color = new_color

        color_name = COLOR_INDEX_REVERSE.get(new_color, f'{new_color.hex()}')
        print(f"[颜色修改] 记录 {record_index}: 颜色 -> {color_name}")
        return True

    def modifyRecordColorByName(self, record_index: int, color_name: str) -> bool:
        """
        通过颜色名称修改记录颜色
        
        Args:
            record_index: 记录索引
            color_name: 颜色名称 ('red', 'green', 'blue', 'black', 'white')
        
        Returns:
            成功返回 True
        """
        if color_name.lower() not in COLOR_INDEX_MAP:
            print(f"错误: 未知颜色 '{color_name}'，可选: {list(COLOR_INDEX_MAP.keys())}")
            return False

        return self.modifyRecordColor(record_index, COLOR_INDEX_MAP[color_name.lower()])

    def modifyRecordLineWidth(self, record_index: int, line_width_mm: float) -> bool:
        """
        修改指定记录的线宽
        
        Args:
            record_index: 记录索引
            line_width_mm: 线宽（毫米），将转换为 uint32 LE (毫米 * 400)
        
        Returns:
            成功返回 True
        """
        if not self._parsed:
            self.parseRecords()

        if record_index < 0 or record_index >= len(self.records):
            print(f"错误: 记录索引 {record_index} 超出范围 (0~{len(self.records) - 1})")
            return False

        rec = self.records[record_index]
        lw_raw = int(line_width_mm * 400)
        offset = rec.marker_offset + LINEWIDTH_OFFSET

        # 写入 uint32 LE 线宽值
        self.data[offset:offset + 4] = struct.pack('<I', lw_raw)
        rec.line_width_raw = lw_raw

        print(f"[线宽修改] 记录 {record_index}: 线宽 -> {line_width_mm:.2f}mm (raw={lw_raw})")
        return True

    def getRotationAngle(self, record_index: int) -> Optional[float]:
        """
        获取 Type 0x01 记录的旋转角度（线段方向角）
        
        Type 0x01 记录在 offset 34-49 存储 2D 旋转矩阵:
        [cos, -sin, sin, cos]，通过 atan2(sin, cos) 计算角度。
        
        Args:
            record_index: 记录索引
        
        Returns:
            角度（度），非 Type 0x01 返回 None
        """
        if not self._parsed:
            self.parseRecords()

        if record_index < 0 or record_index >= len(self.records):
            return None

        rec = self.records[record_index]
        if rec.record_type != 0x01:
            return None

        import math
        base = rec.marker_offset
        cos_val = struct.unpack('<f', self.data[base + 34:base + 38])[0]
        sin_val = struct.unpack('<f', self.data[base + 42:base + 46])[0]
        angle_deg = 360.0 / math.pi * math.atan2(sin_val, cos_val)
        return angle_deg

    def getEndpointCoords(self, record_index: int) -> Optional[List[Tuple[int, int]]]:
        """
        获取 Type 0x04 记录的端点坐标
        
        Type 0x04 记录在 offset 36 起存储直接 uint32 端点:
        [x1, y1, x2, y2, ...]（每个 4 字节 LE）
        
        Args:
            record_index: 记录索引
        
        Returns:
            端点坐标列表 [(x, y), ...]，非 Type 0x04 返回 None
        """
        if not self._parsed:
            self.parseRecords()

        if record_index < 0 or record_index >= len(self.records):
            return None

        rec = self.records[record_index]
        if rec.record_type != 0x04:
            return None

        base = rec.marker_offset
        ep_count = struct.unpack('<H', self.data[base + 34:base + 36])[0]
        coords = []
        for j in range(ep_count):
            x = struct.unpack('<I', self.data[base + 36 + j * 8:base + 40 + j * 8])[0]
            y = struct.unpack('<I', self.data[base + 40 + j * 8:base + 44 + j * 8])[0]
            coords.append((x, y))
        return coords

    def modifyRecordEndpoints(self, record_index: int,
                               new_coords: List[Tuple[int, int]]) -> bool:
        """
        修改 Type 0x04 记录的端点坐标
        
        直接修改 uint32 端点 x1,y1,x2,y2...。点数必须与原始相同。
        
        Args:
            record_index: 记录索引
            new_coords: 新端点坐标 [(x1, y1), (x2, y2), ...]
        
        Returns:
            成功返回 True
        """
        if not self._parsed:
            self.parseRecords()

        if record_index < 0 or record_index >= len(self.records):
            print(f"错误: 记录索引 {record_index} 超出范围")
            return False

        rec = self.records[record_index]
        if rec.record_type != 0x04:
            print(f"错误: 记录 {record_index} 不是 Type 0x04 (直接坐标格式)")
            return False

        base = rec.marker_offset
        ep_count = struct.unpack('<H', self.data[base + 34:base + 36])[0]

        if len(new_coords) != ep_count:
            print(f"错误: 新端点数 {len(new_coords)} != 原始端点数 {ep_count}")
            return False

        for j, (x, y) in enumerate(new_coords):
            pos = base + 36 + j * 8
            self.data[pos:pos + 4] = struct.pack('<I', x & 0xFFFFFFFF)
            self.data[pos + 4:pos + 8] = struct.pack('<I', y & 0xFFFFFFFF)

        print(f"[端点修改] 记录 {record_index}: "
              f"{[(f'({x},{y})') for x, y in new_coords]}")
        return True

    def modifyRecordCoordinates(self, record_index: int,
                                 coord_index: int,
                                 new_coords: List[Tuple[int, int]]) -> bool:
        """
        修改指定记录中 uint32 格式的坐标数据
        
        支持以下格式:
        - 'uint32': Type 0x04 的直接端点坐标（X/Y各4字节）
        - 'uint32_type01': Type 0x01 的位置参数（每个4字节）
        
        修改后点数必须与原始点数相同，以保证文件大小不变。
        
        Args:
            record_index: 记录索引
            coord_index: 坐标区域索引（一条记录可能有多个坐标区域）
            new_coords: 新坐标列表 [(x, y), ...]，每个坐标为 uint32
        
        Returns:
            成功返回 True
        """
        if not self._parsed:
            self.parseRecords()

        if record_index < 0 or record_index >= len(self.records):
            print(f"错误: 记录索引 {record_index} 超出范围")
            return False

        rec = self.records[record_index]
        if coord_index < 0 or coord_index >= len(rec.coord_regions):
            print(f"错误: 坐标区域索引 {coord_index} 超出范围 (0~{len(rec.coord_regions) - 1})")
            return False

        offset, count, fmt = rec.coord_regions[coord_index]
        if fmt not in ('uint32', 'uint32_type01'):
            print(f"错误: 坐标区域 {coord_index} 格式 '{fmt}' 不支持修改")
            return False

        if len(new_coords) != count:
            print(f"错误: 新坐标数 {len(new_coords)} != 原始坐标数 {count} "
                  f"(文件大小不能改变!)")
            return False

        if fmt == 'uint32':
            # Type 0x04: 逐点写入 X/Y (各4字节 LE)
            for j, (x, y) in enumerate(new_coords):
                pos = offset + j * 8
                self.data[pos:pos + 4] = struct.pack('<I', x & 0xFFFFFFFF)
                self.data[pos + 4:pos + 8] = struct.pack('<I', y & 0xFFFFFFFF)
        elif fmt == 'uint32_type01':
            # Type 0x01: 每个位置参数是单个 uint32
            for j, (x, y) in enumerate(new_coords):
                pos = offset + j * 4
                self.data[pos:pos + 4] = struct.pack('<I', x & 0xFFFFFFFF)

        print(f"[坐标修改] 记录 {record_index}, 区域 {coord_index}: "
              f"修改了 {len(new_coords)} 个坐标点")
        return True

    def _update_tail_checksum(self):
        """
        更新文件尾部校验和
        
        校验和格式: filesize_le32 + ff ff ff ff（共 8 字节）
        位于文件最后 8 字节。
        """
        # 写入文件大小 (uint32 LE)
        file_size = len(self.data)
        self.data[-8:-4] = struct.pack('<I', file_size)
        # 校验标记 ff ff ff ff
        self.data[-4:] = b'\xff\xff\xff\xff'

    def save(self, output_path: str) -> bool:
        """
        保存修改后的 WSD 文件
        
        关键要求: 文件大小必须与原始文件完全相同！
        
        Args:
            output_path: 输出文件路径
        
        Returns:
            成功返回 True
        """
        if len(self.data) != self.original_size:
            print(f"严重错误: 文件大小已改变! "
                  f"原始={self.original_size}, 当前={len(self.data)}")
            print("这会导致 EduEditor 无法打开文件!")
            return False

        # 更新尾部校验和
        self._update_tail_checksum()

        with open(output_path, 'wb') as f:
            f.write(self.data)

        print(f"[保存] 输出文件: {output_path} "
              f"(大小: {len(self.data)} 字节, 与原始一致: {len(self.data) == self.original_size})")
        return True

    def get_record_info(self, record_index: int) -> Optional[dict]:
        """
        获取指定记录的详细信息
        
        Args:
            record_index: 记录索引
        
        Returns:
            记录信息字典，索引无效返回 None
        """
        if not self._parsed:
            self.parseRecords()

        if record_index < 0 or record_index >= len(self.records):
            return None

        rec = self.records[record_index]
        color_name = COLOR_INDEX_REVERSE.get(rec.color, rec.color.hex())
        lw_mm = rec.line_width_raw / 400.0 if rec.line_width_raw else 0

        coord_info = []
        for ci, (offset, count, fmt) in enumerate(rec.coord_regions):
            coord_info.append({
                'index': ci,
                'offset': offset,
                'count': count,
                'format': fmt,
                'modifiable': fmt in ('uint32', 'uint32_type01'),
            })

        # 额外信息
        extra = {}
        if rec.record_type == 0x01:
            extra['rotation_angle'] = self.getRotationAngle(record_index)
        elif rec.record_type == 0x04:
            extra['endpoints'] = self.getEndpointCoords(record_index)

        return {
            'record_index': record_index,
            'marker_offset': rec.marker_offset,
            'canvas_index': rec.canvas_index,
            'record_type': rec.record_type,
            'record_type_name': {0x01: '旋转矩阵', 0x04: '直接坐标'}.get(rec.record_type, f'未知'),
            'color': rec.color.hex(),
            'color_name': color_name,
            'line_width_mm': lw_mm,
            'line_width_raw': rec.line_width_raw,
            'coord_regions': coord_info,
            'record_size': rec.record_size,
            **extra,
        }


def wsd_modify(wsd_path: str, output_path: str,
               color_changes: Optional[dict] = None,
               linewidth_changes: Optional[dict] = None,
               coord_changes: Optional[dict] = None) -> bool:
    """
    WSD 文件修改主函数
    
    基于逆向工程的记录表结构，对 WSD 文件进行精确修改。
    支持颜色、线宽、坐标的修改，且保持文件大小不变。
    
    Args:
        wsd_path: 输入 WSD 文件路径
        output_path: 输出 WSD 文件路径
        color_changes: 颜色修改字典 {记录索引: 颜色名或4字节}
            示例: {0: 'red', 1: 'blue', 2: bytes([0x00, 0x00, 0xff, 0xff])}
        linewidth_changes: 线宽修改字典 {记录索引: 线宽毫米}
            示例: {0: 0.5, 1: 2.0}
        coord_changes: 坐标修改字典 {(记录索引, 区域索引): [(x,y), ...]}
            示例: {(0, 0): [(100, 200), (300, 400), ...]}
            注意: 新坐标数必须与原始点数完全相同!
    
    Returns:
        成功返回 True
    
    使用示例:
        # 修改颜色
        wsd_modify('input.wsd', 'output.wsd', color_changes={0: 'red', 1: 'blue'})
        
        # 修改线宽
        wsd_modify('input.wsd', 'output.wsd', linewidth_changes={0: 0.5})
        
        # 修改坐标 + 颜色
        wsd_modify('input.wsd', 'output.wsd',
                   color_changes={0: 'green'},
                   coord_changes={(0, 0): [(100, 200), (300, 400)]})
    """
    print(f"=== WSD 记录修改器 ===")
    print(f"输入: {wsd_path}")
    print(f"输出: {output_path}")

    # 初始化修改器并解析记录表
    modifier = WSDRecordModifier(wsd_path)
    modifier.parseRecords()

    if not modifier.records:
        print("错误: 未找到任何记录标记 (0f 33 ff 00 07)")
        return False

    # 应用颜色修改
    if color_changes:
        print(f"\n[应用颜色修改] {len(color_changes)} 条")
        for rec_idx, color in color_changes.items():
            if isinstance(color, str):
                modifier.modifyRecordColorByName(rec_idx, color)
            elif isinstance(color, (bytes, bytearray)) and len(color) == 4:
                modifier.modifyRecordColor(rec_idx, bytes(color))
            else:
                print(f"  警告: 跳过无效颜色指定: 记录 {rec_idx}, 类型={type(color)}")

    # 应用线宽修改
    if linewidth_changes:
        print(f"\n[应用线宽修改] {len(linewidth_changes)} 条")
        for rec_idx, lw_mm in linewidth_changes.items():
            modifier.modifyRecordLineWidth(rec_idx, lw_mm)

    # 应用坐标修改
    if coord_changes:
        print(f"\n[应用坐标修改] {len(coord_changes)} 条")
        for (rec_idx, coord_idx), coords in coord_changes.items():
            modifier.modifyRecordCoordinates(rec_idx, coord_idx, coords)

    # 保存（自动校验文件大小 + 更新尾部校验和）
    success = modifier.save(output_path)

    if success:
        print(f"\n完成! 输出文件: {output_path}")
        print(f"请用 EduEditor 打开验证。")
    return success


def svg_to_wsd(template_path: str, svg_path: str, output_path: str):
    """
    SVG 转 WSD 主函数（模板替换模式）

    Args:
        template_path: WSD 模板文件路径（必须能被 EduEditor 打开）
        svg_path: SVG 输入文件路径
        output_path: WSD 输出文件路径
    """
    print(f"=== SVG to WSD (模板替换模式) ===")
    print(f"模板: {template_path}")
    print(f"输入: {svg_path}")
    print(f"输出: {output_path}")

    # 1. 解析模板
    print("\n[1/4] 解析模板文件...")
    tpl = WSDTemplateParser(template_path)
    tpl.parse()
    print(f"  矢量对象数: {tpl.get_object_count()}")
    print(f"  总点数: {tpl.get_total_points()}")

    # 2. 解析 SVG
    print("\n[2/4] 解析 SVG 文件...")
    svg_parser = SVGParser(svg_path)
    svg_objects = svg_parser.parse()
    print(f"  SVG 路径数: {len(svg_objects)}")

    if not svg_objects:
        print("错误: SVG 中没有有效路径")
        return False

    # 3. 将 SVG 坐标重采样以匹配模板点数
    print("\n[3/4] 重采样坐标...")
    total_template_pts = tpl.get_total_points()
    total_svg_pts = sum(len(obj.points) for obj in svg_objects)
    print(f"  SVG 总点数: {total_svg_pts}")
    print(f"  模板总点数: {total_template_pts}")

    # 收集所有 SVG 点并展平
    all_svg_points = []
    for obj in svg_objects:
        for pt in obj.points:
            all_svg_points.append((float(pt[0]), float(pt[1])))

    if len(all_svg_points) < 2:
        print("错误: SVG 点数不足")
        return False

    # 计算缩放：将 SVG 坐标映射到 WSD 坐标范围
    # WSD 使用大坐标（如 ±30000），SVG 通常是小坐标
    svg_min_x = min(p[0] for p in all_svg_points)
    svg_max_x = max(p[0] for p in all_svg_points)
    svg_min_y = min(p[1] for p in all_svg_points)
    svg_max_y = max(p[1] for p in all_svg_points)

    svg_w = svg_max_x - svg_min_x if svg_max_x != svg_min_x else 1
    svg_h = svg_max_y - svg_min_y if svg_max_y != svg_min_y else 1

    # 目标 WSD 坐标范围（参考原始文件）
    wsd_range = 25000  # 坐标范围
    wsd_center_x = 0
    wsd_center_y = 0

    scale_x = wsd_range / svg_w
    scale_y = wsd_range / svg_h
    scale = min(scale_x, scale_y)  # 等比缩放

    # 缩放坐标
    scaled_points = []
    for x, y in all_svg_points:
        sx = (x - svg_min_x - svg_w / 2) * scale + wsd_center_x
        sy = -(y - svg_min_y - svg_h / 2) * scale + wsd_center_y  # Y 轴翻转
        scaled_points.append((sx, sy))

    # 重采样到模板总点数
    resampled = resample_points(scaled_points, total_template_pts)
    print(f"  重采样后: {len(resampled)} 点")

    # 4. 替换模板坐标
    print("\n[4/4] 替换模板坐标...")
    success = tpl.replace_coordinates(resampled, output_path)

    if success:
        print(f"\n完成! 输出文件: {output_path}")
        print(f"请用 EduEditor 打开验证。")
    return success


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 4:
        template_path = sys.argv[1]
        svg_path = sys.argv[2]
        output_path = sys.argv[3]
        svg_to_wsd(template_path, svg_path, output_path)
    else:
        print("用法: python svg_to_wsd.py <template.wsd> <input.svg> <output.wsd>")
        print("")
        print("参数:")
        print("  template.wsd - WSD 模板文件（必须能被 EduEditor 打开）")
        print("  input.svg   - SVG 矢量图输入")
        print("  output.wsd  - 输出 WSD 文件")
        print("")
        print("注意: 转换后的 WSD 文件基于模板生成，模板的文档结构将被保留，")
        print("      仅矢量坐标数据被替换为 SVG 内容。")
