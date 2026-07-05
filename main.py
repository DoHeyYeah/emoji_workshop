import sys
import time
import logging
from pathlib import Path
def get_resource_path(relative_path: str) -> Path:
    """获取资源文件绝对路径，兼容 PyInstaller 打包与源码运行"""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path
sys.path.insert(0, str(Path(__file__).parent))
from PyQt6.QtWidgets import (
    QDialog,
    QApplication,
    QMainWindow,
    QHBoxLayout,
    QWidget,
    QVBoxLayout,
    QMessageBox,
    QSplitter,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon
from views.gallery_view import GalleryView
from views.tag_panel import TagPanel
from views.stats_panel import StatsPanel
from views.settings_dialog import SettingsDialog
from views.ai_generate_dialog import AIGenerateDialog
from views.recommend_panel import RecommendPanel
from views.report_view import ReportDialog
from services.database_service import DatabaseService
from services.clipboard_monitor import ClipboardMonitor
from utils.config_manager import ConfigManager
from utils.file_scanner import FileScanner
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
class MainWindow(QMainWindow):
    """表情工坊主窗口"""
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.config.increment_stat("launch_count")
        self.setObjectName("mainWindow")
        self.setWindowTitle("表情工坊 - 智能管理系统")
        self.setMinimumSize(800, 600)
        self._restore_window_state()
        self.db_service = DatabaseService()
        self._setup_menu()
        self._setup_ui()
        self.clipboard_monitor = ClipboardMonitor()
        self.clipboard_monitor.new_image_detected.connect(self._on_new_clipboard_image)
        if self.config.get("behavior.clipboard_monitor_enabled", False):
            self.clipboard_monitor.start()
        self.statusBar().showMessage("就绪")
    def _restore_window_state(self):
        """从配置恢复窗口位置和大小"""
        width = self.config.get("window.width", 1000)
        height = self.config.get("window.height", 650)
        pos_x = self.config.get("window.pos_x", 100)
        pos_y = self.config.get("window.pos_y", 100)
        maximized = self.config.get("window.maximized", False)
        self.setGeometry(pos_x, pos_y, width, height)
        if maximized:
            self.showMaximized()
    def _setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        ai_action = QAction("🎨AI生成表情包", self)
        ai_action.setShortcut("Ctrl+G")
        ai_action.triggered.connect(self._open_ai_dialog)
        file_menu.addAction(ai_action)
        file_menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        view_menu = menubar.addMenu("视图")
        stats_action = QAction("📊数据统计", self)
        stats_action.setShortcut("Ctrl+T")
        stats_action.triggered.connect(self._toggle_stats_panel)
        view_menu.addAction(stats_action)
        report_action = QAction("📝性格画像报告", self)
        report_action.setShortcut("Ctrl+R")
        report_action.triggered.connect(self._open_report_dialog)
        view_menu.addAction(report_action)
        view_menu.addSeparator()
        toggle_panel_action = QAction("隐藏/显示右侧面板", self)
        toggle_panel_action.setShortcut("F9")
        toggle_panel_action.triggered.connect(self._toggle_right_panel)
        view_menu.addAction(toggle_panel_action)
        settings_action = QAction("⚙️设置", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        menubar.addAction(settings_action)
    def _setup_ui(self):
        """设置主界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery = GalleryView(self.db_service)
        self.gallery.setObjectName("galleryView")
        self.gallery.images_selection_changed.connect(self.on_images_selection_changed)
        left_layout.addWidget(self.gallery)
        self.stats_panel = StatsPanel(self.db_service)
        self.stats_panel.setVisible(False)
        left_layout.addWidget(self.stats_panel)
        self.main_splitter.addWidget(left_container)
        self.right_container = QWidget()
        self.right_container.setObjectName("rightContainer")
        right_layout = QVBoxLayout(self.right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.tag_panel = TagPanel(self.db_service)
        self.tag_panel.setObjectName("tagPanel")
        self.tag_panel.filter_tags_changed.connect(self.on_filter_tags_changed)
        self.tag_panel.tags_updated.connect(self.on_tags_updated)
        right_layout.addWidget(self.tag_panel)
        self.recommend_panel = RecommendPanel(self.db_service)
        self.recommend_panel.setObjectName("recommendPanel")
        right_layout.addWidget(self.recommend_panel)
        right_layout.addStretch(1)
        self.right_scroll_area = QScrollArea()
        self.right_scroll_area.setObjectName("rightScrollArea")
        self.right_scroll_area.setWidgetResizable(True)
        self.right_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.right_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_scroll_area.setWidget(self.right_container)
        self.main_splitter.addWidget(self.right_scroll_area)
        self.main_splitter.setSizes([480, 500])
        main_layout.addWidget(self.main_splitter)
        self._apply_theme()
    def _apply_theme(self):
        """固定使用 dark 主题，并强制刷新所有子控件样式。"""
        self.setProperty("theme", "dark")
        widgets = [self] + self.findChildren(QWidget)
        for widget in widgets:
            widget.setProperty("theme", "dark")
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        app = QApplication.instance()
        if app:
            app.style().unpolish(app)
            app.style().polish(app)
    def _open_report_dialog(self):
        """打开性格画像报告对话框"""
        dialog = ReportDialog(self.db_service, self)
        dialog.exec()
    def _open_ai_dialog(self):
        """打开 AI 生成对话框"""
        dialog = AIGenerateDialog(self.db_service, self)
        dialog.exec()
        self.gallery.load_from_database()
    def _open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_theme()
            new_size = self.config.get("ui.thumbnail_size", 128)
            self.gallery.THUMBNAIL_SIZE = new_size
            self.gallery.list_widget.setIconSize(QSize(new_size, new_size))
            self.gallery.load_from_database()
            if self.config.get("behavior.clipboard_monitor_enabled", False):
                self.clipboard_monitor.start()
            else:
                self.clipboard_monitor.stop()
    def _toggle_right_panel(self):
        """切换右侧面板显示/隐藏（F9）"""
        self.right_scroll_area.setVisible(not self.right_scroll_area.isVisible())
    def _toggle_stats_panel(self):
        """切换统计面板显示/隐藏"""
        is_visible = self.stats_panel.isVisible()
        self.stats_panel.setVisible(not is_visible)
        self.gallery.setVisible(is_visible)
        if not is_visible:
            self.stats_panel.refresh_stats()
    def on_images_selection_changed(self, image_ids: list):
        """多图选中时批量更新标签面板"""
        self.tag_panel.set_current_images(image_ids)
    def on_filter_tags_changed(self, tag_names: list, match_mode: str):
        """标签选择变化时筛选画廊"""
        self.gallery.filter_by_tag_names(tag_names, match_mode)
    def on_tags_updated(self):
        """标签更新后刷新当前画廊"""
        self.gallery.load_from_database()
    def _on_new_clipboard_image(self, image):
        reply = QMessageBox.question(
            self,
            "检测到剪贴板图片",
            "检测到新图片，是否加入库？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        save_dir = Path(self.config.get("paths.last_import_folder", str(Path.home() / "Pictures")))
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"clipboard_{int(time.time())}.png"
        image.save(str(save_path))
        info = FileScanner.get_image_info(str(save_path))
        if info:
            self.db_service.add_image(**info)
            self.gallery.load_from_database()
            self.statusBar().showMessage("已从剪贴板加入图片到库", 2000)
    def closeEvent(self, event):
        """关闭时保存窗口状态"""
        if self.isMaximized():
            self.config.set("window.maximized", True)
        else:
            self.config.set("window.maximized", False)
            self.config.set("window.width", self.width())
            self.config.set("window.height", self.height())
            self.config.set("window.pos_x", self.x())
            self.config.set("window.pos_y", self.y())
        self.config.save()
        event.accept()
if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon_path = get_resource_path("resources/icon.png")
    if not icon_path.exists():
        icon_path = get_resource_path("resources/icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyle("Fusion")
    qss_path = get_resource_path("resources/style.qss")
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())