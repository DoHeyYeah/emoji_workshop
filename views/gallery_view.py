from pathlib import Path
from typing import List
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QFileDialog,
    QMessageBox, QProgressBar, QComboBox, QAbstractItemView, QMenu
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon

from services.database_service import DatabaseService
from services.thumbnail_service import ThumbnailService
from services.clipboard_service import ClipboardService
from models.image_model import ImageModel
from utils.file_scanner import FileScanner
from utils.config_manager import ConfigManager
class ThumbnailWorker(QThread):
    """生成缩略图"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal()
    def __init__(self, thumb_service: ThumbnailService, image_models: list):
        super().__init__()
        self.thumb_service = thumb_service
        self.image_models = image_models
    def run(self):
        total = len(self.image_models)
        for i, model in enumerate(self.image_models):
            if not model.thumbnail_path or not Path(model.thumbnail_path).exists():
                thumb_path = self.thumb_service.get_thumbnail(model.file_path)
                if thumb_path:
                    model.thumbnail_path = thumb_path
            self.progress.emit(i + 1, total)
        self.finished.emit()
class GalleryView(QWidget):
    """画廊视图"""
    THUMBNAIL_SIZE = 128
    images_selection_changed = pyqtSignal(list)  # 单/多选信号，发出所有选中的 image_id 列表
    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.thumb_service = ThumbnailService()
        self.config = ConfigManager()
        self.current_images: list[ImageModel] = []
        self._pending_models: list = []
        self.setAcceptDrops(True)
        self.setup_ui()
        self.load_from_database()
    def setup_ui(self):
        layout = QVBoxLayout(self)
        #搜索栏
        search_layout = QHBoxLayout()
        self.search_input = QComboBox()
        self.search_input.setEditable(True)
        self.search_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.search_input.lineEdit().returnPressed.connect(self.do_search)
        self._refresh_search_history()
        self.search_btn = QPushButton("🔍搜索")
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.clicked.connect(self.do_search)
        self.reset_btn = QPushButton("🔄重置")
        self.reset_btn.setObjectName("primaryButton")
        self.reset_btn.clicked.connect(self.reset_search)
        self.clear_history_btn = QPushButton("🧹清空历史")
        self.clear_history_btn.setObjectName("dangerButton")
        self.clear_history_btn.clicked.connect(self._clear_search_history)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.reset_btn)
        search_layout.addWidget(self.clear_history_btn)
        layout.addLayout(search_layout)
        #工具栏
        toolbar = QHBoxLayout()
        self.import_btn = QPushButton("📁导入文件夹")
        self.import_btn.setObjectName("primaryButton")
        self.import_btn.clicked.connect(self.import_folder)
        self.clear_btn = QPushButton("🗑️清空")
        self.clear_btn.setObjectName("dangerButton")
        self.clear_btn.clicked.connect(self.clear_all)
        self.stats_label = QLabel("图片: 0 | 总大小: 0 MB | 缓存: 0")
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.clear_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.stats_label)
        layout.addLayout(toolbar)
        #进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        # 缩略图
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("thumbList")
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_image_context_menu)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)
        #信息栏
        self.info_label = QLabel("就绪")
        layout.addWidget(self.info_label)
    def _refresh_search_history(self, current_text: str = ""):
        """保留搜索历史记录"""
        self.search_input.clear()
        for kw in self.config.get_search_history():
            self.search_input.addItem(kw)
        self.search_input.setEditText(current_text)
        self.search_input.lineEdit().setPlaceholderText("🔍搜索")
    def do_search(self):
        """搜索"""
        keyword = self.search_input.currentText().strip()
        if not keyword:
            self.load_from_database()
            return
        self.config.add_search_history(keyword)
        self._refresh_search_history(keyword)
        self.list_widget.clear()
        self.current_images = []
        rows = self.db.search_images_by_name(keyword)
        for row in rows:
            model = ImageModel.from_db_row(row)
            self.current_images.append(model)
            self._add_thumbnail(model)
        self.info_label.setText(f"搜索'{keyword}'找到{len(rows)}张")
        self.update_stats()
    def reset_search(self):
        """重置搜索"""
        self._refresh_search_history()
        self.load_from_database()
        self.info_label.setText("已重置搜索")
    def _clear_search_history(self):
        """清空搜索历史"""
        history = self.config.get_search_history()
        n = len(history)
        if n == 0:
            self.info_label.setText("暂无搜索历史")
            return
        reply = QMessageBox.question(
            self,
            "确认清空",
            f"确认清空{n}条搜索历史？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        current_text = self.search_input.currentText().strip()
        self.config.clear_search_history()
        self._refresh_search_history(current_text)
        self.info_label.setText("已清空搜索历史")
    def _import_single_image(self, file_path: str) -> bool:
        """导入单张图片，返回是否成功"""
        info = FileScanner.get_image_info(file_path)
        if not info:
            return False
        image_id = self.db.add_image(**info)
        return image_id is not None
    def import_folder(self):
        """导入文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择表情包文件夹")
        if not folder:
            return
        self._pending_models = []
        added_count = self.import_folder_path(folder)
        # 记录最近文件夹
        self.config.add_recent_folder(folder)
        if added_count == 0:
            QMessageBox.information(self, "提示", "未找到支持的图片文件")
            return
        self.info_label.setText(f"成功导入{added_count}张图片，正在生成缩略图...")
        self._generate_thumbnails_async(self._pending_models)
    def import_folder_path(self, folder: str) -> int:
        """扫描入库"""
        self.info_label.setText("正在扫描文件夹...")
        QApplication.processEvents()
        images_info = FileScanner.scan_folder(folder)
        if not images_info:
            return 0
        added_count = 0
        self._pending_models = []
        for info in images_info:
            image_id = self.db.add_image(**info)
            if image_id:
                added_count += 1
                model = ImageModel(
                    id=image_id,
                    name=info['name'],
                    file_path=info['file_path'],
                    file_type=info['file_type'],
                    file_size=info['file_size'],
                    width=info['width'],
                    height=info['height']
                )
                self._pending_models.append(model)
        return added_count
    def _generate_thumbnails_async(self, models: list):
        """生成缩略图"""
        if not models:
            self.load_from_database()
            return
        self.progress_bar.setMaximum(len(models))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.import_btn.setEnabled(False)
        self.worker = ThumbnailWorker(self.thumb_service, models)
        self.worker.progress.connect(self._on_thumb_progress)
        self.worker.finished.connect(self._on_thumb_finished)
        self.worker.start()
    def _on_thumb_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        self.info_label.setText(f"生成缩略图:{current}/{total}")
    def _on_thumb_finished(self):
        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(True)
        self.info_label.setText("缩略图生成完成")
        self.load_from_database()
        self.update_stats()
    def load_from_database(self):
        """全量刷新"""
        self.list_widget.clear()
        self.current_images = []
        rows = self.db.get_all_images()
        for row in rows:
            model = ImageModel.from_db_row(row)
            self.current_images.append(model)
            self._add_thumbnail(model)
        self.update_stats()
    def _add_thumbnail(self, model: ImageModel):
        """添加缩略图"""
        item = QListWidgetItem()
        item.setText(model.display_name)
        item.setData(Qt.ItemDataRole.UserRole, model.id)
        thumb_path = None
        if model.thumbnail_path and Path(model.thumbnail_path).exists():
            thumb_path = model.thumbnail_path
        else:
            thumb_path = self.thumb_service.get_thumbnail(model.file_path)
            if thumb_path:
                model.thumbnail_path = thumb_path
        if thumb_path:
            pixmap = QPixmap(thumb_path)
        else:
            pixmap = QPixmap(model.file_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            item.setIcon(QIcon(scaled))
        self.list_widget.addItem(item)
    def on_item_clicked(self, item: QListWidgetItem):
        """点击缩略图"""
        image_id = item.data(Qt.ItemDataRole.UserRole)
        model = next((m for m in self.current_images if m.id == image_id), None)
        if not model:
            return 
        size_mb = model.file_size / (1024 * 1024)
        self.info_label.setText(
            f"{model.name} | {model.width}x{model.height} | {size_mb:.2f} MB | {model.file_type.upper()}"
        ) 
    def _on_selection_changed(self):
        """信息信号发射"""
        selected_items = self.list_widget.selectedItems()
        selected_ids = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        self.images_selection_changed.emit(selected_ids)
        if len(selected_ids) == 1:
            self.on_item_clicked(selected_items[0])
            return
        if len(selected_ids) > 1:
            self.info_label.setText(f"已选中{len(selected_ids)}张图片")
        else:
            self.info_label.setText("未选中图片")
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击复制图片到剪贴板"""
        image_id = item.data(Qt.ItemDataRole.UserRole)
        model = next((m for m in self.current_images if m.id == image_id), None)
        if not model:
            return
        if ClipboardService.copy_image(model.file_path):
            self.db.record_usage(image_id)
            msg = "已复制 + 已记录使用"
            # 状态栏显示通知
            main_win = self.window()
            if hasattr(main_win, 'statusBar'):
                main_win.statusBar().showMessage(msg, 2000)
    def _show_image_context_menu(self, position):
        """缩略图右键删除"""
        item = self.list_widget.itemAt(position)
        if item and not item.isSelected():
            self.list_widget.setCurrentItem(item)
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("🗑️删除选中图片")
        action = menu.exec(self.list_widget.viewport().mapToGlobal(position))
        if action == delete_action:
            self._delete_selected_images()
    def _delete_selected_images(self):
        """删除图片库中图片库记录和关联标签。"""
        selected_items = self.list_widget.selectedItems()
        image_ids = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        image_ids = [image_id for image_id in image_ids if image_id is not None]
        if not image_ids:
            return
        count = len(image_ids)
        reply = QMessageBox.question(
            self,
            "删除图片记录",
            f"确定从图片库删除选中的{count}张图片吗？\n\n"
            "这会删除图片库记录和标签关联，不会删除原始图片文件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        deleted = 0
        for image_id in image_ids:
            if self.db.delete_image(image_id):
                deleted += 1
        self.load_from_database()
        self.info_label.setText(f"已删除{deleted}张图片记录")
        self.images_selection_changed.emit([])
        main_win = self.window()
        if hasattr(main_win, 'statusBar'):
            main_win.statusBar().showMessage(f"已删除{deleted}张图片记录", 2000)
    def dragEnterEvent(self, event):
        """接受含URL的拖拽事件"""
        urls = event.mimeData().urls()
        if urls and all(url.isLocalFile() for url in urls):
            event.acceptProposedAction()
        else:
            event.ignore()
    def dropEvent(self, event):
        """处理拖拽放入"""
        supported_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        if not urls:
            event.ignore()
            return
        added_count = 0
        all_models = []
        for url in urls:
            path = Path(url.toLocalFile())
            if path.is_dir():
                count = self.import_folder_path(str(path))
                added_count += count
                all_models.extend(self._pending_models)
                self.config.add_recent_folder(str(path))
            elif path.is_file() and path.suffix.lower() in supported_exts:
                if self._import_single_image(str(path)):
                    added_count += 1
        if added_count > 0:
            self.info_label.setText(f"已导入{added_count}张图片")
            if all_models:
                self._generate_thumbnails_async(all_models)
            else:
                self.load_from_database()
        else:
            self.load_from_database()
            self.info_label.setText("拖入完成")
        event.acceptProposedAction()
    def filter_by_tag_names(self, tag_names: List[str], match_mode: str = "union"):
        """按标签筛选，支持并集/交集"""
        if not tag_names:
            self.load_from_database()
            return
        self.list_widget.clear()
        self.current_images = []
        if match_mode == "intersect":
            rows = self.db.get_images_by_tags_intersect(tag_names)
        else:
            rows = self.db.get_images_by_tags_union(tag_names)
        for row in rows:
            model = ImageModel.from_db_row(
                (
                    row["id"],
                    row["name"],
                    row["file_path"],
                    row["file_type"],
                    row["file_size"],
                    row["width"],
                    row["height"],
                    row.get("thumbnail_path"),
                )
            )
            self.current_images.append(model)
            self._add_thumbnail(model)
        mode_cn = "交集" if match_mode == "intersect" else "并集"
        self.info_label.setText(f"标签筛选（{mode_cn}）:{len(rows)}张")
        self.update_stats()
    def clear_all(self):
        """清空"""
        reply = QMessageBox.question(
            self, "确认", "确定清空所有图片记录吗？\n（不会删除原文件，但会清除缩略图缓存）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_all()
            self.thumb_service.clear_cache()
            self.load_from_database()
            self.info_label.setText("已清空")
    def update_stats(self):
        """更新统计"""
        stats = self.db.get_stats()
        size_mb = stats["total_size"] / (1024 * 1024)
        cache_count = self.thumb_service.get_cache_size()
        self.stats_label.setText(
            f"图片: {stats['count']} | 总大小: {size_mb:.2f} MB | 缓存: {cache_count}"
        )