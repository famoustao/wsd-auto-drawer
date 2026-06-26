#!/usr/bin/env python3
"""
WSD to SVG Converter
将 EduEditor WStudio7 (.wsd) 格式转换为 SVG 矢量图
"""

import struct
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class VectorPath:
    """矢量路径对象"""
    points: List[Tuple[float, float]]
    color: str = '#000000'
    fill_color: Optional[str] = None
    stroke_width: float = 1.0
    is_closed: bool = False


class WSDParser:
    """WStudio .wsd 文件解析器"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data = None
        self.version = None
        self.objects: List[VectorPath] = []
    
    def parse(self) -> List[VectorPath]:
        """解析文件并返回路径列表"""
        with open(self.filepath, 'rb') as f:
            self.data = f.read()
        
        if len(self.data) < 10 or self.data[1:8] != b'WSTUDIO':
            raise ValueError("不是有效的 WStudio 文件")
        
        self.version = self.data[8]
        
        # 查找所有对象
        obj_offsets = self._find_objects()
        
        for start, end in obj_offsets:
            obj_data = self.data[start:end]
            path = self._parse_object(obj_data)
            if path:
                self.objects.append(path)
        
        return self.objects
    
    def _find_objects(self) -> List[Tuple[int, int]]:
        """查找所有对象的位置"""
        objects = []
        i = 0
        while i < len(self.data) - 50:
            if self.data[i] == 0x01 and self.data[i+1] == 0xff:
                if b'\x64\x0f3\xff' in self.data[i:i+50]:
                    obj_start = i
                    j = i + 1
                    while j < len(self.data) - 50:
                        if self.data[j] == 0x01 and self.data[j+1] == 0xff:
                            if b'\x64\x0f3\xff' in self.data[j:j+50]:
                                break
                        j += 1
                    obj_end = j if j < len(self.data) - 50 else len(self.data)
                    objects.append((obj_start, obj_end))
                    i = j
                    continue
            i += 1
        return objects
    
    def _parse_object(self, obj_data: bytes) -> Optional[VectorPath]:
        """解析单个对象"""
        if len(obj_data) < 50:
            return None
        
        # 查找对象头结束标记 03 47
        header_end = -1
        for i in range(0, min(60, len(obj_data) - 2)):
            if obj_data[i] == 0x03 and obj_data[i+1] == 0x47:
                header_end = i
                break
        
        if header_end < 0:
            return None
        
        # 点数 (大端序)
        point_count = struct.unpack('>H', obj_data[header_end+2:header_end+4])[0]
        
        # 坐标起始偏移
        coord_start = header_end + 5
        coord_size = point_count * 8
        
        if coord_start + coord_size > len(obj_data):
            return None
        
        # 解析坐标 (低16位小端序有符号整数)
        points = []
        for i in range(point_count):
            offset = coord_start + i * 8
            x = struct.unpack('<h', obj_data[offset:offset+2])[0]
            y = struct.unpack('<h', obj_data[offset+4:offset+6])[0]
            points.append((float(x), float(y)))
        
        # 提取颜色
        color = self._extract_color(obj_data, coord_start + coord_size)
        
        # 判断是否闭合路径
        is_closed = (points[0] == points[-1]) or self._is_near(points[0], points[-1])
        
        return VectorPath(
            points=points,
            color=color,
            is_closed=is_closed
        )
    
    def _extract_color(self, obj_data: bytes, start_offset: int) -> str:
        """提取对象颜色"""
        remaining = obj_data[start_offset:]
        for i in range(0, len(remaining) - 4):
            chunk = remaining[i:i+4]
            if chunk[3] == 0xff:
                r, g, b, a = chunk
                if (r, g, b) not in [(0, 0, 0), (255, 255, 255), (0, 0, 1), (1, 0, 1)]:
                    if max(r, g, b) > 30:
                        return f"#{r:02x}{g:02x}{b:02x}"
        return '#000000'
    
    @staticmethod
    def _is_near(p1: Tuple[float, float], p2: Tuple[float, float], tolerance: float = 5.0) -> bool:
        """判断两点是否接近"""
        return abs(p1[0] - p2[0]) < tolerance and abs(p1[1] - p2[1]) < tolerance


class SVGRenderer:
    """SVG 渲染器"""
    
    def __init__(self, width: float = 800, height: float = 600):
        self.width = width
        self.height = height
        self.padding = 20
    
    def render(self, paths: List[VectorPath], output_path: str, flip_y: bool = True):
        """渲染为 SVG 文件"""
        if not paths:
            print("没有路径可生成")
            return
        
        # 计算边界框
        all_points = []
        for p in paths:
            all_points.extend(p.points)
        
        min_x = min(p[0] for p in all_points)
        max_x = max(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_y = max(p[1] for p in all_points)
        
        # 应用缩放和偏移
        scale = 0.1
        
        if flip_y:
            offset_x = -min_x * scale + 10
            offset_y = max_y * scale + 10
            
            def transform(p):
                return (p[0] * scale + offset_x, -p[1] * scale + offset_y)
        else:
            offset_x = -min_x * scale + 10
            offset_y = -min_y * scale + 10
            
            def transform(p):
                return (p[0] * scale + offset_x, p[1] * scale + offset_y)
        
        width = (max_x - min_x) * scale + 20
        height = (max_y - min_y) * scale + 20
        
        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" viewBox="0 0 {width:.1f} {height:.1f}">
  <rect width="100%" height="100%" fill="#ffffff"/>
'''
        
        for idx, path in enumerate(paths):
            if len(path.points) < 2:
                continue
            
            scaled = [transform(p) for p in path.points]
            
            d = f"M {scaled[0][0]:.2f} {scaled[0][1]:.2f}"
            for x, y in scaled[1:]:
                d += f" L {x:.2f} {y:.2f}"
            
            svg += f'  <path d="{d}" fill="none" stroke="{path.color}" stroke-width="0.8" stroke-linecap="round" stroke-linejoin="round" id="path_{idx}"/>\n'
        
        svg += '</svg>'
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(svg)
        
        print(f"SVG 已生成: {output_path}")


def wsd_to_svg(wsd_path: str, svg_path: str):
    """WSD 转 SVG 主函数"""
    print(f"正在转换: {wsd_path} -> {svg_path}")
    
    parser = WSDParser(wsd_path)
    paths = parser.parse()
    
    if not paths:
        print("警告: 未找到有效路径")
        return
    
    print(f"解析到 {len(paths)} 条路径")
    
    renderer = SVGRenderer()
    renderer.render(paths, svg_path)


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 3:
        wsd_to_svg(sys.argv[1], sys.argv[2])
    else:
        print("用法: python wsd_to_svg.py <input.wsd> <output.svg>")
