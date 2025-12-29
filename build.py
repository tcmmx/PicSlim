#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ImageOPT 打包脚本
用于设置exe图标和名称
"""

import os
import subprocess
import sys
from pathlib import Path

def build_exe():
    """打包exe文件"""
    print("=" * 50)
    print("ImageOPT 打包脚本")
    print("=" * 50)
    print()
    
    # 检查图标文件
    icon_file = "icon.ico"
    icon_param = ""
    
    if os.path.exists(icon_file):
        print(f"[信息] 找到图标文件: {icon_file}")
        icon_param = f"-i {icon_file}"
    else:
        print(f"[警告] 未找到图标文件: {icon_file}")
        print("将使用默认图标打包")
        print("提示: 可以将PNG图片转换为ICO格式作为图标")
        print()
    
    # 打包参数
    exe_name = "图片缩放工具"
    
    # PyInstaller命令
    cmd = [
        "pyinstaller",
        "-F",  # 单文件打包
        "-w",  # 无控制台窗口
        "--name", exe_name,  # 设置exe名称
        "--clean",  # 清理临时文件
    ]
    
    # 添加图标参数
    if icon_param:
        cmd.extend(["-i", icon_file])
    
    # 添加主程序文件
    cmd.append("main.py")
    
    print("[信息] 开始打包...")
    print(f"命令: {' '.join(cmd)}")
    print()
    
    try:
        # 执行打包
        result = subprocess.run(cmd, check=True)
        print()
        print("=" * 50)
        print("打包完成！")
        print(f"生成的EXE文件位于: dist\\{exe_name}.exe")
        print("=" * 50)
    except subprocess.CalledProcessError as e:
        print()
        print("[错误] 打包失败！")
        print(f"错误信息: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print()
        print("[错误] 未找到 pyinstaller！")
        print("请先安装: pip install pyinstaller")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()

