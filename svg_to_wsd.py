#!/usr/bin/env python3
"""
SVG to WSD Converter
将 SVG 矢量图转换为 EduEditor WStudio7 (.wsd) 格式

WSD 格式规范（逆向工程）：
- 文件头: WSTUDIO7 (8字节, 偏移1)
- 每个对象:
  - 对象头: 41字节固定模板，以 03 47 结束
  - 点数: 2字节大端序无符号整数
  - 填充: 1字节 (00)
  - 坐标: 每点8字节，低16位小端序有符号整数 (X,Y)
  - 颜色: 4字节ARGB
  - 尾部: 2字节
"""

import struct
import re
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class WSDObject:
    """WSD 对象"""
    points: List[Tuple[int, int]]
    color: Tuple[int, int, int, int] = (0, 0, 0, 255)
    is_closed: bool = False


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
        
        # 获取 SVG 命名空间
        ns = {'svg': 'http://www.w3.org/2000/svg'}
        
        objects = []
        
        # 查找所有 path 元素
        for path_elem in root.findall('.//svg:path', ns):
            d = path_elem.get('d', '')
            if not d:
                continue
            
            # 解析路径数据
            points = self._parse_path_data(d)
            if len(points) < 2:
                continue
            
            # 提取颜色
            stroke = path_elem.get('stroke', '#000000')
            fill = path_elem.get('fill', 'none')
            color = self._parse_color(stroke)
            
            # 判断是否闭合
            is_closed = fill != 'none' or d.strip().endswith('Z') or d.strip().endswith('z')
            
            objects.append(WSDObject(
                points=self._quantize_points(points),
                color=color,
                is_closed=is_closed
            ))
        
        # 如果没有 namespace，尝试直接查找
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
        
        # 标准化命令
        d = d.replace(',', ' ')
        
        # 匹配命令和数字
        tokens = re.findall(r'([MmLlHhVvCcSsQqTtAaZz])|(-?\d+\.?\d*)', d)
        
        current_cmd = None
        current_pos = (0.0, 0.0)
        start_pos = (0.0, 0.0)
        i = 0
        
        while i < len(tokens):
            token = tokens[i]
            
            if token[0]:  # 是命令
                current_cmd = token[0]
                i += 1
                
                if current_cmd in 'Mm':
                    x = float(tokens[i][1])
                    y = float(tokens[i+1][1])
                    i += 2
                    
                    if current_cmd == 'm':
                        x += current_pos[0]
                        y += current_pos[1]
                    
                    current_pos = (x, y)
                    start_pos = current_pos
                    points.append(current_pos)
                    
                    # 后续的坐标对视为隐式 L/l
                    while i < len(tokens) and not tokens[i][0]:
                        x = float(tokens[i][1])
                        y = float(tokens[i+1][1])
                        i += 2
                        
                        if current_cmd == 'm':
                            x += current_pos[0]
                            y += current_pos[1]
                        
                        current_pos = (x, y)
                        points.append(current_pos)
                
                elif current_cmd in 'Ll':
                    x = float(tokens[i][1])
                    y = float(tokens[i+1][1])
                    i += 2
                    
                    if current_cmd == 'l':
                        x += current_pos[0]
                        y += current_pos[1]
                    
                    current_pos = (x, y)
                    points.append(current_pos)
                    
                    # 隐式续接
                    while i < len(tokens) and not tokens[i][0]:
                        x = float(tokens[i][1])
                        y = float(tokens[i+1][1])
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
                    # 简化贝塞尔曲线为折线
                    if i + 5 < len(tokens):
                        x1 = float(tokens[i][1])
                        y1 = float(tokens[i+1][1])
                        x2 = float(tokens[i+2][1])
                        y2 = float(tokens[i+3][1])
                        x = float(tokens[i+4][1])
                        y = float(tokens[i+5][1])
                        i += 6
                        
                        if current_cmd == 'c':
                            x1 += current_pos[0]
                            y1 += current_pos[1]
                            x2 += current_pos[0]
                            y2 += current_pos[1]
                            x += current_pos[0]
                            y += current_pos[1]
                        
                        # 采样曲线上的点
                        curve_points = self._sample_cubic_bezier(
                            current_pos, (x1, y1), (x2, y2), (x, y), steps=8
                        )
                        points.extend(curve_points[1:])
                        current_pos = (x, y)
                
                elif current_cmd in 'Qq':
                    if i + 3 < len(tokens):
                        x1 = float(tokens[i][1])
                        y1 = float(tokens[i+1][1])
                        x = float(tokens[i+2][1])
                        y = float(tokens[i+3][1])
                        i += 4
                        
                        if current_cmd == 'q':
                            x1 += current_pos[0]
                            y1 += current_pos[1]
                            x += current_pos[0]
                            y += current_pos[1]
                        
                        curve_points = self._sample_quadratic_bezier(
                            current_pos, (x1, y1), (x, y), steps=6
                        )
                        points.extend(curve_points[1:])
                        current_pos = (x, y)
                
                else:
                    # 跳过不支持的命令参数
                    i += 1
            else:
                i += 1
        
        return points
    
    def _sample_cubic_bezier(self, p0, p1, p2, p3, steps=8):
        """采样三次贝塞尔曲线"""
        points = []
        for i in range(steps + 1):
            t = i / steps
            t2 = t * t
            t3 = t2 * t
            
            x = (1 - 3*t + 3*t2 - t3) * p0[0] + \
                (3*t - 6*t2 + 3*t3) * p1[0] + \
                (3*t2 - 3*t3) * p2[0] + \
                t3 * p3[0]
            
            y = (1 - 3*t + 3*t2 - t3) * p0[1] + \
                (3*t - 6*t2 + 3*t3) * p1[1] + \
                (3*t2 - 3*t3) * p2[1] + \
                t3 * p3[1]
            
            points.append((x, y))
        return points
    
    def _sample_quadratic_bezier(self, p0, p1, p2, steps=6):
        """采样二次贝塞尔曲线"""
        points = []
        for i in range(steps + 1):
            t = i / steps
            t2 = t * t
            
            x = (1 - 2*t + t2) * p0[0] + \
                (2*t - 2*t2) * p1[0] + \
                t2 * p2[0]
            
            y = (1 - 2*t + t2) * p0[1] + \
                (2*t - 2*t2) * p1[1] + \
                t2 * p2[1]
            
            points.append((x, y))
        return points
    
    def _parse_color(self, color_str: str) -> Tuple[int, int, int, int]:
        """解析颜色字符串为 ARGB"""
        color_str = color_str.strip()
        
        if color_str.startswith('#'):
            hex_str = color_str[1:]
            if len(hex_str) == 6:
                r = int(hex_str[0:2], 16)
                g = int(hex_str[2:4], 16)
                b = int(hex_str[4:6], 16)
                return (r, g, b, 255)
            elif len(hex_str) == 8:
                a = int(hex_str[0:2], 16)
                r = int(hex_str[2:4], 16)
                g = int(hex_str[4:6], 16)
                b = int(hex_str[6:8], 16)
                return (r, g, b, a)
        
        # 常见颜色名映射
        color_map = {
            'black': (0, 0, 0, 255),
            'white': (255, 255, 255, 255),
            'red': (255, 0, 0, 255),
            'green': (0, 128, 0, 255),
            'blue': (0, 0, 255, 255),
            'orange': (255, 165, 0, 255),
            'pink': (255, 192, 203, 255),
            'yellow': (255, 255, 0, 255),
            'purple': (128, 0, 128, 255),
            'gray': (128, 128, 128, 255),
            'none': (0, 0, 0, 255),
        }
        
        return color_map.get(color_str.lower(), (0, 0, 0, 255))
    
    def _quantize_points(self, points: List[Tuple[float, float]]) -> List[Tuple[int, int]]:
        """将浮点坐标量化为整数坐标"""
        # WSD 使用16位有符号整数，范围 -32768 ~ 32767
        # 我们将坐标缩放到合适的范围
        result = []
        for x, y in points:
            # 缩放并取整
            xi = int(round(x))
            yi = int(round(y))
            # 限制在有效范围内
            xi = max(-32768, min(32767, xi))
            yi = max(-32768, min(32767, yi))
            result.append((xi, yi))
        return result


