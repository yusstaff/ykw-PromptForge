from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional
import json
import sqlite3


DEFAULT_CATEGORIES = [
    "主体",
    "场景",
    "风格",
    "镜头",
    "光影",
    "质量",
    "负面",
]

SYSTEM_CATEGORY_NAMES = [
    "Character",
    "BodyStyle",
    "FacialFeatures",
    "HairColor",
    "Hairstyle",
    "HairAccessory",
    "Outfit",
    "Pose",
    "Expression",
    "Scene",
    "Camera",
    "Lighting",
    "ColorPalette",
    "ArtStyle",
]


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


class PromptForgeDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_system INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS prompt_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    prompt_text TEXT NOT NULL DEFAULT '',
                    negative_prompt TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '',
                    weight REAL NOT NULL DEFAULT 1.0,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS reference_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_id INTEGER NOT NULL,
                    stored_path TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(prompt_id) REFERENCES prompt_items(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    positive_prompt TEXT NOT NULL,
                    negative_prompt TEXT NOT NULL,
                    item_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_prompt_items_category
                    ON prompt_items(category_id);
                CREATE INDEX IF NOT EXISTS idx_reference_images_prompt
                    ON reference_images(prompt_id);
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(categories)").fetchall()
            }
            if "is_system" not in columns:
                conn.execute(
                    "ALTER TABLE categories ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0"
                )

            count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            if count == 0:
                stamp = now_text()
                conn.executemany(
                    "INSERT INTO categories(name, sort_order, is_system, created_at) VALUES (?, ?, ?, ?)",
                    [(name, index, 0, stamp) for index, name in enumerate(DEFAULT_CATEGORIES)],
                )
            self._ensure_system_categories(conn)

    def _ensure_system_categories(self, conn: sqlite3.Connection) -> None:
        stamp = now_text()
        self._migrate_system_category_aliases(conn)
        existing = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM categories").fetchall()
        }
        for index, name in enumerate(SYSTEM_CATEGORY_NAMES):
            if name in existing:
                conn.execute(
                    "UPDATE categories SET is_system = 1, sort_order = ? WHERE name = ?",
                    (index, name),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO categories(name, sort_order, is_system, created_at)
                    VALUES (?, ?, 1, ?)
                    """,
                    (name, index, stamp),
                )
        conn.execute(
            """
            UPDATE categories
            SET is_system = 0
            WHERE name NOT IN ({})
            """.format(",".join("?" for _ in SYSTEM_CATEGORY_NAMES)),
            SYSTEM_CATEGORY_NAMES,
        )

    def _migrate_system_category_aliases(self, conn: sqlite3.Connection) -> None:
        aliases = {
            "Face": "FacialFeatures",
        }
        for old_name, new_name in aliases.items():
            old_row = conn.execute(
                "SELECT id FROM categories WHERE name = ?",
                (old_name,),
            ).fetchone()
            if not old_row:
                continue

            new_row = conn.execute(
                "SELECT id FROM categories WHERE name = ?",
                (new_name,),
            ).fetchone()
            if not new_row:
                conn.execute(
                    "UPDATE categories SET name = ? WHERE id = ?",
                    (new_name, old_row["id"]),
                )
                continue

            conn.execute(
                "UPDATE prompt_items SET category_id = ? WHERE category_id = ?",
                (new_row["id"], old_row["id"]),
            )
            conn.execute("DELETE FROM categories WHERE id = ?", (old_row["id"],))

    def list_categories(self) -> List[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM categories ORDER BY is_system DESC, sort_order ASC, name ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def add_category(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("分类名称不能为空。")
        with self.connect() as conn:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) FROM categories WHERE is_system = 0"
            ).fetchone()[0]
            cursor = conn.execute(
                "INSERT INTO categories(name, sort_order, is_system, created_at) VALUES (?, ?, 0, ?)",
                (name, int(max_order) + 1, now_text()),
            )
            return int(cursor.lastrowid)

    def delete_category(self, category_id: int) -> None:
        with self.connect() as conn:
            category = conn.execute(
                "SELECT is_system FROM categories WHERE id = ?",
                (category_id,),
            ).fetchone()
            if category and int(category["is_system"]):
                raise ValueError("系统分类不可删除。")
            count = conn.execute(
                "SELECT COUNT(*) FROM prompt_items WHERE category_id = ?",
                (category_id,),
            ).fetchone()[0]
            if count:
                raise ValueError("这个分类下还有提示词，请先移动或删除提示词。")
            conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def list_items(self, category_id: Optional[int] = None, query: str = "") -> List[dict]:
        clauses = []
        params = []
        if category_id is not None:
            clauses.append("p.category_id = ?")
            params.append(category_id)
        if query.strip():
            like = f"%{query.strip()}%"
            clauses.append(
                "(p.title LIKE ? OR p.prompt_text LIKE ? OR p.negative_prompt LIKE ? OR p.tags LIKE ? OR c.name LIKE ?)"
            )
            params.extend([like, like, like, like, like])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT
                p.*,
                c.name AS category_name,
                c.sort_order AS category_order,
                c.is_system AS category_is_system,
                (SELECT COUNT(*) FROM reference_images r WHERE r.prompt_id = p.id) AS image_count
            FROM prompt_items p
            JOIN categories c ON c.id = p.category_id
            {where_sql}
            ORDER BY c.is_system DESC, c.sort_order ASC, p.updated_at DESC, p.title ASC
        """
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_item(self, item_id: int) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT p.*, c.name AS category_name, c.is_system AS category_is_system
                FROM prompt_items p
                JOIN categories c ON c.id = p.category_id
                WHERE p.id = ?
                """,
                (item_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_item(
        self,
        category_id: int,
        title: str,
        prompt_text: str,
        negative_prompt: str,
        tags: str,
        weight: float,
        notes: str,
    ) -> int:
        stamp = now_text()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO prompt_items(
                    category_id, title, prompt_text, negative_prompt,
                    tags, weight, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category_id,
                    title.strip(),
                    prompt_text.strip(),
                    negative_prompt.strip(),
                    tags.strip(),
                    float(weight),
                    notes.strip(),
                    stamp,
                    stamp,
                ),
            )
            return int(cursor.lastrowid)

    def update_item(
        self,
        item_id: int,
        category_id: int,
        title: str,
        prompt_text: str,
        negative_prompt: str,
        tags: str,
        weight: float,
        notes: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE prompt_items
                SET category_id = ?,
                    title = ?,
                    prompt_text = ?,
                    negative_prompt = ?,
                    tags = ?,
                    weight = ?,
                    notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    category_id,
                    title.strip(),
                    prompt_text.strip(),
                    negative_prompt.strip(),
                    tags.strip(),
                    float(weight),
                    notes.strip(),
                    now_text(),
                    item_id,
                ),
            )

    def delete_item(self, item_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM prompt_items WHERE id = ?", (item_id,))

    def list_images(self, prompt_id: int) -> List[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM reference_images
                WHERE prompt_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (prompt_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_referenced_image_paths(self) -> List[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT stored_path
                FROM reference_images
                WHERE stored_path != ''
                ORDER BY stored_path ASC
                """
            ).fetchall()
        return [row["stored_path"] for row in rows]

    def add_image(self, prompt_id: int, stored_path: str, original_name: str) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reference_images(prompt_id, stored_path, original_name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (prompt_id, stored_path, original_name, now_text()),
            )
            return int(cursor.lastrowid)

    def delete_image(self, image_id: int) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM reference_images WHERE id = ?",
                (image_id,),
            ).fetchone()
            if not row:
                return None
            conn.execute("DELETE FROM reference_images WHERE id = ?", (image_id,))
            return dict(row)

    def save_recipe(
        self,
        title: str,
        positive_prompt: str,
        negative_prompt: str,
        item_ids: Iterable[int],
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO recipes(title, positive_prompt, negative_prompt, item_ids_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    title.strip(),
                    positive_prompt.strip(),
                    negative_prompt.strip(),
                    json.dumps(list(item_ids), ensure_ascii=False),
                    now_text(),
                ),
            )
            return int(cursor.lastrowid)

    def list_recipes(self) -> List[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM recipes ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [dict(row) for row in rows]
