#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ImageOPT - 批量图片分辨率缩小工具 v1.0
使用 PySide6 和 Pillow 实现
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QGroupBox, QProgressBar,
    QTextEdit, QFileDialog, QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QScrollArea, QRadioButton, QButtonGroup, QSlider, QGridLayout, QFrame
)
from PySide6.QtCore import QThread, Signal, Qt, QSize
from PySide6.QtGui import QFont, QPixmap, QImage


class FileScanThread(QThread):
    """文件扫描线程类，避免UI线程阻塞"""
    
    scan_progress = Signal(str)  # 扫描进度消息
    scan_finished = Signal(list)  # 扫描完成，返回文件列表
    
    def __init__(self, directory: str, recursive: bool, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.recursive = recursive
        self.is_cancelled = False
    
    def cancel(self):
        """取消扫描"""
        self.is_cancelled = True
    
    def run(self):
        """执行文件扫描"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
        image_files = []
        
        try:
            if self.recursive:
                count = 0
                for root, dirs, files in os.walk(self.directory):
                    if self.is_cancelled:
                        break
                    for file in files:
                        if self.is_cancelled:
                            break
                        if Path(file).suffix.lower() in image_extensions:
                            image_files.append(os.path.join(root, file))
                            count += 1
                            if count % 50 == 0:  # 每50个文件更新一次进度
                                self.scan_progress.emit(f"已扫描 {count} 个图片文件...")
            else:
                files = os.listdir(self.directory)
                for file in files:
                    if self.is_cancelled:
                        break
                    file_path = os.path.join(self.directory, file)
                    if os.path.isfile(file_path) and Path(file).suffix.lower() in image_extensions:
                        image_files.append(file_path)
        except Exception as e:
            self.scan_progress.emit(f"扫描错误: {str(e)}")
        
        if not self.is_cancelled:
            sorted_files = sorted(list(set(image_files)))  # 去重并排序
            self.scan_finished.emit(sorted_files)


class ImageProcessThread(QThread):
    """图片处理线程类，避免UI线程阻塞"""
    
    progress_update = Signal(int, int)  # 当前进度, 总数量
    log_update = Signal(str)  # 日志消息
    finish_signal = Signal(int, int)  # 成功数量, 失败数量
    
    def __init__(self, image_files: List[str], resize_mode: str, 
                 resize_value: float, output_format: str, quality: int,
                 output_mode: str, output_dir: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.image_files = image_files
        self.resize_mode = resize_mode  # 'scale' 或 'width'
        self.resize_value = resize_value
        self.output_format = output_format  # 'original', 'png', 'jpg', 'webp'
        self.quality = quality  # 1-100
        self.output_mode = output_mode  # 'overwrite' 或 'new_file'
        self.output_dir = output_dir  # 目标目录，None表示使用原目录
        self.is_cancelled = False
    
    def cancel(self):
        """取消处理"""
        self.is_cancelled = True
    
    def run(self):
        """执行批量处理"""
        total = len(self.image_files)
        success_count = 0
        fail_count = 0
        
        for idx, image_path in enumerate(self.image_files):
            if self.is_cancelled:
                self.log_update.emit("处理已取消")
                break
            
            try:
                self.log_update.emit(f"开始处理：{os.path.basename(image_path)}")
                
                # 打开图片
                with Image.open(image_path) as img:
                    original_size = img.size
                    self.log_update.emit(f"原尺寸：{original_size[0]}x{original_size[1]}")
                    
                    # 计算新尺寸
                    if self.resize_mode == 'scale':
                        new_width = int(original_size[0] * self.resize_value)
                        new_height = int(original_size[1] * self.resize_value)
                    else:  # width mode
                        if original_size[0] <= self.resize_value:
                            self.log_update.emit(f"⚠️ 原宽度 {original_size[0]} 小于等于目标宽度 {self.resize_value}，跳过")
                            fail_count += 1
                            self.progress_update.emit(idx + 1, total)
                            continue
                        new_width = int(self.resize_value)
                        new_height = int(original_size[1] * (self.resize_value / original_size[0]))
                    
                    # 缩放图片
                    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # 确定输出路径和格式
                    output_path, output_format = self._get_output_path(image_path, original_size, (new_width, new_height))
                    
                    # 保存图片
                    save_kwargs = {}
                    if output_format.upper() in ['JPG', 'JPEG']:
                        save_kwargs['quality'] = self.quality
                        if resized_img.mode in ['RGBA', 'LA', 'P']:
                            # 转换为RGB以支持JPG
                            rgb_img = Image.new('RGB', resized_img.size, (255, 255, 255))
                            if resized_img.mode == 'P':
                                resized_img = resized_img.convert('RGBA')
                            if resized_img.mode in ['RGBA', 'LA']:
                                alpha = resized_img.split()[-1]
                                rgb_img.paste(resized_img, mask=alpha)
                            else:
                                rgb_img.paste(resized_img)
                            resized_img = rgb_img
                    elif output_format.upper() == 'PNG':
                        save_kwargs['optimize'] = True
                        # PNG支持透明通道，保持原模式
                        if resized_img.mode not in ['RGBA', 'LA', 'P']:
                            # 如果原图没有透明通道，保持原模式或转换为RGB
                            pass
                    elif output_format.upper() == 'WEBP':
                        save_kwargs['quality'] = self.quality
                        save_kwargs['method'] = 6  # 最高质量压缩
                        # WEBP支持透明通道，如果是RGBA模式保持，否则转换为RGB
                        if resized_img.mode not in ['RGBA', 'LA']:
                            if resized_img.mode == 'P':
                                resized_img = resized_img.convert('RGBA')
                            else:
                                resized_img = resized_img.convert('RGB')
                    
                    resized_img.save(output_path, format=output_format, **save_kwargs)
                    self.log_update.emit(f"保存路径：{output_path} | 新尺寸：{new_width}x{new_height}")
                    self.log_update.emit(f"✅ 处理成功：{os.path.basename(image_path)}")
                    success_count += 1
                    
            except Exception as e:
                self.log_update.emit(f"❌ 处理失败：{os.path.basename(image_path)} - {str(e)}")
                fail_count += 1
            
            self.progress_update.emit(idx + 1, total)
        
        self.log_update.emit("=" * 50)
        self.log_update.emit(f"处理完成 | 总计：{total} 个 | 成功：{success_count} 个 | 失败：{fail_count} 个")
        self.finish_signal.emit(success_count, fail_count)
    
    def _get_output_path(self, original_path: str, original_size: Tuple[int, int], 
                         new_size: Tuple[int, int]) -> Tuple[str, str]:
        """获取输出路径和格式"""
        path_obj = Path(original_path)
        
        # 确定输出格式
        if self.output_format == 'original':
            output_format = path_obj.suffix[1:].upper() if path_obj.suffix else 'PNG'
            if output_format == 'JPG':
                output_format = 'JPEG'
        elif self.output_format == 'png':
            output_format = 'PNG'
        elif self.output_format == 'webp':
            output_format = 'WEBP'
        else:  # jpg
            output_format = 'JPEG'
        
        # 确定输出目录
        if self.output_dir:
            output_parent = Path(self.output_dir)
            output_parent.mkdir(parents=True, exist_ok=True)
        else:
            output_parent = path_obj.parent
        
        # 确定输出路径
        if self.output_mode == 'overwrite':
            # 如果格式改变，需要修改扩展名
            original_ext = path_obj.suffix.lower()
            if output_format == 'JPEG' and original_ext not in ['.jpg', '.jpeg']:
                output_path = str(output_parent / path_obj.with_suffix('.jpg').name)
            elif output_format == 'PNG' and original_ext != '.png':
                output_path = str(output_parent / path_obj.with_suffix('.png').name)
            elif output_format == 'WEBP' and original_ext != '.webp':
                output_path = str(output_parent / path_obj.with_suffix('.webp').name)
            else:
                output_path = str(output_parent / path_obj.name)
        else:  # new_file
            # 添加分辨率信息到文件名
            size_info = f"_{new_size[0]}x{new_size[1]}"
            if output_format == 'JPEG':
                new_name = f"{path_obj.stem}{size_info}.jpg"
            elif output_format == 'WEBP':
                new_name = f"{path_obj.stem}{size_info}.webp"
            else:
                new_name = f"{path_obj.stem}{size_info}.{output_format.lower()}"
            output_path = str(output_parent / new_name)
        
        return output_path, output_format


class ImageResizerWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.selected_files = []  # 所有文件列表
        self.checked_files = set()  # 选中的文件集合（用于处理）
        self.card_widgets = {}  # 文件路径到卡片widget的映射，用于快速更新
        self.process_thread = None
        self.scan_thread = None
        self._init_ui()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.process_thread and self.process_thread.isRunning():
            reply = QMessageBox.question(
                self, "确认", "处理正在进行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                if self.process_thread:
                    self.process_thread.cancel()
                    self.process_thread.wait(3000)  # 等待最多3秒
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
    
    def _init_ui(self):
        """初始化界面"""
        self.setWindowTitle("ImageOPT - 批量图片分辨率缩小工具 v1.0")
        self.setMinimumSize(900, 950)  # 增加窗口高度，确保预览区域完全显示
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. 选择文件/目录区域
        group_select = QGroupBox("1. 选择文件/目录")
        layout_select = QVBoxLayout()
        
        layout_buttons = QHBoxLayout()
        # 递归子目录选项放在最左边
        self.chk_recursive = QCheckBox("递归子目录")
        self.chk_recursive.setChecked(True)
        layout_buttons.addWidget(self.chk_recursive)
        
        self.btn_select_dir = QPushButton("选择目录")
        self.btn_select_dir.clicked.connect(self._select_directory)
        self.btn_select_files = QPushButton("选择图片文件")
        self.btn_select_files.clicked.connect(self._select_files)
        
        # 文件管理按钮
        self.btn_remove_checked = QPushButton("移除选中")
        self.btn_remove_checked.clicked.connect(self._remove_checked_files)
        self.btn_remove_unchecked = QPushButton("移除未选中")
        self.btn_remove_unchecked.clicked.connect(self._remove_unchecked_files)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.clicked.connect(self._clear_selected)
        
        layout_buttons.addWidget(self.btn_select_dir)
        layout_buttons.addWidget(self.btn_select_files)
        layout_buttons.addWidget(self.btn_remove_checked)
        layout_buttons.addWidget(self.btn_remove_unchecked)
        layout_buttons.addWidget(self.btn_clear)
        layout_buttons.addStretch()
        
        layout_select.addLayout(layout_buttons)
        
        self.label_selected = QLabel("已选文件：无")
        layout_select.addWidget(self.label_selected)
        
        # 预览区域（缩略图卡片）- 显示所有，可滚动，包含文件信息
        layout_preview = QVBoxLayout()
        layout_preview.addWidget(QLabel("图片预览（单击切换选中状态，显示所有图片及详细信息）："))
        self.preview_area = QScrollArea()
        self.preview_area.setWidgetResizable(True)
        self.preview_area.setFixedHeight(200)  # 固定高度200px
        self.preview_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preview_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preview_widget = QWidget()
        # 使用网格布局，每行显示多个卡片
        self.preview_layout = QGridLayout(self.preview_widget)
        self.preview_layout.setContentsMargins(5, 5, 5, 5)
        self.preview_layout.setSpacing(10)
        # 设置列拉伸策略，防止单个卡片占满整行
        for i in range(4):  # 最多4列
            self.preview_layout.setColumnStretch(i, 0)  # 不拉伸列
        self.preview_area.setWidget(self.preview_widget)
        layout_preview.addWidget(self.preview_area)
        layout_select.addLayout(layout_preview)
        
        group_select.setLayout(layout_select)
        main_layout.addWidget(group_select)
        
        # 2. 缩放方式区域
        group_resize = QGroupBox("2. 缩放方式（二选一）")
        layout_resize = QVBoxLayout()
        
        # 单选按钮组
        self.resize_mode_group = QButtonGroup()
        
        layout_scale = QHBoxLayout()
        self.radio_scale = QRadioButton("缩放倍数（0<值<=1，如0.5=50%）：")
        self.radio_scale.setChecked(True)
        self.resize_mode_group.addButton(self.radio_scale, 0)
        layout_scale.addWidget(self.radio_scale)
        
        # 缩放倍数拖动条
        self.slider_scale = QSlider(Qt.Horizontal)
        self.slider_scale.setRange(1, 100)  # 0.01-0.99，步长0.01
        self.slider_scale.setValue(50)  # 对应0.5
        self.slider_scale.setTickPosition(QSlider.TicksBelow)
        self.slider_scale.setTickInterval(10)
        self.label_scale_value = QLabel("0.50")
        self.label_scale_value.setMinimumWidth(40)
        self.label_scale_value.setAlignment(Qt.AlignCenter)
        self.slider_scale.valueChanged.connect(lambda v: self.label_scale_value.setText(f"{v/100:.2f}"))
        
        layout_scale.addWidget(self.slider_scale)
        layout_scale.addWidget(self.label_scale_value)
        layout_scale.addStretch()
        layout_resize.addLayout(layout_scale)
        
        layout_width = QHBoxLayout()
        self.radio_width = QRadioButton("目标宽度（像素，高度等比例）：")
        self.resize_mode_group.addButton(self.radio_width, 1)
        layout_width.addWidget(self.radio_width)
        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 99999)
        self.spin_width.setValue(1920)
        layout_width.addWidget(self.spin_width)
        layout_width.addStretch()
        layout_resize.addLayout(layout_width)
        
        group_resize.setLayout(layout_resize)
        main_layout.addWidget(group_resize)
        
        # 输出格式和质量（合并到缩放方式组内）
        layout_output = QHBoxLayout()
        layout_output.addWidget(QLabel("输出格式："))
        self.combo_format = QComboBox()
        self.combo_format.addItems(["原格式", "PNG", "JPG", "WEBP"])
        layout_output.addWidget(self.combo_format)
        
        layout_output.addWidget(QLabel("图片质量（1-100，JPG/WEBP有效）："))
        # 质量拖动条
        self.slider_quality = QSlider(Qt.Horizontal)
        self.slider_quality.setRange(1, 100)
        self.slider_quality.setValue(95)
        self.slider_quality.setTickPosition(QSlider.TicksBelow)
        self.slider_quality.setTickInterval(10)
        self.label_quality_value = QLabel("95")
        self.label_quality_value.setMinimumWidth(40)
        self.label_quality_value.setAlignment(Qt.AlignCenter)
        self.slider_quality.valueChanged.connect(lambda v: self.label_quality_value.setText(str(v)))
        
        layout_output.addWidget(self.slider_quality)
        layout_output.addWidget(self.label_quality_value)
        
        layout_output.addWidget(QLabel("保存方式："))
        self.combo_save_mode = QComboBox()
        self.combo_save_mode.addItems(["覆盖原文件", "生成新文件（带分辨率信息）"])
        layout_output.addWidget(self.combo_save_mode)
        
        layout_output.addStretch()
        layout_resize.addLayout(layout_output)
        
        # 目标目录设置
        layout_output_dir = QHBoxLayout()
        self.chk_use_output_dir = QCheckBox("保存到目标目录：")
        self.chk_use_output_dir.setChecked(False)
        self.chk_use_output_dir.toggled.connect(self._on_output_dir_toggled)
        layout_output_dir.addWidget(self.chk_use_output_dir)
        
        self.edit_output_dir = QLineEdit()
        self.edit_output_dir.setPlaceholderText("留空则保存到原文件目录")
        self.edit_output_dir.setEnabled(False)
        layout_output_dir.addWidget(self.edit_output_dir)
        
        self.btn_select_output_dir = QPushButton("选择目录")
        self.btn_select_output_dir.setEnabled(False)
        self.btn_select_output_dir.clicked.connect(self._select_output_directory)
        layout_output_dir.addWidget(self.btn_select_output_dir)
        
        layout_resize.addLayout(layout_output_dir)
        
        # 3. 筛选条件区域
        group_filter = QGroupBox("3. 筛选条件（可选，留空不筛选）")
        layout_filter = QVBoxLayout()
        
        layout_filter1 = QHBoxLayout()
        layout_filter1.addWidget(QLabel("文件名包含："))
        self.edit_name_contains = QLineEdit()
        layout_filter1.addWidget(self.edit_name_contains)
        layout_filter1.addWidget(QLabel("文件名不包含："))
        self.edit_name_not_contains = QLineEdit()
        layout_filter1.addWidget(self.edit_name_not_contains)
        layout_filter.addLayout(layout_filter1)
        
        layout_filter2 = QHBoxLayout()
        layout_filter2.addWidget(QLabel("文件大小高于（MB）："))
        self.spin_size_min = QDoubleSpinBox()
        self.spin_size_min.setRange(0, 99999)
        self.spin_size_min.setDecimals(2)
        layout_filter2.addWidget(self.spin_size_min)
        layout_filter2.addWidget(QLabel("图片格式（逗号分隔）："))
        self.edit_formats = QLineEdit()
        self.edit_formats.setText("jpg,png,jpeg,bmp,gif")
        layout_filter2.addWidget(self.edit_formats)
        layout_filter.addLayout(layout_filter2)
        
        layout_filter3 = QHBoxLayout()
        layout_filter3.addWidget(QLabel("宽度高于（像素）："))
        self.spin_width_min = QSpinBox()
        self.spin_width_min.setRange(0, 99999)
        layout_filter3.addWidget(self.spin_width_min)
        layout_filter3.addWidget(QLabel("宽度低于（像素）："))
        self.spin_width_max = QSpinBox()
        self.spin_width_max.setRange(0, 99999)
        layout_filter3.addWidget(self.spin_width_max)
        layout_filter.addLayout(layout_filter3)
        
        layout_filter4 = QHBoxLayout()
        layout_filter4.addWidget(QLabel("高度高于（像素）："))
        self.spin_height_min = QSpinBox()
        self.spin_height_min.setRange(0, 99999)
        layout_filter4.addWidget(self.spin_height_min)
        layout_filter4.addWidget(QLabel("高度低于（像素）："))
        self.spin_height_max = QSpinBox()
        self.spin_height_max.setRange(0, 99999)
        layout_filter4.addWidget(self.spin_height_max)
        layout_filter.addLayout(layout_filter4)
        
        group_filter.setLayout(layout_filter)
        main_layout.addWidget(group_filter)
        
        # 4. 执行处理区域
        group_process = QGroupBox("4. 执行处理")
        layout_process = QVBoxLayout()
        
        layout_buttons_process = QHBoxLayout()
        self.btn_start = QPushButton("开始处理")
        self.btn_start.clicked.connect(self._start_process)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.btn_cancel = QPushButton("终止处理")
        self.btn_cancel.clicked.connect(self._cancel_process)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        layout_buttons_process.addWidget(self.btn_start)
        layout_buttons_process.addWidget(self.btn_cancel)
        layout_process.addLayout(layout_buttons_process)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout_process.addWidget(self.progress_bar)
        
        # 处理状态文本
        self.label_status = QLabel("就绪")
        self.label_status.setAlignment(Qt.AlignCenter)
        layout_process.addWidget(self.label_status)
        
        group_process.setLayout(layout_process)
        main_layout.addWidget(group_process)
        
        # 5. 处理日志区域
        group_log = QGroupBox("5. 处理日志")
        layout_log = QVBoxLayout()
        
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setFont(QFont("Consolas", 9))
        layout_log.addWidget(self.text_log)
        
        group_log.setLayout(layout_log)
        main_layout.addWidget(group_log)
        
        # 设置布局比例
        main_layout.setStretchFactor(group_select, 1)
        main_layout.setStretchFactor(group_resize, 0)
        main_layout.setStretchFactor(group_filter, 0)
        main_layout.setStretchFactor(group_process, 0)
        main_layout.setStretchFactor(group_log, 2)
    
    def _select_directory(self):
        """选择目录（使用线程扫描，避免卡死）"""
        directory = QFileDialog.getExistingDirectory(self, "选择图片目录")
        if directory:
            recursive = self.chk_recursive.isChecked()
            self._log(f"🔍 开始扫描目录：{directory}（{'递归' if recursive else '不递归'}）...")
            
            # 禁用按钮，显示扫描中
            self.btn_select_dir.setEnabled(False)
            self.btn_select_files.setEnabled(False)
            self.label_selected.setText("扫描中，请稍候...")
            
            # 创建并启动扫描线程
            if self.scan_thread and self.scan_thread.isRunning():
                self.scan_thread.cancel()
                self.scan_thread.wait(1000)
            
            self.scan_thread = FileScanThread(directory, recursive)
            self.scan_thread.scan_progress.connect(self._log)
            self.scan_thread.scan_finished.connect(self._on_scan_finished)
            self.scan_thread.start()
    
    def _on_scan_finished(self, files: List[str]):
        """扫描完成回调"""
        self.selected_files = files
        # 新选择的文件默认全部选中（确保checked_files是selected_files的子集）
        self.checked_files = set(files)
        self._update_selected_label()
        self._update_preview()
        self._log(f"✅ 扫描完成，找到 {len(self.selected_files)} 个图片文件（已全部选中）")
        self.btn_select_dir.setEnabled(True)
        self.btn_select_files.setEnabled(True)
    
    def _select_files(self):
        """选择图片文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片文件", "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp *.gif *.webp);;所有文件 (*.*)"
        )
        if files:
            # 过滤图片格式
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
            new_files = [
                f for f in files 
                if Path(f).suffix.lower() in image_extensions
            ]
            # 添加到文件列表（去重）
            for f in new_files:
                if f not in self.selected_files:
                    self.selected_files.append(f)
            # 新选择的文件默认全部选中（确保checked_files是selected_files的子集）
            self.checked_files.update(new_files)
            # 清理不在selected_files中的checked_files
            self.checked_files = {f for f in self.checked_files if f in self.selected_files}
            self._update_selected_label()
            self._update_preview()
            self._log(f"✅ 选择 {len(new_files)} 个图片文件（已全部选中）")
    
    def _get_all_image_files(self, directory: str, recursive: bool) -> List[str]:
        """获取目录下所有图片文件"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
        image_files = []
        
        if recursive:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if Path(file).suffix.lower() in image_extensions:
                        image_files.append(os.path.join(root, file))
        else:
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path) and Path(file).suffix.lower() in image_extensions:
                    image_files.append(file_path)
        
        return sorted(list(set(image_files)))  # 去重并排序
    
    def _update_selected_label(self):
        """更新已选文件标签（修复统计错误）"""
        total_count = len(self.selected_files)
        # 确保checked_files只包含selected_files中的文件
        self.checked_files = {f for f in self.checked_files if f in self.selected_files}
        checked_count = len(self.checked_files)
        unchecked_count = total_count - checked_count
        
        if total_count == 0:
            self.label_selected.setText("已选文件：无")
        else:
            self.label_selected.setText(f"已选文件：{total_count} 个 | 选中：{checked_count} 个 | 未选中：{unchecked_count} 个")
    
    def _clear_selected(self):
        """清空所有文件"""
        self.selected_files = []
        self.checked_files.clear()
        self.card_widgets.clear()  # 清空卡片字典
        self._update_selected_label()
        self._update_preview()
        self._log("已清空所有文件")
    
    def _remove_checked_files(self):
        """移除选中的文件（优化：批量移除卡片）"""
        # 确保只移除在selected_files中的文件
        to_remove = [f for f in self.checked_files if f in self.selected_files]
        if not to_remove:
            QMessageBox.information(self, "提示", "没有选中的文件")
            return
        
        removed_count = len(to_remove)
        # 移除对应的卡片widget
        for file_path in to_remove:
            if file_path in self.card_widgets:
                card = self.card_widgets[file_path]
                card.setParent(None)
                del self.card_widgets[file_path]
        
        # 从文件列表中移除
        self.selected_files = [f for f in self.selected_files if f not in to_remove]
        self.checked_files -= set(to_remove)
        self._update_selected_label()
        self._log(f"已移除 {removed_count} 个选中的文件")
    
    def _remove_unchecked_files(self):
        """移除未选中的文件（优化：批量移除卡片）"""
        unchecked = set(self.selected_files) - self.checked_files
        if not unchecked:
            QMessageBox.information(self, "提示", "没有未选中的文件")
            return
        
        removed_count = len(unchecked)
        # 移除对应的卡片widget
        for file_path in unchecked:
            if file_path in self.card_widgets:
                card = self.card_widgets[file_path]
                card.setParent(None)
                del self.card_widgets[file_path]
        
        # 只保留选中的文件
        self.selected_files = list(self.checked_files)
        self._update_selected_label()
        self._log(f"已移除 {removed_count} 个未选中的文件")
    
    def _toggle_file_check(self, file_path: str):
        """切换文件选中状态（优化：只更新单个卡片，不重建所有）"""
        # 确保文件在selected_files中
        if file_path not in self.selected_files:
            return
        
        # 切换选中状态
        if file_path in self.checked_files:
            self.checked_files.remove(file_path)
        else:
            self.checked_files.add(file_path)
        
        # 只更新当前卡片的样式，不重建所有卡片
        self._update_card_style(file_path)
        self._update_selected_label()
    
    def _update_card_style(self, file_path: str):
        """更新单个卡片的样式（优化性能）"""
        if file_path not in self.card_widgets:
            return
        
        card = self.card_widgets[file_path]
        is_checked = file_path in self.checked_files
        
        # 更新卡片样式
        if is_checked:
            card_style = """
                QFrame {
                    border: 2px solid #0078d4;
                    border-radius: 5px;
                    background-color: #e3f2fd;
                    padding: 5px;
                }
                QFrame:hover {
                    border: 2px solid #005a9e;
                    background-color: #bbdefb;
                }
            """
        else:
            card_style = """
                QFrame {
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    background-color: #f9f9f9;
                    padding: 5px;
                }
                QFrame:hover {
                    border: 2px solid #0078d4;
                    background-color: #f0f0f0;
                }
            """
        card.setStyleSheet(card_style)
        
        # 更新选中状态标签
        # 查找选中状态标签（通常是第4或第5个子widget）
        layout = card.layout()
        if layout:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item:
                    widget = item.widget()
                    if isinstance(widget, QLabel) and ("已选中" in widget.text() or "未选中" in widget.text()):
                        widget.setText("✓ 已选中" if is_checked else "○ 未选中")
                        if is_checked:
                            widget.setStyleSheet("font-size: 9px; color: #0078d4; font-weight: bold;")
                        else:
                            widget.setStyleSheet("font-size: 9px; color: #999;")
                        break
    
    def _update_preview(self):
        """更新预览区域（显示所有缩略图卡片，包含文件信息）"""
        # 清空现有预览
        for i in reversed(range(self.preview_layout.count())):
            item = self.preview_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.setParent(None)
        
        # 显示所有文件的预览卡片
        row = 0
        col = 0
        cols_per_row = 4  # 每行显示4个卡片
        
        for file_path in self.selected_files:
            try:
                # 创建卡片容器
                card = QFrame()
                card.setFrameShape(QFrame.Box)
                
                # 判断是否选中
                is_checked = file_path in self.checked_files
                
                # 根据选中状态设置样式
                if is_checked:
                    card_style = """
                        QFrame {
                            border: 2px solid #0078d4;
                            border-radius: 5px;
                            background-color: #e3f2fd;
                            padding: 5px;
                        }
                        QFrame:hover {
                            border: 2px solid #005a9e;
                            background-color: #bbdefb;
                        }
                    """
                else:
                    card_style = """
                        QFrame {
                            border: 1px solid #ccc;
                            border-radius: 5px;
                            background-color: #f9f9f9;
                            padding: 5px;
                        }
                        QFrame:hover {
                            border: 2px solid #0078d4;
                            background-color: #f0f0f0;
                        }
                    """
                card.setStyleSheet(card_style)
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(5, 5, 5, 5)
                card_layout.setSpacing(3)
                
                # 加载图片
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    # 缩略图
                    scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    image_label = QLabel()
                    image_label.setPixmap(scaled_pixmap)
                    image_label.setAlignment(Qt.AlignCenter)
                    image_label.setFixedSize(150, 150)
                    image_label.setStyleSheet("background-color: white; border: 1px solid #ddd;")
                    card_layout.addWidget(image_label)
                    
                    # 获取文件信息
                    file_name = os.path.basename(file_path)
                    file_ext = Path(file_path).suffix.upper()
                    file_size = os.path.getsize(file_path)
                    size_mb = file_size / (1024 * 1024)
                    
                    # 获取图片尺寸
                    try:
                        with Image.open(file_path) as img:
                            width, height = img.size
                            resolution_text = f"{width}×{height}"
                    except Exception:
                        resolution_text = "未知"
                    
                    # 文件名（截断过长的）
                    display_name = file_name if len(file_name) <= 20 else file_name[:17] + "..."
                    name_label = QLabel(display_name)
                    name_label.setToolTip(file_name)
                    name_label.setWordWrap(True)
                    name_label.setAlignment(Qt.AlignCenter)
                    name_label.setStyleSheet("font-weight: bold; font-size: 10px;")
                    card_layout.addWidget(name_label)
                    
                    # 格式和大小
                    format_size_label = QLabel(f"{file_ext} | {size_mb:.2f}MB")
                    format_size_label.setAlignment(Qt.AlignCenter)
                    format_size_label.setStyleSheet("font-size: 9px; color: #666;")
                    card_layout.addWidget(format_size_label)
                    
                    # 分辨率
                    resolution_label = QLabel(f"分辨率: {resolution_text}")
                    resolution_label.setAlignment(Qt.AlignCenter)
                    resolution_label.setStyleSheet("font-size: 9px; color: #666;")
                    card_layout.addWidget(resolution_label)
                    
                    # 选中状态指示
                    check_label = QLabel("✓ 已选中" if is_checked else "○ 未选中")
                    check_label.setAlignment(Qt.AlignCenter)
                    if is_checked:
                        check_label.setStyleSheet("font-size: 9px; color: #0078d4; font-weight: bold;")
                    else:
                        check_label.setStyleSheet("font-size: 9px; color: #999;")
                    card_layout.addWidget(check_label)
                    
                    # 移除按钮
                    btn_remove = QPushButton("移除")
                    btn_remove.setStyleSheet("""
                        QPushButton {
                            background-color: #f44336;
                            color: white;
                            border: none;
                            border-radius: 3px;
                            padding: 3px;
                            font-size: 9px;
                        }
                        QPushButton:hover {
                            background-color: #d32f2f;
                        }
                    """)
                    btn_remove.clicked.connect(lambda checked, path=file_path: self._remove_file(path))
                    card_layout.addWidget(btn_remove)
                    
                    # 单击切换选中状态
                    def make_click_handler(path):
                        def handler(event):
                            if event.button() == Qt.LeftButton:
                                self._toggle_file_check(path)
                        return handler
                    card.mousePressEvent = make_click_handler(file_path)
                    
                    # 设置卡片固定宽度，防止单个卡片占满整行
                    card.setMaximumWidth(180)  # 卡片最大宽度
                    card.setMinimumWidth(180)  # 卡片最小宽度
                    
                    # 添加到网格布局
                    self.preview_layout.addWidget(card, row, col)
                    # 保存卡片引用，用于快速更新
                    self.card_widgets[file_path] = card
                    
                    # 更新行列位置
                    col += 1
                    if col >= cols_per_row:
                        col = 0
                        row += 1
            except Exception as e:
                # 如果加载失败，创建一个错误卡片
                error_card = QFrame()
                error_card.setFrameShape(QFrame.Box)
                error_card.setStyleSheet("border: 1px solid #f00; background-color: #ffe0e0; padding: 5px;")
                error_layout = QVBoxLayout(error_card)
                error_label = QLabel(f"加载失败\n{os.path.basename(file_path)}")
                error_label.setAlignment(Qt.AlignCenter)
                error_label.setWordWrap(True)
                error_layout.addWidget(error_label)
                
                # 选中状态
                is_checked = file_path in self.checked_files
                check_label = QLabel("✓ 已选中" if is_checked else "○ 未选中")
                check_label.setAlignment(Qt.AlignCenter)
                if is_checked:
                    check_label.setStyleSheet("font-size: 9px; color: #f00; font-weight: bold;")
                else:
                    check_label.setStyleSheet("font-size: 9px; color: #999;")
                error_layout.addWidget(check_label)
                
                # 移除按钮
                btn_remove = QPushButton("移除")
                btn_remove.setStyleSheet("""
                    QPushButton {
                        background-color: #f44336;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        padding: 3px;
                        font-size: 9px;
                    }
                    QPushButton:hover {
                        background-color: #d32f2f;
                    }
                """)
                btn_remove.clicked.connect(lambda checked, path=file_path: self._remove_file(path))
                error_layout.addWidget(btn_remove)
                
                # 单击切换选中状态
                def make_click_handler(path):
                    def handler(event):
                        if event.button() == Qt.LeftButton:
                            self._toggle_file_check(path)
                    return handler
                error_card.mousePressEvent = make_click_handler(file_path)
                
                # 更新错误卡片样式
                if is_checked:
                    error_card.setStyleSheet("border: 2px solid #f00; background-color: #ffe0e0; padding: 5px;")
                else:
                    error_card.setStyleSheet("border: 1px solid #f00; background-color: #ffe0e0; padding: 5px;")
                
                # 设置错误卡片固定宽度，防止单个卡片占满整行
                error_card.setMaximumWidth(180)
                error_card.setMinimumWidth(180)
                
                self.preview_layout.addWidget(error_card, row, col)
                col += 1
                if col >= cols_per_row:
                    col = 0
                    row += 1
    
    def _remove_file(self, file_path: str):
        """移除单个文件（优化：只移除对应卡片，不重建所有）"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self.checked_files.discard(file_path)  # 从选中集合中移除
            
            # 只移除对应的卡片widget
            if file_path in self.card_widgets:
                card = self.card_widgets[file_path]
                card.setParent(None)
                del self.card_widgets[file_path]
            
            self._update_selected_label()
            self._log(f"已移除：{os.path.basename(file_path)}")
    
    def _filter_files(self, files: List[str]) -> List[str]:
        """多条件筛选文件"""
        filtered = files.copy()
        
        # 文件名筛选
        name_contains = self.edit_name_contains.text().strip()
        if name_contains:
            filtered = [f for f in filtered if name_contains.lower() in os.path.basename(f).lower()]
        
        name_not_contains = self.edit_name_not_contains.text().strip()
        if name_not_contains:
            filtered = [f for f in filtered if name_not_contains.lower() not in os.path.basename(f).lower()]
        
        # 格式筛选
        formats_text = self.edit_formats.text().strip()
        if formats_text:
            formats = [f.strip().lower() for f in formats_text.split(',')]
            formats = [f if f.startswith('.') else f'.{f}' for f in formats]
            filtered = [f for f in filtered if Path(f).suffix.lower() in formats]
        
        # 文件大小筛选
        size_min = self.spin_size_min.value()
        if size_min > 0:
            filtered = [f for f in filtered if os.path.getsize(f) / (1024 * 1024) > size_min]
        
        # 像素尺寸筛选
        width_min = self.spin_width_min.value()
        width_max = self.spin_width_max.value()
        height_min = self.spin_height_min.value()
        height_max = self.spin_height_max.value()
        
        if width_min > 0 or width_max > 0 or height_min > 0 or height_max > 0:
            size_filtered = []
            for file_path in filtered:
                try:
                    with Image.open(file_path) as img:
                        width, height = img.size
                        if width_min > 0 and width <= width_min:
                            continue
                        if width_max > 0 and width >= width_max:
                            continue
                        if height_min > 0 and height <= height_min:
                            continue
                        if height_max > 0 and height >= height_max:
                            continue
                        size_filtered.append(file_path)
                except Exception:
                    continue
            filtered = size_filtered
        
        return filtered
    
    def _start_process(self):
        """开始处理"""
        if not self.selected_files:
            QMessageBox.warning(self, "警告", "请先选择图片文件或目录！")
            return
        
        # 确定缩放方式
        if self.radio_scale.isChecked():
            scale_value = self.slider_scale.value() / 100.0  # 从拖动条获取值（1-99对应0.01-0.99）
            if scale_value <= 0 or scale_value > 1:
                QMessageBox.warning(self, "警告", "缩放倍数必须在0到1之间（不包含0和1）！")
                return
            resize_mode = 'scale'
            resize_value = scale_value
        else:  # radio_width is checked
            width_value = self.spin_width.value()
            if width_value <= 0:
                QMessageBox.warning(self, "警告", "目标宽度必须大于0！")
                return
            resize_mode = 'width'
            resize_value = width_value
        
        # 只处理选中的文件，然后筛选
        files_to_process = list(self.checked_files)
        filtered_files = self._filter_files(files_to_process)
        if not filtered_files:
            QMessageBox.warning(self, "警告", "筛选后没有符合条件的文件！")
            return
        
        self._log(f"🔍 全条件筛选后共 {len(filtered_files)} 个文件待处理")
        
        # 获取输出设置
        format_map = {"原格式": "original", "PNG": "png", "JPG": "jpg", "WEBP": "webp"}
        output_format = format_map[self.combo_format.currentText()]
        quality = self.slider_quality.value()  # 从拖动条获取值
        save_mode_map = {"覆盖原文件": "overwrite", "生成新文件（带分辨率信息）": "new_file"}
        output_mode = save_mode_map[self.combo_save_mode.currentText()]
        
        # 获取目标目录
        output_dir = None
        if self.chk_use_output_dir.isChecked():
            output_dir = self.edit_output_dir.text().strip()
            if not output_dir:
                QMessageBox.warning(self, "警告", "请选择目标目录！")
                return
            if not os.path.isdir(output_dir):
                QMessageBox.warning(self, "警告", "目标目录不存在！")
                return
        
        # 禁用按钮和文件选择
        self.btn_start.setEnabled(False)
        self.btn_start.setText("处理中...")
        self.btn_cancel.setEnabled(True)
        self.btn_select_dir.setEnabled(False)
        self.btn_select_files.setEnabled(False)
        self.chk_recursive.setEnabled(False)
        self.slider_scale.setEnabled(False)
        self.slider_quality.setEnabled(False)
        self.radio_scale.setEnabled(False)
        self.radio_width.setEnabled(False)
        self.spin_width.setEnabled(False)
        self.progress_bar.setValue(0)
        self.label_status.setText(f"准备处理 {len(filtered_files)} 个文件...")
        
        # 创建并启动处理线程
        self.process_thread = ImageProcessThread(
            filtered_files, resize_mode, resize_value, output_format, quality, output_mode, output_dir
        )
        self.process_thread.progress_update.connect(self._update_progress)
        self.process_thread.log_update.connect(self._log)
        self.process_thread.finish_signal.connect(self._on_process_finished)
        self.process_thread.start()
    
    def _update_progress(self, current: int, total: int):
        """更新进度条"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
            self.label_status.setText(f"处理中：{current}/{total} ({progress}%)")
    
    def _on_process_finished(self, success: int, fail: int):
        """处理完成回调"""
        self.btn_start.setEnabled(True)
        self.btn_start.setText("开始处理")
        self.btn_cancel.setEnabled(False)
        self.btn_select_dir.setEnabled(True)
        self.btn_select_files.setEnabled(True)
        self.chk_recursive.setEnabled(True)
        self.slider_scale.setEnabled(True)
        self.slider_quality.setEnabled(True)
        self.radio_scale.setEnabled(True)
        self.radio_width.setEnabled(True)
        self.spin_width.setEnabled(True)
        self.label_status.setText(f"完成：成功 {success} 个，失败 {fail} 个")
        QMessageBox.information(self, "完成", f"处理完成！\n成功：{success} 个\n失败：{fail} 个")
    
    def _on_output_dir_toggled(self, checked: bool):
        """目标目录复选框切换"""
        self.edit_output_dir.setEnabled(checked)
        self.btn_select_output_dir.setEnabled(checked)
    
    def _select_output_directory(self):
        """选择目标目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择目标目录")
        if directory:
            self.edit_output_dir.setText(directory)
    
    def _cancel_process(self):
        """取消处理"""
        if self.process_thread and self.process_thread.isRunning():
            reply = QMessageBox.question(
                self, "确认", "确定要终止当前处理吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.process_thread.cancel()
                self._log("⚠️ 用户请求终止处理...")
    
    def _log(self, message: str):
        """添加日志"""
        self.text_log.append(message)
        # 自动滚动到底部
        scrollbar = self.text_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    """主程序入口"""
    # 高DPI适配（必须在QApplication创建之前）
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # 设置应用信息
    app.setApplicationName("ImageOPT")
    app.setApplicationVersion("1.0")
    
    # 创建主窗口
    window = ImageResizerWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

