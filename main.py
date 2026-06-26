#!/usr/bin/env python3
"""
WSD Auto Drawer - 主程序入口
支持 SVG 与 WSD 的双向转换（单文件 + 批量）

用法:
    python main.py svg2wsd <input.svg> <output.wsd>
    python main.py wsd2svg <input.wsd> <output.svg>
    python main.py batch <input_dir> <output_dir> --mode svg2wsd
"""

import argparse
import os
import sys
import time

from svg_to_wsd import svg_to_wsd
from wsd_to_svg import wsd_to_svg


def batch_convert(input_dir: str, output_dir: str, mode: str):
    """批量转换（增强版，带进度统计）"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"创建输出目录: {output_dir}")

    # 收集文件
    if mode == 'svg2wsd':
        ext = '.svg'
        target_ext = '.wsd'
        convert_func = svg_to_wsd
    else:
        ext = '.wsd'
        target_ext = '.svg'
        convert_func = wsd_to_svg

    files = sorted([f for f in os.listdir(input_dir) if f.lower().endswith(ext)])

    if not files:
        print(f"警告: 在 {input_dir} 中未找到 {ext} 文件")
        return

    print(f"\n{'='*50}")
    print(f"批量转换: {mode}")
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print(f"文件数量: {len(files)}")
    print(f"{'='*50}\n")

    success = 0
    failed = 0
    start_time = time.time()

    for idx, filename in enumerate(files, 1):
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, os.path.splitext(filename)[0] + target_ext)

        print(f"[{idx:>{len(str(len(files)))}}/{len(files)}] {filename} ... ", end='', flush=True)

        try:
            convert_func(input_path, output_path)
            print("OK")
            success += 1
        except Exception as e:
            print(f"FAIL ({e})")
            failed += 1

    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"完成: 成功 {success} / 失败 {failed} / 总计 {len(files)}")
    print(f"耗时: {elapsed:.2f} 秒")
    print(f"输出: {output_dir}")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(
        description='WSD Auto Drawer - SVG 与 WSD 双向转换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 单文件转换
  python main.py svg2wsd input.svg output.wsd
  python main.py wsd2svg input.wsd output.svg

  # 批量转换（目录级别）
  python main.py batch ./svg_dir ./wsd_dir --mode svg2wsd
  python main.py batch ./wsd_dir ./svg_dir --mode wsd2svg
        '''
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # svg2wsd 命令
    svg2wsd_parser = subparsers.add_parser('svg2wsd', help='SVG 转 WSD')
    svg2wsd_parser.add_argument('input', help='输入 SVG 文件')
    svg2wsd_parser.add_argument('output', help='输出 WSD 文件')

    # wsd2svg 命令
    wsd2svg_parser = subparsers.add_parser('wsd2svg', help='WSD 转 SVG')
    wsd2svg_parser.add_argument('input', help='输入 WSD 文件')
    wsd2svg_parser.add_argument('output', help='输出 SVG 文件')

    # batch 命令
    batch_parser = subparsers.add_parser('batch', help='批量转换')
    batch_parser.add_argument('input_dir', help='输入目录')
    batch_parser.add_argument('output_dir', help='输出目录')
    batch_parser.add_argument('--mode', choices=['svg2wsd', 'wsd2svg'], required=True,
                             help='转换模式')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == 'svg2wsd':
        if not os.path.exists(args.input):
            print(f"错误: 文件不存在: {args.input}")
            sys.exit(1)
        svg_to_wsd(args.input, args.output)

    elif args.command == 'wsd2svg':
        if not os.path.exists(args.input):
            print(f"错误: 文件不存在: {args.input}")
            sys.exit(1)
        wsd_to_svg(args.input, args.output)

    elif args.command == 'batch':
        if not os.path.exists(args.input_dir):
            print(f"错误: 目录不存在: {args.input_dir}")
            sys.exit(1)
        batch_convert(args.input_dir, args.output_dir, args.mode)


if __name__ == '__main__':
    main()
