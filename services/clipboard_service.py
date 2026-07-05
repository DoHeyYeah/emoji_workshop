from pathlib import Path
from PyQt6.QtCore import QMimeData, QUrl
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication
class ClipboardService:
    """统一的剪贴板复制服务,适配静图和动图"""
    INTERNAL_MIME_TYPE = "application/x-emoji-workshop-internal"
    @staticmethod
    def copy_image(file_path: str) -> bool:
        """复制图片到剪贴板"""
        path = Path(file_path)
        if not path.exists():
            return False
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path.absolute()))])
        image = QImage(str(path))
        if not image.isNull():
            mime.setImageData(image)
        mime.setData(ClipboardService.INTERNAL_MIME_TYPE, b"1")
        QApplication.clipboard().setMimeData(mime)
        return True
    @staticmethod
    def is_animated(file_path: str) -> bool:
        """判断是否为动图(GIF / WebP 动图)"""
        suffix = Path(file_path).suffix.lower()
        return suffix in {'.gif', '.webp'}