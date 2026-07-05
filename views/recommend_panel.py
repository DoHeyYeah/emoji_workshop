from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLineEdit,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from controllers.recommend_controller import RecommendController
from services.database_service import DatabaseService
from services.thumbnail_service import ThumbnailService
from services.clipboard_service import ClipboardService
from utils.config_manager import ConfigManager
class RecommendPanel(QWidget):
    """智能推荐侧边栏"""
    image_selected = pyqtSignal(int)  # 选中推荐结果时发出 image_id
    def __init__(self, db_service: DatabaseService, parent=None) -> None:
        super().__init__(parent)
        self.db = db_service
        self.controller = RecommendController(db_service)
        self.config = ConfigManager()
        self.thumb_service = ThumbnailService()
        self.recommend_worker: RecommendWorker | None = None
        self._setup_ui()
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        title = QLabel("💡智能推荐")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        self.context_input = QLineEdit()
        self.context_input.setPlaceholderText("请粘贴聊天上下文...")
        self.context_input.setFixedHeight(30)
        layout.addWidget(self.context_input)
        btn_row = QHBoxLayout()
        self.recommend_btn = QPushButton("🔍推荐")
        self.recommend_btn.setObjectName("primaryButton")
        self.recommend_btn.clicked.connect(self._do_recommend)
        self.goto_settings_btn = QPushButton("前往设置")
        self.goto_settings_btn.setObjectName("secondaryButton")
        self.goto_settings_btn.clicked.connect(self._goto_settings)
        self.goto_settings_btn.setVisible(False)
        btn_row.addWidget(self.recommend_btn)
        btn_row.addWidget(self.goto_settings_btn)
        layout.addLayout(btn_row)
        self.error_label = QLabel("⚠️请先在设置→AI推荐中配置LLM API Key")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(not self.config.is_llm_enabled())
        layout.addWidget(self.error_label)
        self.result_list = QListWidget()
        self.result_list.setObjectName("thumbList")
        self.result_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.result_list.setIconSize(QSize(96, 96))
        self.result_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.result_list.setSpacing(6)
        self.result_list.setMinimumHeight(200)
        self.result_list.itemDoubleClicked.connect(self._on_double_click)
        self.result_list.itemClicked.connect(self._on_single_click)
        layout.addWidget(self.result_list)
        self.hint_label = QLabel("双击结果可复制到剪贴板")
        self.hint_label.setObjectName("hintLabel")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)
    # 推荐流程
    def _set_recommending_ui(self, running: bool) -> None:
        self.recommend_btn.setEnabled(not running)
        self.recommend_btn.setText("连接中…" if running else "🔍 推荐")
        if running:
            self.error_label.setVisible(False)
            self.goto_settings_btn.setVisible(False)
            self.hint_label.setText("🔄正在连接AI…")
    def _do_recommend(self) -> None:
        context = self.context_input.text().strip()
        if not context:
            self.error_label.setText("请输入聊天上下文后再推荐")
            self.error_label.setVisible(True)
            return
        if self.recommend_worker and self.recommend_worker.isRunning():
            return
        self._set_recommending_ui(True)
        self.recommend_worker = RecommendWorker(self.controller, context, top_k=6, parent=self)
        self.recommend_worker.succeeded.connect(self._on_recommend_success)
        self.recommend_worker.failed.connect(self._on_recommend_failed)
        self.recommend_worker.finished.connect(self._on_recommend_done)
        self.recommend_worker.start()
    def _on_recommend_success(self, results, _tags) -> None:
        self.error_label.clear()
        self.error_label.setVisible(False)
        self.goto_settings_btn.setVisible(False)
        self._show_results(results)
        self._update_diag_hint(results)
    def _on_recommend_failed(self, raw_msg: str) -> None:
        self.result_list.clear()
        self.hint_label.setText("推荐失败")
        msg = self._friendly_error(raw_msg)
        self.error_label.setText(msg)
        self.error_label.setVisible(True)
        needs_settings = any(k in raw_msg for k in ("设置", "未启用", "未配置"))
        self.goto_settings_btn.setVisible(needs_settings)
    def _on_recommend_done(self) -> None:
        self._set_recommending_ui(False)
        self.recommend_worker = None
    @staticmethod
    def _friendly_error(raw_msg: str) -> str:
        if any(k in raw_msg for k in ("未启用", "未配置", "当前库中没有任何标签")):
            return raw_msg
        if "未返回任何推荐标签" in raw_msg:
            return "⚠️AI已连接，但未返回可用推荐，请稍后再试"
        return "⚠️AI连接失败：网络不佳或API Key无效，请检查设置"
    # 结果渲染
    def _show_results(self, models) -> None:
        self.result_list.clear()
        if not models:
            self.hint_label.setText("暂无推荐结果，请先导入表情包并添加标签")
            return
        self.hint_label.setText("双击结果可复制到剪贴板")
        for idx, model in enumerate(models):
            item = QListWidgetItem()
            if idx == 0:
                item.setText(f"⭐ 最佳推荐 | {model.display_name}")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item.setText(model.display_name)
            item.setData(Qt.ItemDataRole.UserRole, model.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, model.file_path)
            thumb_path = model.thumbnail_path
            if not thumb_path or not Path(thumb_path).exists():
                thumb_path = self.thumb_service.get_thumbnail(model.file_path)
            pixmap = QPixmap(thumb_path) if thumb_path else QPixmap(model.file_path)
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap.scaled(
                    96, 96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )))
            self.result_list.addItem(item)
    def _update_diag_hint(self, results) -> None:
        debug = getattr(self.controller, "last_debug_info", {}) or {}
        llm_status = debug.get("llm_status", "未启用")
        vision_status = debug.get("vision_status", "未启用")
        tags = ",".join(debug.get("tags", [])[:3]) or "-"
        keywords = ",".join(debug.get("keywords", [])[:3]) or "-"
        candidate_count = debug.get("candidate_count", 0)
        fallback = debug.get("fallback", "")
        base = "✅推荐完成" if results else "暂无推荐结果"
        diag = (
            f"{base} | LLM:{llm_status} | 视觉:{vision_status} | "
            f"标签:{tags} | 关键词:{keywords} | 候选:{candidate_count}"
        )
        if fallback:
            diag += f" | 降级:{fallback}"
        self.hint_label.setText(diag)
    # 交互
    def _on_single_click(self, item: QListWidgetItem) -> None:
        image_id = item.data(Qt.ItemDataRole.UserRole)
        if image_id is not None:
            self.image_selected.emit(image_id)
    def _on_double_click(self, item: QListWidgetItem) -> None:
        file_path = item.data(Qt.ItemDataRole.UserRole + 1)
        if not file_path or not Path(file_path).exists():
            return
        if ClipboardService.copy_image(file_path):
            image_id = item.data(Qt.ItemDataRole.UserRole)
            if image_id:
                self.db.record_usage(image_id)
            msg = "已复制+已记录使用"
            self.hint_label.setText(f"✅{msg}")
            main_win = self.window()
            if hasattr(main_win, "statusBar"):
                main_win.statusBar().showMessage(msg, 2000)
        else:
            self.hint_label.setText("❌复制失败")
        QTimer.singleShot(3000, lambda: self.hint_label.setText("双击结果可复制到剪贴板"))
    def _goto_settings(self) -> None:
        main_win = self.window()
        if hasattr(main_win, "_open_settings"):
            main_win._open_settings()
class RecommendWorker(QThread):
    """后台执行推荐请求"""
    succeeded = pyqtSignal(object, object)
    failed = pyqtSignal(str)
    def __init__(self, controller: RecommendController, context: str, top_k: int, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._context = context
        self._top_k = top_k
    def run(self) -> None:
        try:
            results = self._controller.recommend(self._context, top_k=self._top_k)
            tags = list(self._controller.last_recommended_tags)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(results, tags)