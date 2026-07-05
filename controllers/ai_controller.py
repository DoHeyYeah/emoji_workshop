from PyQt6.QtCore import QObject, pyqtSignal
from services.database_service import DatabaseService
class AIController(QObject):
    """AI 生成业务控制器"""
    image_imported = pyqtSignal(int)  # 返回导入的图片 ID
    generation_started = pyqtSignal()
    generation_finished = pyqtSignal(bool, str)  # 成功/失败, 消息
    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
    def open_generate_dialog(self, parent_widget=None):
        """打开 AI 生成对话框"""
        from views.ai_generate_dialog import AIGenerateDialog
        dialog = AIGenerateDialog(self.db, parent_widget)
        dialog.exec()
    def validate_api_key(self, provider: str, api_key: str) -> bool:
        """验证 API Key 是否有效（简单检查格式）"""
        if provider == "siliconflow":
            return api_key.startswith("sk-") and len(api_key) > 20
        return True