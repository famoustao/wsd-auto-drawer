#!/usr/bin/env python3
"""
WSD Auto Drawer - 单元测试
测试 SVG 与 WSD 的双向转换
"""

import os
import sys
import struct
import tempfile
import unittest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from svg_to_wsd import SVGParser, WSDWriter, WSDObject, svg_to_wsd
from wsd_to_svg import WSDParser, SVGRenderer, wsd_to_svg


class TestSVGToWSD(unittest.TestCase):
    """测试 SVG 到 WSD 转换"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_parse_simple_svg(self):
        """测试解析简单 SVG"""
        svg_content = '''<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <path d="M 10 10 L 50 50 L 90 10" stroke="#ff0000" fill="none"/>
</svg>'''
        
        svg_path = os.path.join(self.test_dir, 'test.svg')
        with open(svg_path, 'w') as f:
            f.write(svg_content)
        
        parser = SVGParser(svg_path)
        objects = parser.parse()
        
        self.assertEqual(len(objects), 1)
        self.assertEqual(len(objects[0].points), 3)
        self.assertEqual(objects[0].color, (255, 0, 0, 255))
    
    def test_parse_closed_path(self):
        """测试解析闭合路径"""
        svg_content = '''<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <path d="M 10 10 L 50 50 L 90 10 Z" stroke="#0000ff" fill="#00ff00"/>
</svg>'''
        
        svg_path = os.path.join(self.test_dir, 'test.svg')
        with open(svg_path, 'w') as f:
            f.write(svg_content)
        
        parser = SVGParser(svg_path)
        objects = parser.parse()
        
        self.assertEqual(len(objects), 1)
        self.assertTrue(objects[0].is_closed)
    
    def test_write_wsd(self):
        """测试写入 WSD 文件"""
        objects = [
            WSDObject(
                points=[(100, 100), (200, 200), (300, 100)],
                color=(255, 0, 0, 255),
                is_closed=False
            )
        ]
        
        wsd_path = os.path.join(self.test_dir, 'test.wsd')
        writer = WSDWriter(objects)
        writer.write(wsd_path)
        
        self.assertTrue(os.path.exists(wsd_path))
        self.assertGreater(os.path.getsize(wsd_path), 0)
    
    def test_full_conversion(self):
        """测试完整转换流程"""
        svg_content = '''<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <path d="M 10 10 L 50 50 L 90 10" stroke="#ff6600" fill="none"/>
  <path d="M 10 90 L 50 50 L 90 90" stroke="#0066ff" fill="none"/>
</svg>'''
        
        svg_path = os.path.join(self.test_dir, 'input.svg')
        wsd_path = os.path.join(self.test_dir, 'output.wsd')
        
        with open(svg_path, 'w') as f:
            f.write(svg_content)
        
        svg_to_wsd(svg_path, wsd_path)
        
        self.assertTrue(os.path.exists(wsd_path))


class TestWSDToSVG(unittest.TestCase):
    """测试 WSD 到 SVG 转换"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_parse_wsd_header(self):
        """测试解析 WSD 文件头"""
        # 创建一个最小化的有效 WSD 文件
        wsd_data = bytearray()
        wsd_data.append(0x00)  # 偏移0
        wsd_data.extend(b'WSTUDIO7')  # 文件头
        wsd_data.extend(b'\x00' * 100)  # 填充
        
        # 添加一个简单对象
        header = bytes([
            0x01, 0xff, 0xfd, 0xfe, 0xfe, 0xff,
            0x64, 0x0f, 0x33, 0xff,
            0x00, 0x07, 0x04, 0xff, 0xff,
            0xfd, 0xfe, 0xfe, 0xff,
            0x00, 0x22, 0x00, 0x00, 0x08,
            0x00, 0x00, 0x00, 0x00,
            0x04, 0x00, 0x04, 0x10,
            0x01, 0x00, 0x01, 0x00,
            0x00, 0x00,
            0x03, 0x47
        ])
        wsd_data.extend(header)
        
        # 点数: 3
        wsd_data.extend(struct.pack('>H', 3))
        wsd_data.append(0x00)  # 填充
        
        # 坐标: (100, 100), (200, 200), (300, 100)
        for x, y in [(100, 100), (200, 200), (300, 100)]:
            wsd_data.extend(struct.pack('<h', x))
            wsd_data.extend(b'\x00\x00')
            wsd_data.extend(struct.pack('<h', y))
            wsd_data.extend(b'\x00\x00')
        
        # 颜色: 红色
        wsd_data.extend([255, 0, 0, 255])
        # 尾部
        wsd_data.extend([0x00, 0x00])
        
        # 文件尾
        wsd_data.extend(b'\x00' * 20)
        
        wsd_path = os.path.join(self.test_dir, 'test.wsd')
        with open(wsd_path, 'wb') as f:
            f.write(wsd_data)
        
        parser = WSDParser(wsd_path)
        paths = parser.parse()
        
        self.assertEqual(len(paths), 1)
        self.assertEqual(len(paths[0].points), 3)
    
    def test_render_svg(self):
        """测试渲染 SVG"""
        from wsd_to_svg import VectorPath
        
        paths = [
            VectorPath(
                points=[(100.0, 100.0), (200.0, 200.0), (300.0, 100.0)],
                color='#ff0000',
                is_closed=False
            )
        ]
        
        svg_path = os.path.join(self.test_dir, 'output.svg')
        renderer = SVGRenderer()
        renderer.render(paths, svg_path)
        
        self.assertTrue(os.path.exists(svg_path))
        with open(svg_path, 'r') as f:
            content = f.read()
        self.assertIn('svg', content)
        self.assertIn('path', content)


class TestRoundTrip(unittest.TestCase):
    """测试往返转换（SVG -> WSD -> SVG）"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_roundtrip(self):
        """测试往返转换"""
        svg_content = '''<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <path d="M 10 10 L 50 50 L 90 10" stroke="#ff6600" fill="none"/>
</svg>'''
        
        svg1_path = os.path.join(self.test_dir, 'input.svg')
        wsd_path = os.path.join(self.test_dir, 'middle.wsd')
        svg2_path = os.path.join(self.test_dir, 'output.svg')
        
        with open(svg1_path, 'w') as f:
            f.write(svg_content)
        
        # SVG -> WSD
        svg_to_wsd(svg1_path, wsd_path)
        self.assertTrue(os.path.exists(wsd_path))
        
        # WSD -> SVG
        wsd_to_svg(wsd_path, svg2_path)
        self.assertTrue(os.path.exists(svg2_path))
        
        with open(svg2_path, 'r') as f:
            content = f.read()
        self.assertIn('svg', content)


if __name__ == '__main__':
    unittest.main(verbosity=2)
