#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将PNG图片转换为ICO格式（保留透明度）
支持圆形图标、透明背景等
"""

from PIL import Image
import sys
import os

def convert_png_to_ico(png_path, ico_path=None):
    """
    将PNG图片转换为ICO格式
    
    Args:
        png_path: PNG图片路径
        ico_path: 输出的ICO文件路径（默认为icon.ico）
    """
    if not os.path.exists(png_path):
        print(f"[错误] 文件不存在: {png_path}")
        return False
    
    # 默认输出文件名
    if ico_path is None:
        ico_path = "icon.ico"
    
    try:
        # 打开PNG图片
        img = Image.open(png_path)
        print(f"[信息] 原始图片: {img.size}, 模式: {img.mode}")
        
        # 如果图片不是RGBA模式（带透明度），转换为RGBA
        if img.mode != 'RGBA':
            print("[信息] 转换为RGBA模式以支持透明度...")
            # 创建白色背景
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                # 调色板模式，先转换为RGBA
                img = img.convert('RGBA')
            rgb_img.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
            img = rgb_img.convert('RGBA')
        else:
            print("[信息] 图片已包含透明度通道")
        
        # 定义多个尺寸（Windows需要不同尺寸的图标）
        sizes = [
            (256, 256),  # 大图标（任务栏、大图标视图）
            (128, 128),  # 中等图标
            (64, 64),    # 小图标
            (48, 48),    # 标准图标
            (32, 32),    # 列表视图
            (16, 16)     # 最小图标
        ]
        
        print(f"[信息] 正在生成ICO文件（包含 {len(sizes)} 个尺寸）...")
        
        # 保存为ICO格式（PIL会自动处理多尺寸）
        img.save(ico_path, format='ICO', sizes=sizes)
        
        print(f"[成功] ICO文件已生成: {ico_path}")
        print(f"[提示] 现在可以使用此图标文件打包EXE")
        return True
        
    except Exception as e:
        print(f"[错误] 转换失败: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("PNG转ICO工具（保留透明度）")
    print("=" * 50)
    print()
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print(f"  python {sys.argv[0]} <PNG文件路径> [输出ICO文件名]")
        print()
        print("示例:")
        print(f"  python {sys.argv[0]} icon.png")
        print(f"  python {sys.argv[0]} icon.png icon.ico")
        print()
        
        # 交互式输入
        png_file = input("请输入PNG文件路径（或直接拖拽文件到这里）: ").strip().strip('"')
        if png_file:
            convert_png_to_ico(png_file)
    else:
        png_file = sys.argv[1]
        ico_file = sys.argv[2] if len(sys.argv) > 2 else None
        convert_png_to_ico(png_file, ico_file)
    
    print()
    input("按回车键退出...")