class WSDWriter:
    """WSD 文件写入器"""
    
    # 对象头模板 (41字节)
    # 基于逆向分析得到的固定头结构
    OBJECT_HEADER = bytes([
        0x01, 0xff, 0xfd, 0xfe, 0xfe, 0xff,  # 开始标记
        0x64, 0x0f, 0x33, 0xff,               # 标识符 "d.3."
        0x00, 0x07, 0x04, 0xff, 0xff,         # 控制字节
        0xfd, 0xfe, 0xfe, 0xff,               # 标记
        0x00, 0x22, 0x00, 0x00, 0x08,         # 更多控制
        0x00, 0x00, 0x00, 0x00,               # 填充
        0x04, 0x00, 0x04, 0x10,               # 尺寸信息
        0x01, 0x00, 0x01, 0x00,               # 类型信息
        0x00, 0x00,                           # 填充
        0x03, 0x47                            # 头结束标记
    ])
    
    def __init__(self, objects: List[WSDObject]):
        self.objects = objects
    
    def write(self, output_path: str):
        """写入 WSD 文件"""
        with open(output_path, 'wb') as f:
            # 写入文件头
            f.write(b'\x00')  # 偏移0的填充字节
            f.write(b'WSTUDIO7')
            f.write(b'\x07')  # 版本号
            
            # 写入每个对象
            for obj in self.objects:
                self._write_object(f, obj)
            
            # 写入文件尾
            f.write(b'\x00' * 20)
        
        print(f"WSD 文件已生成: {output_path}")
        print(f"  对象数量: {len(self.objects)}")
    
    def _write_object(self, f, obj: WSDObject):
        """写入单个对象"""
        # 写入对象头
        f.write(self.OBJECT_HEADER)
        
        # 写入点数 (大端序)
        point_count = len(obj.points)
        f.write(struct.pack('>H', point_count))
        
        # 填充字节
        f.write(b'\x00')
        
        # 写入坐标数据
        for x, y in obj.points:
            # 每点8字节，低16位小端序有符号整数
            # X坐标 (4字节，低2字节有效)
            f.write(struct.pack('<h', x))
            f.write(b'\x00\x00')
            # Y坐标 (4字节，低2字节有效)
            f.write(struct.pack('<h', y))
            f.write(b'\x00\x00')
        
        # 写入颜色 (ARGB)
        r, g, b, a = obj.color
        f.write(bytes([r, g, b, a]))
        
        # 对象尾
        f.write(b'\x00\x00')


def svg_to_wsd(svg_path: str, wsd_path: str):
    """SVG 转 WSD 主函数"""
    print(f"正在转换: {svg_path} -> {wsd_path}")
    
    # 解析 SVG
    parser = SVGParser(svg_path)
    objects = parser.parse()
    
    if not objects:
        print("警告: 未找到有效路径")
        return
    
    print(f"解析到 {len(objects)} 个对象")
    
    # 写入 WSD
    writer = WSDWriter(objects)
    writer.write(wsd_path)


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 3:
        svg_to_wsd(sys.argv[1], sys.argv[2])
    else:
        print("用法: python svg_to_wsd.py <input.svg> <output.wsd>")
