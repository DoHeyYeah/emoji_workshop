import hashlib
import logging
from pathlib import Path
from PIL import Image
class ThumbnailService:
    """缩略图生成与缓存服务"""
    THUMB_SIZE = 128
    QUALITY = 85
    def __init__(self, cache_dir: str | None = None):
        if cache_dir is None:
            # 默认放在 resources/thumbnails/
            self.cache_dir = Path(__file__).parent.parent / "resources" / "thumbnails"
        else:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    def _get_cache_path(self, file_path: str) -> Path:
        """根据原图路径生成缓存文件名"""
        path_obj = Path(file_path)
        mtime = str(path_obj.stat().st_mtime) if path_obj.exists() else "0"
        unique_str = f"{file_path}:{mtime}"
        hash_name = hashlib.md5(unique_str.encode()).hexdigest()
        return self.cache_dir / f"{hash_name}.jpg"
    def get_thumbnail(self, file_path: str) -> str | None:
        """获取缩略图路径。如果缓存不存在则生成。"""
        src = Path(file_path)
        if not src.exists():
            return None
        cache_path = self._get_cache_path(file_path)
        if cache_path.exists():
            return str(cache_path)
        return self._generate_thumbnail(file_path, cache_path)
    def _normalize_to_rgb(self, img: Image.Image) -> Image.Image:
        """将任意模式图像安全转换为 RGB（处理透明通道）"""
        if img.mode in ("RGBA", "LA", "P", "PA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            rgba = img.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            return bg
        if img.mode != "RGB":
            return img.convert("RGB")
        return img
    def _generate_thumbnail(self, src_path: str, dst_path: Path) -> str | None:
        """用 Pillow 生成缩略图"""
        try:
            with Image.open(src_path) as img:
                img = self._normalize_to_rgb(img)
                img.thumbnail((self.THUMB_SIZE, self.THUMB_SIZE), Image.Resampling.LANCZOS)
                img.save(dst_path, "JPEG", quality=self.QUALITY)
                return str(dst_path)
        except Exception as e:
            logging.error("缩略图生成失败 %s: %s", src_path, e)
            return None
    def clear_cache(self):
        """清空所有缩略图缓存"""
        for f in self.cache_dir.glob("*.jpg"):
            f.unlink()
    def get_cache_size(self) -> int:
        """获取缓存文件数量"""
        return len(list(self.cache_dir.glob("*.jpg")))