import os
import logging
from pathlib import Path
from PIL import Image
class FileScanner:
    """文件夹扫描器"""
    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    EXCLUDE_DIRS = {
        "venv",
        ".venv",
        "env",
        "__pycache__",
        ".git",
        "site-packages",
        "node_modules",
        ".idea",
        ".vscode",
        "dist",
        "build",
        ".pytest_cache",
    }
    @classmethod
    def scan_directory(cls, root_path: str) -> list[str]:
        """扫描目录并返回图片文件路径列表（跳过无关目录）"""
        results: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in cls.EXCLUDE_DIRS]
            for filename in filenames:
                if Path(filename).suffix.lower() in cls.SUPPORTED_FORMATS:
                    results.append(str(Path(dirpath) / filename))
        return results
    @classmethod
    def scan_folder(cls, folder_path: str) -> list[dict]:
        """
        扫描文件夹中的所有图片并返回
        """
        results: list[dict] = []
        folder = Path(folder_path)
        if not folder.exists():
            return results
        for file_path_str in cls.scan_directory(str(folder)):
            info = cls.get_image_info(file_path_str)
            if info:
                results.append(info)
        return results
    @classmethod
    def get_image_info(cls, file_path: str) -> dict:
        """获取单张图片的详细信息"""
        path = Path(file_path)
        if not path.exists() or path.suffix.lower() not in cls.SUPPORTED_FORMATS:
            return {}
        try:
            return cls._build_image_info(path)
        except Exception as e:
            logging.debug("无法读取图片%s: %s", path, e)
            return {}
    @staticmethod
    def _build_image_info(path: Path) -> dict:
        """构建统一的图片信息字典"""
        with Image.open(path) as img:
            width, height = img.size
        return {
            "file_path": str(path.absolute()),
            "name": path.stem,
            "file_type": path.suffix.lower().replace(".", ""),
            "file_size": path.stat().st_size,
            "width": width,
            "height": height,
        }