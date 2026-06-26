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
