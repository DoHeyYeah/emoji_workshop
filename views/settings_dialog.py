from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QDialogButtonBox,
    QFileDialog, QTabWidget, QWidget, QGroupBox, QFormLayout,
    QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSignal
from utils.config_manager import ConfigManager
class ConnectionTestThread(QThread):
    """通用后台连接测试线程"""
    result = pyqtSignal(bool, str)  # success, message
    def __init__(self, test_func, parent=None):
        super().__init__(parent)
        self.test_func = test_func
    def run(self):
        try:
            ok, msg = self.test_func()
            self.result.emit(ok, msg or "")
        except Exception as exc:
            self.result.emit(False, str(exc))
class SettingsDialog(QDialog):
    """应用设置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.network_thread = None
        self.llm_thread = None
        self.vision_thread = None
        self.setWindowTitle("⚙️应用设置")
        self.setMinimumSize(600, 600)
        self.resize(600, 600)
        self._setup_ui()
        self._load_all_settings()
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.paths_tab = self._create_paths_tab()
        self.network_tab = self._create_network_tab()
        self.advanced_tab = self._create_advanced_tab()
        self.ai_tab = self._create_ai_tab()
        self.tabs.addTab(self.paths_tab, "路径")
        self.tabs.addTab(self.network_tab, "网络")
        self.tabs.addTab(self.advanced_tab, "高级")
        self.tabs.addTab(self.ai_tab, "🤖AI推荐")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def _create_paths_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        group = QGroupBox("默认路径")
        form = QFormLayout()
        import_layout = QHBoxLayout()
        self.import_path_edit = QLineEdit()
        self.import_path_edit.setReadOnly(True)
        import_layout.addWidget(self.import_path_edit)
        import_btn = QPushButton("浏览...")
        import_btn.clicked.connect(self._browse_import)
        import_layout.addWidget(import_btn)
        form.addRow("默认导入文件夹:", import_layout)
        export_layout = QHBoxLayout()
        self.export_path_edit = QLineEdit()
        self.export_path_edit.setReadOnly(True)
        export_layout.addWidget(self.export_path_edit)
        export_btn = QPushButton("浏览...")
        export_btn.clicked.connect(self._browse_export)
        export_layout.addWidget(export_btn)
        form.addRow("默认导出文件夹:", export_layout)
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        return tab
    def _create_network_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        group = QGroupBox("连接测试")
        v = QVBoxLayout()
        self.test_result_label = QLabel("点击测试按钮验证网络连接")
        v.addWidget(self.test_result_label)
        self.test_network_btn = QPushButton("🌐测试网络连接")
        self.test_network_btn.clicked.connect(self._test_network)
        v.addWidget(self.test_network_btn)
        group.setLayout(v)
        layout.addWidget(group)
        layout.addStretch()
        return tab
    def _create_ai_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        llm_group = QGroupBox("LLM智能推荐")
        llm_form = QFormLayout()
        self.llm_enabled_check = QCheckBox("启用LLM智能推荐")
        llm_form.addRow(self.llm_enabled_check)
        self.llm_base_url_edit = QLineEdit()
        llm_form.addRow("Base URL:", self.llm_base_url_edit)
        self.llm_api_key_edit = QLineEdit()
        self.llm_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        llm_form.addRow("API Key:", self.llm_api_key_edit)
        self.llm_model_edit = QLineEdit()
        llm_form.addRow("Model:", self.llm_model_edit)
        self.llm_test_btn = QPushButton("测试连接")
        self.llm_test_btn.clicked.connect(self._test_llm_connection)
        llm_form.addRow("", self.llm_test_btn)
        self.llm_test_result = QLabel("未测试")
        llm_form.addRow("状态:", self.llm_test_result)
        llm_group.setLayout(llm_form)
        layout.addWidget(llm_group)
        vision_group = QGroupBox("视觉精排")
        vision_form = QFormLayout()
        self.vision_enabled_check = QCheckBox("启用视觉精排")
        vision_form.addRow(self.vision_enabled_check)
        self.vision_base_url_edit = QLineEdit()
        vision_form.addRow("Base URL:", self.vision_base_url_edit)
        self.vision_api_key_edit = QLineEdit()
        self.vision_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        vision_form.addRow("API Key:", self.vision_api_key_edit)
        self.vision_model_edit = QLineEdit()
        vision_form.addRow("Model:", self.vision_model_edit)
        self.vision_test_btn = QPushButton("测试连接")
        self.vision_test_btn.clicked.connect(self._test_vision_connection)
        vision_form.addRow("", self.vision_test_btn)
        self.vision_test_result = QLabel("未测试")
        vision_form.addRow("状态:", self.vision_test_result)
        vision_group.setLayout(vision_form)
        layout.addWidget(vision_group)
        layout.addStretch()
        return tab
    def _create_advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        danger_group = QGroupBox("危险操作")
        v = QVBoxLayout()
        reset_btn = QPushButton("🔄重置所有配置为默认值")
        reset_btn.setObjectName("dangerButton")
        reset_btn.clicked.connect(self._restore_defaults)
        v.addWidget(reset_btn)
        clear_cache_btn = QPushButton("🗑️清空缩略图缓存")
        clear_cache_btn.setObjectName("dangerButton")
        clear_cache_btn.clicked.connect(self._clear_cache)
        v.addWidget(clear_cache_btn)
        danger_group.setLayout(v)
        layout.addWidget(danger_group)
        layout.addStretch()
        return tab
    def _load_all_settings(self):
        self.import_path_edit.setText(self.config.get("paths.last_import_folder", ""))
        self.export_path_edit.setText(self.config.get("paths.last_export_folder", ""))
        llm = self.config.get_llm_config()
        self.llm_enabled_check.setChecked(llm.get("enabled", False))
        self.llm_base_url_edit.setText(llm.get("base_url", ""))
        self.llm_api_key_edit.setText(llm.get("api_key", ""))
        self.llm_model_edit.setText(llm.get("model", ""))
        vision = self.config.get_vision_config()
        self.vision_enabled_check.setChecked(vision.get("enabled", False))
        self.vision_base_url_edit.setText(vision.get("base_url", ""))
        self.vision_api_key_edit.setText(vision.get("api_key", ""))
        self.vision_model_edit.setText(vision.get("model", ""))
    def _save_and_close(self):
        self.config.set("paths.last_import_folder", self.import_path_edit.text().strip())
        self.config.set("paths.last_export_folder", self.export_path_edit.text().strip())
        self.config.set_llm_config(
            base_url=self.llm_base_url_edit.text().strip(),
            api_key=self.llm_api_key_edit.text().strip(),
            model=self.llm_model_edit.text().strip(),
            enabled=self.llm_enabled_check.isChecked(),
        )
        self.config.set_vision_config(
            base_url=self.vision_base_url_edit.text().strip(),
            api_key=self.vision_api_key_edit.text().strip(),
            model=self.vision_model_edit.text().strip(),
            enabled=self.vision_enabled_check.isChecked(),
        )
        self.config.save()
        self.accept()
    def _browse_import(self):
        folder = QFileDialog.getExistingDirectory(self, "选择默认导入文件夹")
        if folder:
            self.import_path_edit.setText(folder)
    def _browse_export(self):
        folder = QFileDialog.getExistingDirectory(self, "选择默认导出文件夹")
        if folder:
            self.export_path_edit.setText(folder)
    def _restore_defaults(self):
        reply = QMessageBox.question(
            self, "确认重置",
            "确定将所有配置恢复为默认值吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.reset_to_default()
            self._load_all_settings()
            QMessageBox.information(self, "完成", "配置已重置为默认值")
    def _clear_cache(self):
        reply = QMessageBox.question(
            self, "确认", "确定清空所有缩略图缓存吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "完成", "缩略图缓存已清空")
    def _set_test_result(self, label: QLabel, success: bool, message: str = ""):
        if success:
            label.setText("✅连接成功")
            label.setStyleSheet("color: #51cf66;")
            label.setToolTip("")
        else:
            label.setText("❌连接失败")
            label.setStyleSheet("color: #ff6b6b;")
            label.setToolTip(message or "")
    def _start_test_thread(self, thread_attr: str, before_start, test_func, on_done):
        t = getattr(self, thread_attr, None)
        if t and t.isRunning():
            return
        before_start()
        t = ConnectionTestThread(test_func, self)
        t.result.connect(on_done)
        t.finished.connect(lambda: setattr(self, thread_attr, None))
        setattr(self, thread_attr, t)
        t.start()
    def _test_network(self):
        def before():
            self.test_network_btn.setEnabled(False)
            self.test_result_label.setText("正在测试...")
            self.test_result_label.setStyleSheet("")
            self.test_result_label.setToolTip("")
        def test_func():
            import requests
            urls = [("百度", "https://www.baidu.com"), ("Google", "https://www.google.com")]
            failed = []
            for name, url in urls:
                try:
                    requests.get(url, timeout=5)
                except Exception as exc:
                    failed.append(f"{name}: {exc}")
            if failed:
                return False, "\n".join(failed)
            return True, "网络连接正常"
        def done(success: bool, message: str):
            self.test_network_btn.setEnabled(True)
            if success:
                self.test_result_label.setText("✅网络连接正常")
                self.test_result_label.setStyleSheet("color: #51cf66;")
                self.test_result_label.setToolTip("")
            else:
                self.test_result_label.setText("❌网络连接异常")
                self.test_result_label.setStyleSheet("color: #ff6b6b;")
                self.test_result_label.setToolTip(message)
        self._start_test_thread("network_thread", before, test_func, done)
    def _test_llm_connection(self):
        def before():
            self.llm_test_btn.setEnabled(False)
            self.llm_test_result.setText("测试中...")
            self.llm_test_result.setStyleSheet("")
            self.llm_test_result.setToolTip("")
        def test_func():
            from services.llm_service import LLMService
            llm = LLMService(
                base_url=self.llm_base_url_edit.text().strip(),
                api_key=self.llm_api_key_edit.text().strip(),
                model=self.llm_model_edit.text().strip(),
            )
            _ = llm.chat("hi", timeout=30)
            return True, ""
        def done(success: bool, message: str):
            self.llm_test_btn.setEnabled(True)
            self._set_test_result(self.llm_test_result, success, message)
        self._start_test_thread("llm_thread", before, test_func, done)
    def _test_vision_connection(self):
        def before():
            self.vision_test_btn.setEnabled(False)
            self.vision_test_result.setText("测试中...")
            self.vision_test_result.setStyleSheet("")
            self.vision_test_result.setToolTip("")
        def test_func():
            from services.vision_service import VisionService
            svc = VisionService(
                base_url=self.vision_base_url_edit.text().strip(),
                api_key=self.vision_api_key_edit.text().strip(),
                model=self.vision_model_edit.text().strip(),
            )
            ok, msg = svc.test_connection()
            return bool(ok), msg or ""
        def done(success: bool, message: str):
            self.vision_test_btn.setEnabled(True)
            self._set_test_result(self.vision_test_result, success, message)
        self._start_test_thread("vision_thread", before, test_func, done)