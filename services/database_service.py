import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional


class DatabaseService:
    """数据库服务：图片、标签、推荐检索、使用历史"""

    # 无前缀列清单（避免 i.i.id 这类问题）
    IMAGE_COLUMNS = (
        "id, name, file_path, file_type, file_size, width, height, thumbnail_path"
    )

    def __init__(self, db_path: str = None):
        if db_path is None:
            # database_service.py 位于 <repo>/services/
            # parent.parent 才是项目根目录 <repo>
            project_root = Path(__file__).resolve().parent.parent
            db_path = str(project_root / "emoji_workshop.db")
        self.db_path = db_path
        self._init_database()
        self.ensure_usage_history_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_database(self):
        """初始化数据库表结构（IF NOT EXISTS 保证升级安全）"""
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    file_type TEXT NOT NULL,
                    file_size INTEGER,
                    width INTEGER,
                    height INTEGER,
                    thumbnail_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT DEFAULT '#FF6B6B'
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS image_tags (
                    image_id INTEGER REFERENCES images(id) ON DELETE CASCADE,
                    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                    PRIMARY KEY (image_id, tag_id)
                )
                """
            )

            conn.commit()

    def _image_columns(self, alias: Optional[str] = None) -> str:
        """返回图片列名；若提供 alias 则返回 alias.col 形式"""
        cols = ["id", "name", "file_path", "file_type", "file_size", "width", "height", "thumbnail_path"]
        if alias:
            return ", ".join([f"{alias}.{c}" for c in cols])
        return ", ".join(cols)

    @staticmethod
    def _row_to_image_dict(row: tuple) -> dict:
        return {
            "id": row[0],
            "name": row[1],
            "file_path": row[2],
            "file_type": row[3],
            "file_size": row[4],
            "width": row[5],
            "height": row[6],
            "thumbnail_path": row[7],
        }

    def _fetch_images(self, query: str, params: list | tuple = ()) -> list[tuple]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def _fetch_image_dicts(self, query: str, params: list | tuple = ()) -> list[dict]:
        return [self._row_to_image_dict(row) for row in self._fetch_images(query, params)]

    def add_image(
        self,
        file_path: str,
        name: str,
        file_type: str,
        file_size: int = 0,
        width: int = 0,
        height: int = 0,
        thumbnail_path: str = "",
    ) -> int:
        """添加单张图片记录，返回图片ID"""
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO images (name, file_path, file_type, file_size, width, height, thumbnail_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, file_path, file_type, file_size, width, height, thumbnail_path),
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                cursor.execute("SELECT id FROM images WHERE file_path = ?", (file_path,))
                row = cursor.fetchone()
                return row[0] if row else 0

    def get_all_images(self) -> list[tuple]:
        """获取所有图片记录（tuple 版）"""
        return self._fetch_images(
            f"""
            SELECT {self._image_columns()}
            FROM images
            ORDER BY created_at DESC
            """
        )

    def get_image_by_id(self, image_id: int) -> Optional[tuple]:
        """根据ID获取单张图片"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
            return cursor.fetchone()

    def delete_image(self, image_id: int) -> bool:
        """删除图片记录（级联删除标签关联）"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all(self):
        """清空所有数据"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM image_tags")
            cursor.execute("DELETE FROM tags")
            cursor.execute("DELETE FROM images")
            conn.commit()

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM images")
            count, total_size = cursor.fetchone()
            return {"count": count, "total_size": total_size}

    def add_tag(self, name: str, color: str = "#FF6B6B") -> int:
        """添加标签，返回标签ID（自动去首尾空格，大小写不敏感复用已有标签）"""
        normalized_name = (name or "").strip()
        if not normalized_name:
            return 0

        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO tags (name, color) VALUES (?, ?)",
                    (normalized_name, color),
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                cursor.execute(
                    "SELECT id FROM tags WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
                    (normalized_name,),
                )
                row = cursor.fetchone()
                return row[0] if row else 0

    def get_all_tags(self) -> list[tuple]:
        """获取所有标签"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, color FROM tags ORDER BY name")
            return cursor.fetchall()

    def delete_tag(self, tag_id: int):
        """删除标签（级联删除关联）"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM image_tags WHERE tag_id = ?", (tag_id,))
            cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            conn.commit()

    def add_image_tag(self, image_id: int, tag_id: int):
        """给图片打标签"""
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                    (image_id, tag_id),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass

    def add_tag_to_image(self, image_id: int, tag_name: str, color: str = "#FF6B6B"):
        """按标签名给图片打标签（不存在时自动创建标签）"""
        tag_id = self.add_tag(tag_name, color)
        if tag_id:
            self.add_image_tag(image_id, tag_id)

    def remove_image_tag(self, image_id: int, tag_id: int):
        """移除图片的标签"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM image_tags WHERE image_id = ? AND tag_id = ?",
                (image_id, tag_id),
            )
            conn.commit()

    def get_image_tags(self, image_id: int) -> list[tuple]:
        """获取图片的所有标签"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t.id, t.name, t.color
                FROM tags t
                JOIN image_tags it ON t.id = it.tag_id
                WHERE it.image_id = ?
                """,
                (image_id,),
            )
            return cursor.fetchall()

    def search_images_by_tags(self, tag_ids: list[int]) -> list[tuple]:
        """按标签ID交集筛选（兼容旧接口，返回 tuple）"""
        if not tag_ids:
            return self.get_all_images()
        uniq_tag_ids = list(dict.fromkeys(tag_ids))
        placeholders = ",".join("?" * len(uniq_tag_ids))
        query = f"""
            SELECT {self._image_columns("i")}
            FROM images i
            JOIN image_tags it ON i.id = it.image_id
            WHERE it.tag_id IN ({placeholders})
            GROUP BY i.id
            HAVING COUNT(DISTINCT it.tag_id) = ?
            ORDER BY i.created_at DESC
        """
        return self._fetch_images(query, [*uniq_tag_ids, len(uniq_tag_ids)])

    def get_images_by_tags_union(self, tag_names: list[str]) -> list[dict]:
        """按标签名并集筛选图片（命中任一标签即可）"""
        if not tag_names:
            return [self._row_to_image_dict(row) for row in self.get_all_images()]

        normalized = []
        for n in tag_names:
            s = (n or "").strip().lower()
            if s:
                normalized.append(s)
        normalized = list(dict.fromkeys(normalized))
        if not normalized:
            return [self._row_to_image_dict(row) for row in self.get_all_images()]

        placeholders = ",".join("?" * len(normalized))
        query = f"""
            SELECT DISTINCT {self._image_columns("i")}
            FROM images i
            JOIN image_tags it ON i.id = it.image_id
            JOIN tags t ON t.id = it.tag_id
            WHERE LOWER(TRIM(t.name)) IN ({placeholders})
            ORDER BY i.created_at DESC
        """
        return self._fetch_image_dicts(query, normalized)

    def get_images_by_tags_intersect(self, tag_names: list[str]) -> list[dict]:
        """按标签名交集筛选图片（需同时命中所有标签）"""
        if not tag_names:
            return [self._row_to_image_dict(row) for row in self.get_all_images()]

        normalized = []
        for n in tag_names:
            s = (n or "").strip().lower()
            if s:
                normalized.append(s)
        normalized = list(dict.fromkeys(normalized))
        if not normalized:
            return [self._row_to_image_dict(row) for row in self.get_all_images()]

        placeholders = ",".join("?" * len(normalized))
        query = f"""
            SELECT {self._image_columns("i")}
            FROM images i
            JOIN image_tags it ON i.id = it.image_id
            JOIN tags t ON t.id = it.tag_id
            WHERE LOWER(TRIM(t.name)) IN ({placeholders})
            GROUP BY i.id
            HAVING COUNT(DISTINCT LOWER(TRIM(t.name))) = ?
            ORDER BY i.created_at DESC
        """
        return self._fetch_image_dicts(query, [*normalized, len(normalized)])

    def search_images_by_name(self, keyword: str) -> list[tuple]:
        """按名称搜索图片"""
        return self._fetch_images(
            f"""
            SELECT {self._image_columns()}
            FROM images
            WHERE name LIKE ?
            ORDER BY created_at DESC
            """,
            (f"%{keyword}%",),
        )

    def get_all_images_with_tags(self, limit: int | None = None) -> list[dict]:
        """获取全部图片及标签元数据（按创建时间倒序）"""
        limit_sql = ""
        params: list = []
        if limit and limit > 0:
            limit_sql = "LIMIT ?"
            params.append(limit)

        rows = self._fetch_images(
            f"""
            SELECT
                {self._image_columns("i")},
                i.created_at,
                GROUP_CONCAT(DISTINCT t.name) AS tag_names
            FROM images i
            LEFT JOIN image_tags it ON i.id = it.image_id
            LEFT JOIN tags t ON t.id = it.tag_id
            GROUP BY i.id
            ORDER BY i.created_at DESC
            {limit_sql}
            """,
            params,
        )

        result: list[dict] = []
        for row in rows:
            tags = [tag.strip() for tag in (row[9] or "").split(",") if tag and tag.strip()]
            info = self._row_to_image_dict(row[:8])
            info["created_at"] = row[8]
            info["tags"] = tags
            result.append(info)
        return result

    def search_by_keywords(self, keywords: list[str], top_k: int = 3) -> list[tuple]:
        """按关键词列表模糊匹配标签，返回按命中标签数量排序的图片（tuple）"""
        if not keywords:
            return []
        conditions = " OR ".join(["LOWER(TRIM(t.name)) LIKE ?" for _ in keywords])
        params = [f"%{(kw or '').strip().lower()}%" for kw in keywords if (kw or "").strip()]
        if not params:
            return []
        query = f"""
            SELECT {self._image_columns("i")}, COUNT(DISTINCT t.id) AS match_count
            FROM images i
            JOIN image_tags it ON i.id = it.image_id
            JOIN tags t ON it.tag_id = t.id
            WHERE {conditions}
            GROUP BY i.id
            ORDER BY match_count DESC, i.id DESC
            LIMIT ?
        """
        rows = self._fetch_images(query, [*params, top_k])
        return [row[:8] for row in rows]

    def ensure_usage_history_table(self):
        """确保 usage_history 表存在"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id INTEGER REFERENCES images(id) ON DELETE CASCADE,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def record_usage(self, image_id: int):
        """记录一次表情包使用"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usage_history (image_id, used_at) VALUES (?, ?)",
                (image_id, datetime.now().isoformat()),
            )
            conn.commit()

    def get_usage_history(self, since: Optional[str] = None) -> list[tuple]:
        """获取使用历史记录"""
        with self._connect() as conn:
            cursor = conn.cursor()
            if since:
                cursor.execute(
                    """
                    SELECT id, image_id, used_at
                    FROM usage_history
                    WHERE used_at >= ?
                    ORDER BY used_at DESC
                    """,
                    (since,),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, image_id, used_at
                    FROM usage_history
                    ORDER BY used_at DESC
                    """
                )
            return cursor.fetchall()

    def clear_usage_history(self):
        """清空全部使用历史记录"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM usage_history")
            conn.commit()
