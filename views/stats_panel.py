import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QFrame, QScrollArea, QPushButton, QSizePolicy,
    QMessageBox
)
from PyQt6.QtCore import Qt, QSize, QEvent
from PyQt6.QtGui import QPixmap, QIcon, QFontMetrics
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
sys.path.insert(0, str(Path(__file__).parent.parent))
from services.database_service import DatabaseService
from utils.config_manager import ConfigManager
CHART_BG = "#ffffff"
CHART_TEXT = "#526174"
CHART_GRID = "#dce7f5"
CHART_BLUE = "#5b8def"
CHART_BLUE_DARK = "#4169b1"
CHART_FILL_ALPHA = 0.16
class StatsPanel(QWidget):
    """数据统计面板：核心指标 + 趋势图 + 时段分布 + 使用次数排行榜"""
    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.config = ConfigManager()
        self.thumb_service = None  # 延迟导入避免循环
        self._last_trend_date = datetime.now().date() # 记录最近一次刷新「最近7天趋势」时所属的日期，用于跨天（24:00）时同步刷新
        self.setup_ui()
        self.refresh_stats()
    def setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        # 顶部工具栏卡片
        header_card = QFrame()
        header_card.setObjectName("statsToolbar")
        header_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)
        title_label = QLabel("📊数据统计")
        title_label.setObjectName("panelTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        self.clear_button = QPushButton("🗑清空历史记录")
        self.clear_button.setObjectName("dangerButton")
        self.clear_button.setToolTip("清空全部使用历史记录，所有统计将回到初始的空状态")
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.setFixedHeight(32)
        self.clear_button.clicked.connect(self.on_clear_history_clicked)
        header_layout.addWidget(self.clear_button)
        self.refresh_button = QPushButton("🔄刷新")
        self.refresh_button.setObjectName("primaryButton")
        self.refresh_button.setToolTip("刷新「使用时段分布（最近24小时）」；跨天时同时刷新「最近7天使用趋势」")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setFixedHeight(32)
        self.refresh_button.clicked.connect(self.on_refresh_clicked)
        header_layout.addWidget(self.refresh_button)
        outer_layout.addWidget(header_card)
        # 可滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer_layout.addWidget(self.scroll_area)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        #三个核心数字卡片
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(6)
        self.card_images = self._make_card("总图片数", "0")
        self.card_tags = self._make_card("总标签数", "0")
        self.card_usage = self._make_card("总使用次数", "0")
        cards_layout.addWidget(self.card_images)
        cards_layout.addWidget(self.card_tags)
        cards_layout.addWidget(self.card_usage)
        layout.addLayout(cards_layout)
        layout.addSpacing(8)
        #每日使用趋势
        trend_label = QLabel("📈最近7天使用趋势")
        trend_label.setObjectName("chartSectionLabel")
        layout.addWidget(trend_label)
        trend_card = QFrame()
        trend_card.setObjectName("chartCard")
        trend_card_layout = QVBoxLayout(trend_card)
        trend_card_layout.setContentsMargins(4, 4, 4, 4)
        self.trend_figure = Figure(figsize=(7, 2.8), dpi=90)
        self.trend_figure.patch.set_facecolor(CHART_BG)
        self.trend_canvas = FigureCanvas(self.trend_figure)
        self.trend_canvas.setMinimumHeight(200)
        self.trend_canvas.setStyleSheet(f"background-color: {CHART_BG}; border: none;")
        self.trend_canvas.installEventFilter(self)
        trend_card_layout.addWidget(self.trend_canvas)
        layout.addWidget(trend_card)
        # 时段分布图（最近24小时）
        hour_label = QLabel("⏰使用时段分布（最近 24 小时）")
        hour_label.setObjectName("chartSectionLabel")
        layout.addWidget(hour_label)
        hour_card = QFrame()
        hour_card.setObjectName("chartCard")
        hour_card_layout = QVBoxLayout(hour_card)
        hour_card_layout.setContentsMargins(4, 4, 4, 4)
        self.hour_figure = Figure(figsize=(7, 2.8), dpi=90)
        self.hour_figure.patch.set_facecolor(CHART_BG)
        self.hour_canvas = FigureCanvas(self.hour_figure)
        self.hour_canvas.setMinimumHeight(200)
        self.hour_canvas.setStyleSheet(f"background-color: {CHART_BG}; border: none;")
        self.hour_canvas.installEventFilter(self)
        hour_card_layout.addWidget(self.hour_canvas)
        layout.addWidget(hour_card)
        # 表情使用次数排行榜（展示全部已使用表情）
        ranking_label = QLabel("🏆 表情使用次数排行榜")
        ranking_label.setObjectName("chartSectionLabel")
        layout.addWidget(ranking_label)
        self.ranking_list = QListWidget()
        self.ranking_list.setObjectName("rankingList")
        self.ranking_list.setMinimumHeight(220)
        self.ranking_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ranking_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ranking_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.ranking_list.installEventFilter(self)
        self.ranking_list.viewport().installEventFilter(self)
        layout.addWidget(self.ranking_list)
        # 最近刷新时间
        self.refresh_label = QLabel("")
        self.refresh_label.setObjectName("hintLabel")
        layout.addWidget(self.refresh_label)
        layout.addStretch()
        self.scroll_area.setWidget(content)
    def eventFilter(self, watched, event):
        """把子控件吞掉的滚轮事件转交给外层滚动区域。"""
        if event.type() == QEvent.Type.Wheel and hasattr(self, "scroll_area"):
            wheel_targets = {
                self.ranking_list,
                self.ranking_list.viewport(),
                self.trend_canvas,
                self.hour_canvas,
            }
            if watched in wheel_targets:
                scrollbar = self.scroll_area.verticalScrollBar()
                delta = event.angleDelta().y()
                if delta:
                    scrollbar.setValue(scrollbar.value() - delta)
                    event.accept()
                    return True
        return super().eventFilter(watched, event)
    def _make_card(self, title: str, value: str) -> QFrame:
        """创建紧凑统计数字卡片"""
        card = QFrame()
        card.setObjectName("statsCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setMinimumHeight(56)
        card.setMaximumHeight(72)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(2)
        title_lbl = AutoFitLabel(title, min_size=9, max_size=12)
        title_lbl.setObjectName("statsTitle")
        title_lbl.setWordWrap(True)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_lbl = AutoFitLabel(value, min_size=12, max_size=22)
        value_lbl.setObjectName("statsValue")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title_lbl, 1)
        v.addWidget(value_lbl, 1)
        # 保存 value_lbl 引用以便更新
        card._title_label = title_lbl
        card._value_label = value_lbl
        return card
    def on_clear_history_clicked(self):
        """清空全部使用历史记录，并将所有统计刷新回初始空状态"""
        reply = QMessageBox.question(
            self,
            "清空历史记录",
            "确定要清空全部使用历史记录吗？\n\n"
            "清空后，总使用次数、使用趋势、时段分布、使用次数排行榜以及"
            "性格画像报告所依赖的数据都会回到初始的空状态，且无法恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.clear_usage_history()
        except Exception:
            QMessageBox.warning(self, "清空历史记录", "清空失败，请稍后重试。")
            return
        self.refresh_stats()
    def on_refresh_clicked(self):
        """刷新按钮：更新「最近24小时」时段分布；跨天时同步刷新「最近7天趋势」与卡片"""
        self._refresh_cards()
        self._refresh_hourly()
        # 跨天（例如到了次日 00:00）时，最近7天的窗口已经滚动，需要同步刷新
        if datetime.now().date() != self._last_trend_date:
            self._refresh_trend()
        self._refresh_ranking()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.refresh_label.setText(f"上次刷新：{now_str}")
    def refresh_stats(self):
        """刷新所有统计数据（使用本地时间）"""
        self._refresh_cards()
        self._refresh_trend()
        self._refresh_hourly()
        self._refresh_ranking()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.refresh_label.setText(f"上次刷新：{now_str}")
    def _refresh_cards(self):
        """更新三张核心卡片"""
        stats = self.db.get_stats()
        image_count = stats.get("count", 0)
        tags = self.db.get_all_tags()
        tag_count = len(tags)
        try:
            usage_rows = self.db.get_usage_history()
            usage_count = len(usage_rows)
        except Exception:
            usage_count = 0
        self.card_images._value_label.setText(str(image_count))
        self.card_tags._value_label.setText(str(tag_count))
        self.card_usage._value_label.setText(str(usage_count))
    @staticmethod
    def _parse_used_at(used_at_str: str) -> datetime | None:
        """解析时间字符串，兼容多种格式"""
        try:
            s = str(used_at_str).replace('T', ' ').split('.')[0]
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return None
    def _refresh_trend(self):
        """最近7天使用趋势折线图（本地时间）"""
        self.trend_figure.clear()
        self.trend_figure.patch.set_facecolor(CHART_BG)
        ax = self.trend_figure.add_subplot(111)
        ax.set_facecolor(CHART_BG)
        ax.tick_params(colors=CHART_TEXT, labelsize=8)
        ax.xaxis.label.set_color(CHART_TEXT)
        ax.yaxis.label.set_color(CHART_TEXT)
        today = datetime.now().date()
        dates = [(today - timedelta(days=i)).strftime("%m-%d") for i in range(6, -1, -1)]
        counts = defaultdict(int)
        try:
            rows = self.db.get_usage_history()
            for row in rows:
                # row: (id, image_id, used_at)
                dt = self._parse_used_at(row[2])
                try:
                    if dt is None:
                        continue
                    day_label = dt.date().strftime("%m-%d")
                    if day_label in dates:
                        counts[day_label] += 1
                except ValueError:
                    pass
        except Exception:
            pass
        values = [counts.get(d, 0) for d in dates]
        ax.plot(dates, values, marker='o', color=CHART_BLUE, linewidth=2, markersize=5)
        ax.fill_between(dates, values, alpha=CHART_FILL_ALPHA, color=CHART_BLUE)
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates)
        ax.grid(axis='y', color=CHART_GRID, linewidth=0.8, alpha=0.8)
        for spine in ax.spines.values():
            spine.set_color(CHART_GRID)
        self.trend_figure.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.18)
        self.trend_canvas.draw()
        self._last_trend_date = today
    def _refresh_hourly(self):
        """最近24小时时段分布柱状图（本地时间，滚动窗口）
        """
        self.hour_figure.clear()
        self.hour_figure.patch.set_facecolor(CHART_BG)
        ax = self.hour_figure.add_subplot(111)
        ax.set_facecolor(CHART_BG)
        ax.tick_params(colors=CHART_TEXT, labelsize=8)
        now = datetime.now()
        window_start = now - timedelta(hours=24)
        hour_counts = [0] * 24
        try:
            rows = self.db.get_usage_history()
            for row in rows:
                dt = self._parse_used_at(row[2])
                if dt is not None and window_start <= dt <= now:
                    hour_counts[dt.hour] += 1
        except Exception:
            pass
        hours = list(range(24))
        colors = [CHART_BLUE if h in range(9, 22) else CHART_BLUE_DARK for h in hours]
        ax.bar(hours, hour_counts, color=colors, edgecolor='none')
        ax.set_xticks(hours)
        ax.set_xticklabels([f"{h}时" for h in hours], color=CHART_TEXT, fontsize=7, rotation=90)
        ax.grid(axis='y', color=CHART_GRID, linewidth=0.8, alpha=0.8)
        ax.set_xlim(-0.5, 23.5)
        for spine in ax.spines.values():
            spine.set_color(CHART_GRID)
        self.hour_figure.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.22)
        self.hour_canvas.draw()
    def _refresh_ranking(self):
        """表情使用次数排行榜（展示全部已使用表情，带缩略图）
        """
        self.ranking_list.clear()
        self.ranking_list.setIconSize(QSize(40, 40))
        try:
            rows = self.db.get_usage_history()
        except Exception:
            rows = []
        if not rows:
            self.ranking_list.addItem("暂无使用记录")
            self._fit_ranking_height()
            return
        # 统计每张图片的使用次数
        use_counts: dict = defaultdict(int)
        for row in rows:
            image_id = row[1]
            use_counts[image_id] += 1
        # 按使用次数降序排序（次数相同按 image_id 升序），展示全部，依次编号 #1…#N
        ranked = sorted(use_counts.items(), key=lambda x: (-x[1], x[0]))
        # 延迟导入 ThumbnailService
        if self.thumb_service is None:
            from services.thumbnail_service import ThumbnailService
            self.thumb_service = ThumbnailService()
        rank = 0
        for image_id, count in ranked:
            img_row = self.db.get_image_by_id(image_id)
            if not img_row:
                continue
            rank += 1
            name = img_row[1]
            file_path = img_row[2]
            item = QListWidgetItem(f"#{rank}  {name}   ·   使用 {count} 次")
            item.setData(Qt.ItemDataRole.UserRole, image_id)
            # 加载缩略图
            thumb_path = self.thumb_service.get_thumbnail(file_path)
            if thumb_path:
                pixmap = QPixmap(thumb_path)
            else:
                pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(40, 40,
                                       Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(scaled))
            self.ranking_list.addItem(item)
        self._fit_ranking_height()
    def _fit_ranking_height(self):
        """根据条目数量调整排行榜列表高度"""
        count = self.ranking_list.count()
        if count <= 0:
            self.ranking_list.setFixedHeight(220)
            return
        row_height = self.ranking_list.sizeHintForRow(0)
        if row_height <= 0:
            row_height = 48
        frame = 2 * self.ranking_list.frameWidth()
        total = row_height * count + frame + 4
        self.ranking_list.setFixedHeight(total)
class AutoFitLabel(QLabel):
    """根据当前控件尺寸自动调整字号"""
    def __init__(self, text: str = "", min_size: int = 10, max_size: int = 36, parent=None):
        super().__init__(text, parent)
        self._min_size = min_size
        self._max_size = max_size
        self._update_font()
    def setText(self, text: str):
        super().setText(text)
        self._update_font()
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_font()
    def _update_font(self):
        text = self.text() or " "
        rect = self.contentsRect()
        max_w = max(10, rect.width() - 6)
        max_h = max(10, rect.height() - 6)
        font = self.font()
        flags = int(self.alignment())
        if self.wordWrap():
            flags |= int(Qt.TextFlag.TextWordWrap)
        for size in range(self._max_size, self._min_size - 1, -1):
            font.setPointSize(size)
            metrics = QFontMetrics(font)
            text_rect = metrics.boundingRect(0, 0, max_w, max_h, flags, text)
            if text_rect.height() <= max_h and text_rect.width() <= max_w:
                self.setFont(font)
                return
        font.setPointSize(self._min_size)
        self.setFont(font)