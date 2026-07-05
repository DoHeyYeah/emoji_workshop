import json
import logging
from pathlib import Path
from typing import Any, Optional
class ConfigManager:
    """应用配置管理器"""
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    def __init__(self, config_name: str = "emoji_workshop_config.json"):
        if self._initialized:
            return
        self._initialized = True
        self.config_dir = Path.home() / ".emoji_workshop"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / config_name
        self._defaults = {
            "window": {
                "width": 1200,
                "height": 700,
                "pos_x": 100,
                "pos_y": 100,
                "maximized": False,
            },
            "ui": {
                "theme": "dark",
                "thumbnail_size": 128,
                "preview_panel_width": 500,
            },
            "paths": {
                "last_import_folder": str(Path.home() / "Pictures"),
                "last_export_folder": str(Path.home() / "Desktop"),
                "cache_dir": None,
            },
            "ai": {
                "provider": "pollinations",
                "doubao_api_key": "",
            },
            "ai_providers": {
                "active": "doubao",
                "pollinations": {
                    "enabled": True,
                    "api_key": "",
                    "model": "",
                    "base_url": "",
                },
                "doubao": {
                    "enabled": False,
                    "api_key": "",
                    "model": "doubao-seedream-5-0-260128",
                    "base_url": "",
                },
                "custom": {
                    "enabled": False,
                    "api_key": "",
                    "model": "",
                    "base_url": "",
                },
            },
            "llm": {
                "enabled": False,
                "base_url": "",
                "api_key": "",
                "model": "",
            },
            "vision": {
                "enabled": False,
                "base_url": "",
                "api_key": "",
                "model": "",
            },
            "replicate": {
                "base_url": "",
                "api_key": "",
                "model": "",
            },
            "behavior": {
                "auto_save": True,
                "confirm_delete": True,
                "clipboard_monitor_enabled": False,
                "recent_folders": [],
                "recent_files": [],
                "search_history": [],
            },
            "stats": {
                "total_imported": 0,
                "total_tags_created": 0,
                "launch_count": 0,
            },
        }
        self._config = {}
        self._load()
    def _load(self) -> None:
        """从文件加载配置，合并到默认值"""
        self._config = self._deep_copy(self._defaults)
        if not self.config_file.exists():
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self._deep_merge(self._config, loaded)
        except (json.JSONDecodeError, OSError) as e:
            logging.debug("[ConfigManager]配置加载失败，使用默认配置: %s", e)
    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            return True
        except OSError as e:
            logging.debug("[ConfigManager]配置保存失败: %s", e)
            return False
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        value: Any = self._config
        for k in key.split("."):
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    def set(self, key: str, value: Any, autosave: bool | None = None) -> None:
        """设置配置项"""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        do_save = self.get("behavior.auto_save", True) if autosave is None else autosave
        if do_save:
            self.save()
    def set_many(self, items: dict[str, Any], autosave: bool | None = None) -> None:
        """批量设置配置项"""
        for key, value in items.items():
            self.set(key, value, autosave=False)
        do_save = self.get("behavior.auto_save", True) if autosave is None else autosave
        if do_save:
            self.save()
    def reset_to_default(self, key: Optional[str] = None) -> None:
        """重置配置：key=None 重置全部，否则重置指定键"""
        if key is None:
            self._config = self._deep_copy(self._defaults)
            self.save()
            return
        exists, default_val = self._try_get_default_by_key(key)
        if exists:
            self.set(key, default_val)
        else:
            logging.debug("[ConfigManager] reset_to_default: 未找到默认键 %s", key)
    def add_recent_folder(self, folder_path: str) -> None:
        """添加最近文件夹（去重，最多保留10个）"""
        recent = self.get("behavior.recent_folders", [])
        recent = [f for f in recent if f != folder_path]
        recent.insert(0, folder_path)
        self.set("behavior.recent_folders", recent[:10])
    def get_recent_folders(self) -> list:
        return self.get("behavior.recent_folders", [])
    def add_search_history(self, keyword: str) -> None:
        """添加搜索历史"""
        if not keyword:
            return
        history = self.get("behavior.search_history", [])
        history = [k for k in history if k != keyword]
        history.insert(0, keyword)
        self.set("behavior.search_history", history[:20])
    def get_search_history(self) -> list:
        return self.get("behavior.search_history", [])
    def clear_search_history(self) -> None:
        self.set("behavior.search_history", [])
    def increment_stat(self, stat_key: str) -> None:
        current = self.get(f"stats.{stat_key}", 0)
        self.set(f"stats.{stat_key}", current + 1)
    def get_llm_config(self) -> dict:
        cfg = self.get("llm", {}) or {}
        return {
            "enabled": bool(cfg.get("enabled", False)),
            "base_url": cfg.get("base_url", ""),
            "api_key": cfg.get("api_key", ""),
            "model": cfg.get("model", ""),
        }
    def set_llm_config(self, base_url: str, api_key: str, model: str, enabled: bool) -> None:
        self.set_many(
            {
                "llm.base_url": base_url,
                "llm.api_key": api_key,
                "llm.model": model,
                "llm.enabled": enabled,
            }
        )
    def is_llm_enabled(self) -> bool:
        cfg = self.get_llm_config()
        return bool(cfg.get("enabled") and cfg.get("api_key"))
    def get_vision_config(self) -> dict:
        cfg = self.get("vision", {}) or {}
        return {
            "enabled": bool(cfg.get("enabled", False)),
            "base_url": cfg.get("base_url", ""),
            "api_key": cfg.get("api_key", ""),
            "model": cfg.get("model", ""),
        }
    def set_vision_config(self, enabled: bool, base_url: str, api_key: str, model: str) -> None:
        self.set_many(
            {
                "vision.enabled": enabled,
                "vision.base_url": base_url,
                "vision.api_key": api_key,
                "vision.model": model,
            }
        )
    def get_replicate_config(self) -> dict:
        cfg = self.get("replicate", {}) or {}
        return {
            "base_url": cfg.get("base_url", ""),
            "api_key": cfg.get("api_key", ""),
            "model": cfg.get("model", ""),
        }
    def set_replicate_config(self, base_url: str, api_key: str, model: str) -> None:
        self.set_many(
            {
                "replicate.base_url": base_url,
                "replicate.api_key": api_key,
                "replicate.model": model,
            }
        )
    def get_ai_provider_config(self, name: str | None = None) -> dict:
        """获取 AI 文生图提供商配置"""
        cfg = self.get("ai_providers", {}) or {}
        defaults = self._defaults.get("ai_providers", {})
        merged = {
            "active": cfg.get("active", defaults.get("active", "pollinations")),
            "pollinations": {**defaults.get("pollinations", {}), **cfg.get("pollinations", {})},
            "doubao": {**defaults.get("doubao", {}), **cfg.get("doubao", {})},
            "custom": {**defaults.get("custom", {}), **cfg.get("custom", {})},
        }
        merged["doubao"]["api_key"] = merged["doubao"].get("api_key") or self.get("ai.doubao_api_key", "")
        if name:
            return dict(merged.get(name, {}))
        return merged
    def set_ai_provider_config(self, name: str, **kwargs) -> None:
        allowed = {"api_key", "model", "base_url", "enabled"}
        current = self.get_ai_provider_config(name)
        updated = dict(current)
        for key, value in kwargs.items():
            if key in allowed:
                updated[key] = value
        updates: dict[str, Any] = {f"ai_providers.{name}": updated}
        if name == "doubao" and "api_key" in kwargs:
            updates["ai.doubao_api_key"] = kwargs.get("api_key", "")
        self.set_many(updates)
    def _deep_copy(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        return obj
    def _deep_merge(self, base: dict, override: dict) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    def _try_get_default_by_key(self, key: str) -> tuple[bool, Any]:
        """根据键从默认值中获取，返回 (是否存在该键, 默认值)"""
        value: Any = self._defaults
        for k in key.split("."):
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return False, None
        return True, self._deep_copy(value)