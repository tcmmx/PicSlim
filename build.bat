@echo off
chcp 65001 >nul
echo ========================================
echo PicSlim 打包脚本
echo ========================================
echo.

REM 检查是否存在图标文件
if not exist "icon.ico" (
    echo [警告] 未找到 icon.ico 文件
    echo 将使用默认图标打包
    echo.
    set ICON_PARAM=
) else (
    echo [信息] 找到图标文件: icon.ico
    set ICON_PARAM=-i icon.ico
)

REM 打包命令
echo [信息] 开始打包...
echo.

pyinstaller -F -w %ICON_PARAM% --name "PicSlim-批量图片缩放工具" --clean main.py

echo.
echo ========================================
echo 打包完成！
echo 生成的EXE文件位于: dist\PicSlim-批量图片缩放工具.exe
echo ========================================
pause

