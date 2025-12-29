"""
SQLite Database Module for undefined
Uses aiosqlite for async database operations

Tables:
- users: User data (uuid, nickname, position, inventory, status)
- objects: World objects (id, name, position, description, properties)
- materials: Discovered materials (id, name, recipe, properties)
- logs: History logs (id, timestamp, content)
- rules: World rules/settings (key, value as JSON)
- supporters: Supporter information
- object_types: Blueprints for craftable items
"""

import os
import json
import aiosqlite
from datetime import datetime
from typing import Dict, List, Optional, Any
import gzip

DB_FILE = "world.db"
MAX_HISTORY_CACHE = int(os.getenv("MAX_HISTORY_CACHE", "500"))

# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                         DATABASE SCHEMA                                        ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

SCHEMA = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    uuid TEXT PRIMARY KEY,
    nickname TEXT NOT NULL,
    x INTEGER DEFAULT 0,
    y INTEGER DEFAULT 0,
    z INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Healthy',
    inventory TEXT DEFAULT '{}',
    attributes TEXT DEFAULT '{}',
    skills TEXT DEFAULT '{}',
    name_set INTEGER DEFAULT 0,
    is_dead INTEGER DEFAULT 0,
    time_offset REAL DEFAULT 0,
    last_exercise TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Objects table (world objects)
CREATE TABLE IF NOT EXISTS objects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    x INTEGER DEFAULT 0,
    y INTEGER DEFAULT 0,
    z INTEGER DEFAULT 0,
    description TEXT DEFAULT '',
    properties TEXT DEFAULT '{}',
    indestructible INTEGER DEFAULT 0,
    creator TEXT DEFAULT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Materials table (discovered materials)
CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_en TEXT,
    type TEXT DEFAULT 'invented',
    recipe TEXT DEFAULT '',
    description TEXT DEFAULT '',
    properties TEXT DEFAULT '{}',
    creator TEXT DEFAULT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Logs table (history)
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    actor TEXT DEFAULT NULL,
    action TEXT DEFAULT '',
    result TEXT DEFAULT '',
    content TEXT DEFAULT ''
);

-- Rules table (key-value settings)
CREATE TABLE IF NOT EXISTS rules (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT '{}'
);

-- Supporters table
CREATE TABLE IF NOT EXISTS supporters (
    uuid TEXT PRIMARY KEY,
    nickname TEXT NOT NULL,
    is_supporter INTEGER DEFAULT 1,
    supporter_name TEXT DEFAULT NULL,
    amount REAL DEFAULT 0,
    granted_by TEXT DEFAULT NULL,
    registered_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Object Types table (blueprints)
CREATE TABLE IF NOT EXISTS object_types (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_en TEXT,
    category TEXT DEFAULT 'misc',
    base_materials TEXT DEFAULT '[]',
    description TEXT DEFAULT '',
    properties TEXT DEFAULT '{}',
    creator TEXT DEFAULT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Natural Elements table
CREATE TABLE IF NOT EXISTS natural_elements (
    name TEXT PRIMARY KEY,
    type TEXT DEFAULT '',
    hardness REAL DEFAULT 0,
    density REAL DEFAULT 0,
    melting_point REAL DEFAULT NULL,
    boiling_point REAL DEFAULT NULL,
    flammable INTEGER DEFAULT 0,
    properties TEXT DEFAULT '{}'
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_objects_position ON objects(x, y, z);
CREATE INDEX IF NOT EXISTS idx_users_nickname ON users(nickname);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
"""


class Database:
    """Async SQLite database manager"""
    
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Connect to database and initialize schema"""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        
        # Optimize for high concurrency and robustness
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA synchronous=NORMAL")
        await self._connection.execute("PRAGMA busy_timeout=5000")
        
        await self._connection.executescript(SCHEMA)
        
        # === Migration: Ensure new columns exist for existing users ===
        try:
            # Check for attributes column
            async with self.conn.execute("PRAGMA table_info(users)") as cursor:
                columns = [row["name"] for row in await cursor.fetchall()]
                
                if "attributes" not in columns:
                    print("[DB MIGRATION] Adding 'attributes' column to users table...")
                    await self.conn.execute("ALTER TABLE users ADD COLUMN attributes TEXT DEFAULT '{}'")
                
                if "skills" not in columns:
                    print("[DB MIGRATION] Adding 'skills' column to users table...")
                    await self.conn.execute("ALTER TABLE users ADD COLUMN skills TEXT DEFAULT '{}'")
                
                if "time_offset" not in columns:
                    print("[DB MIGRATION] Adding 'time_offset' column to users table...")
                    await self.conn.execute("ALTER TABLE users ADD COLUMN time_offset REAL DEFAULT 0")
                
                if "last_exercise" not in columns:
                    print("[DB MIGRATION] Adding 'last_exercise' column to users table...")
                    await self.conn.execute("ALTER TABLE users ADD COLUMN last_exercise TEXT DEFAULT '{}'")
                    
            await self._connection.commit()
        except Exception as e:
            print(f"[DB MIGRATION ERROR] {e}")
            
        print(f"[DB] Connected to {self.db_path} (WAL mode enabled)")
    
    async def close(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            print("[DB] Connection closed")
    
    @property
    def conn(self) -> aiosqlite.Connection:
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection
    
    # ═══════════════════════════════════════════════════════════════════
    #                           USERS
    # ═══════════════════════════════════════════════════════════════════
    
    async def get_user(self, uuid: str) -> Optional[dict]:
        """Get user by UUID"""
        async with self.conn.execute(
            "SELECT * FROM users WHERE uuid = ?", (uuid,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_user_dict(row)
        return None
    
    async def save_user(self, uuid: str, data: dict) -> bool:
        """Insert or update user"""
        try:
            inventory = json.dumps(data.get("inventory", {}), ensure_ascii=False)
            attributes = json.dumps(data.get("attributes", {}), ensure_ascii=False)
            skills = json.dumps(data.get("skills", {}), ensure_ascii=False)
            position = data.get("position", {"x": 0, "y": 0, "z": 0})
            if isinstance(position, list):
                x, y = position[0], position[1]
                z = position[2] if len(position) > 2 else 0
            else:
                x = position.get("x", 0)
                y = position.get("y", 0)
                z = position.get("z", 0)
            
            await self.conn.execute("""
                INSERT INTO users (uuid, nickname, x, y, z, status, inventory, attributes, skills, name_set, is_dead, time_offset, last_exercise)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET
                    nickname = excluded.nickname,
                    x = excluded.x,
                    y = excluded.y,
                    z = excluded.z,
                    status = excluded.status,
                    inventory = excluded.inventory,
                    attributes = excluded.attributes,
                    skills = excluded.skills,
                    name_set = excluded.name_set,
                    is_dead = excluded.is_dead,
                    time_offset = excluded.time_offset,
                    last_exercise = excluded.last_exercise
            """, (
                uuid,
                data.get("nickname", "Unknown"),
                int(x), int(y), int(z),
                data.get("status", "Healthy"),
                inventory,
                attributes,
                skills,
                1 if data.get("name_set", False) else 0,
                1 if data.get("is_dead", False) else 0,
                float(data.get("time_offset", 0)),
                json.dumps(data.get("last_exercise", {}), ensure_ascii=False)
            ))
            await self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] save_user: {e}")
            return False
    
    async def get_all_users(self) -> Dict[str, dict]:
        """Get all users as dict[uuid -> user_data]"""
        users = {}
        async with self.conn.execute("SELECT * FROM users") as cursor:
            async for row in cursor:
                users[row["uuid"]] = self._row_to_user_dict(row)
        return users
    
    def _row_to_user_dict(self, row) -> dict:
        """Convert DB row to user dict (API compatible format)"""
        return {
            "nickname": row["nickname"],
            "name_set": bool(row["name_set"]),
            "position": {"x": row["x"], "y": row["y"], "z": row["z"]},
            "status": row["status"],
            "inventory": json.loads(row["inventory"] or "{}"),
            "attributes": json.loads(row["attributes"] or "{}"),
            "skills": json.loads(row["skills"] or "{}"),
            "is_dead": bool(row["is_dead"]),
            "time_offset": float(row["time_offset"] or 0),
            "last_exercise": json.loads(row["last_exercise"] or "{}"),
            "created_at": row["created_at"]
        }
    
    # ═══════════════════════════════════════════════════════════════════
    #                           OBJECTS
    # ═══════════════════════════════════════════════════════════════════
    
    async def get_object(self, obj_id: str) -> Optional[dict]:
        """Get object by ID"""
        async with self.conn.execute(
            "SELECT * FROM objects WHERE id = ?", (obj_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_object_dict(row)
        return None
    
    async def save_object(self, obj_id: str, data: dict) -> bool:
        """Insert or update object"""
        try:
            properties = json.dumps(data.get("properties", {}), ensure_ascii=False)
            position = data.get("position", [0, 0, 0])
            if isinstance(position, list):
                x = position[0] if len(position) > 0 else 0
                y = position[1] if len(position) > 1 else 0
                z = position[2] if len(position) > 2 else 0
            else:
                x, y, z = 0, 0, 0
            
            await self.conn.execute("""
                INSERT INTO objects (id, name, x, y, z, description, properties, indestructible, creator)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    x = excluded.x,
                    y = excluded.y,
                    z = excluded.z,
                    description = excluded.description,
                    properties = excluded.properties,
                    indestructible = excluded.indestructible,
                    creator = excluded.creator
            """, (
                obj_id,
                data.get("name", obj_id),
                int(x), int(y), int(z),
                data.get("description", ""),
                properties,
                1 if data.get("indestructible", False) else 0,
                data.get("creator")
            ))
            await self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] save_object: {e}")
            return False
    
    async def delete_object(self, obj_id: str) -> bool:
        """Delete object by ID"""
        try:
            await self.conn.execute("DELETE FROM objects WHERE id = ?", (obj_id,))
            await self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] delete_object: {e}")
            return False
    
    async def get_all_objects(self) -> Dict[str, dict]:
        """Get all objects as dict[id -> object_data]"""
        objects = {}
        async with self.conn.execute("SELECT * FROM objects") as cursor:
            async for row in cursor:
                objects[row["id"]] = self._row_to_object_dict(row)
        return objects
    
    async def get_objects_near(self, x: int, y: int, radius: int = 10) -> List[dict]:
        """Get objects within Manhattan distance radius"""
        objects = []
        async with self.conn.execute("""
            SELECT * FROM objects 
            WHERE ABS(x - ?) + ABS(y - ?) <= ?
        """, (x, y, radius)) as cursor:
            async for row in cursor:
                objects.append(self._row_to_object_dict(row))
        return objects
    
    def _row_to_object_dict(self, row) -> dict:
        """Convert DB row to object dict (API compatible format)"""
        return {
            "id": row["id"],
            "name": row["name"],
            "position": [row["x"], row["y"], row["z"]],
            "description": row["description"],
            "properties": json.loads(row["properties"] or "{}"),
            "indestructible": bool(row["indestructible"]),
            "creator": row["creator"]
        }
    
    # ═══════════════════════════════════════════════════════════════════
    #                           MATERIALS
    # ═══════════════════════════════════════════════════════════════════
    
    async def get_material(self, material_id: str) -> Optional[dict]:
        """Get material by ID"""
        async with self.conn.execute(
            "SELECT * FROM materials WHERE id = ?", (material_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_material_dict(row)
        return None
    
    async def save_material(self, material_id: str, data: dict) -> bool:
        """Insert or update material"""
        try:
            properties = json.dumps(data.get("properties", {}), ensure_ascii=False)
            await self.conn.execute("""
                INSERT INTO materials (id, name, name_en, type, recipe, description, properties, creator, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    name_en = excluded.name_en,
                    type = excluded.type,
                    recipe = excluded.recipe,
                    description = excluded.description,
                    properties = excluded.properties,
                    creator = excluded.creator
            """, (
                material_id,
                data.get("name", material_id),
                data.get("name_en", data.get("name", material_id)),
                data.get("type", "invented"),
                data.get("recipe", ""),
                data.get("description", ""),
                properties,
                data.get("creator"),
                data.get("created_at", datetime.now().isoformat())
            ))
            await self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] save_material: {e}")
            return False
    
    async def get_all_materials(self) -> Dict[str, dict]:
        """Get all materials as dict"""
        materials = {"_README": {"description": "Discovered materials stored here", "total_discoveries": 0}}
        count = 0
        async with self.conn.execute("SELECT * FROM materials") as cursor:
            async for row in cursor:
                materials[row["id"]] = self._row_to_material_dict(row)
                count += 1
        materials["_README"]["total_discoveries"] = count
        return materials
    
    def _row_to_material_dict(self, row) -> dict:
        """Convert DB row to material dict"""
        return {
            "id": row["id"],
            "name": row["name"],
            "name_en": row["name_en"],
            "type": row["type"],
            "recipe": row["recipe"],
            "description": row["description"],
            "properties": json.loads(row["properties"] or "{}"),
            "creator": row["creator"],
            "created_at": row["created_at"]
        }
    
    # ═══════════════════════════════════════════════════════════════════
    #                           OBJECT TYPES (Blueprints)
    # ═══════════════════════════════════════════════════════════════════
    
    async def get_object_type(self, type_id: str) -> Optional[dict]:
        """Get object type by ID"""
        async with self.conn.execute(
            "SELECT * FROM object_types WHERE id = ?", (type_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_object_type_dict(row)
        return None
    
    async def save_object_type(self, type_id: str, data: dict) -> bool:
        """Insert or update object type (blueprint)"""
        try:
            properties = json.dumps(data.get("properties", {}), ensure_ascii=False)
            base_materials = json.dumps(data.get("base_materials", []), ensure_ascii=False)
            await self.conn.execute("""
                INSERT INTO object_types (id, name, name_en, category, base_materials, description, properties, creator, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    name_en = excluded.name_en,
                    category = excluded.category,
                    base_materials = excluded.base_materials,
                    description = excluded.description,
                    properties = excluded.properties,
                    creator = excluded.creator
            """, (
                type_id,
                data.get("name", type_id),
                data.get("name_en", data.get("name", type_id)),
                data.get("category", "misc"),
                base_materials,
                data.get("description", ""),
                properties,
                data.get("creator"),
                data.get("created_at", datetime.now().isoformat())
            ))
            await self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] save_object_type: {e}")
            return False
    
    async def get_all_object_types(self) -> Dict[str, dict]:
        """Get all object types as dict"""
        types = {"_README": {"description": "User-created object blueprints registry", "total_blueprints": 0}}
        count = 0
        async with self.conn.execute("SELECT * FROM object_types") as cursor:
            async for row in cursor:
                types[row["id"]] = self._row_to_object_type_dict(row)
                count += 1
        types["_README"]["total_blueprints"] = count
        return types
    
    def _row_to_object_type_dict(self, row) -> dict:
        """Convert DB row to object type dict"""
        return {
            "id": row["id"],
            "name": row["name"],
            "name_en": row["name_en"],
            "category": row["category"],
            "base_materials": json.loads(row["base_materials"] or "[]"),
            "description": row["description"],
            "properties": json.loads(row["properties"] or "{}"),
            "creator": row["creator"],
            "created_at": row["created_at"]
        }
    
    # ═══════════════════════════════════════════════════════════════════
    #                           LOGS (History)
    # ═══════════════════════════════════════════════════════════════════
    
    async def add_log(self, timestamp: str, actor: str = None, action: str = "", result: str = "") -> bool:
        """Add a history log entry"""
        try:
            await self.conn.execute("""
                INSERT INTO logs (timestamp, actor, action, result)
                VALUES (?, ?, ?, ?)
            """, (timestamp, actor, action, result))
            await self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] add_log: {e}")
            return False
    
    async def get_recent_logs(self, limit: int = 100) -> List[dict]:
        """Get recent log entries"""
        logs = []
        async with self.conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        ) as cursor:
            async for row in cursor:
                logs.append({
                    "timestamp": row["timestamp"],
                    "actor": row["actor"],
                    "action": row["action"],
                    "result": row["result"]
                })
        logs.reverse()  # Oldest first
        return logs
    
    async def get_all_logs(self) -> List[dict]:
        """Get all log entries"""
        logs = []
        async with self.conn.execute("SELECT * FROM logs ORDER BY id") as cursor:
            async for row in cursor:
                logs.append({
                    "timestamp": row["timestamp"],
                    "actor": row["actor"],
                    "action": row["action"],
                    "result": row["result"]
                })
        return logs

    # ═══════════════════════════════════════════════════════════════════
    #                      LOG ARCHIVE + RETENTION
    # ═══════════════════════════════════════════════════════════════════

    async def archive_and_trim_logs(
        self,
        archive_dir: str,
        keep_last: int = 50000,
        compress_gzip: bool = True,
    ) -> Optional[dict]:
        """
        Archive old logs to a JSONL (optionally gzipped) file and trim the logs table to keep_last rows.

        - World state (objects/users/materials/...) is NOT affected.
        - This only touches the 'logs' table.
        Returns a dict with archive metadata if an archive occurred, otherwise None.
        """
        if keep_last <= 0:
            raise ValueError("keep_last must be > 0")

        # Count rows
        async with self.conn.execute("SELECT COUNT(*) AS cnt FROM logs") as cursor:
            row = await cursor.fetchone()
            total = int(row["cnt"]) if row else 0

        if total <= keep_last:
            return None

        # Find cutoff id: keep rows with id >= cutoff_id
        offset = keep_last - 1
        async with self.conn.execute(
            "SELECT id FROM logs ORDER BY id DESC LIMIT 1 OFFSET ?",
            (offset,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            cutoff_id = int(row["id"])

        # Determine archive range
        async with self.conn.execute("SELECT MIN(id) AS min_id, MAX(id) AS max_id FROM logs WHERE id < ?", (cutoff_id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row["min_id"] is None:
                return None
            min_id = int(row["min_id"])
            max_id = int(row["max_id"])

        os.makedirs(archive_dir, exist_ok=True)
        date_tag = datetime.now().strftime("%Y%m%d")
        base_name = f"logs_{date_tag}_{min_id}-{max_id}.jsonl"
        archive_path = os.path.join(archive_dir, base_name + (".gz" if compress_gzip else ""))

        # Stream rows to file (avoid loading everything into RAM)
        opener = (lambda p: gzip.open(p, "wt", encoding="utf-8")) if compress_gzip else (lambda p: open(p, "w", encoding="utf-8"))
        written = 0
        with opener(archive_path) as f:
            async with self.conn.execute(
                "SELECT id, timestamp, actor, action, result FROM logs WHERE id < ? ORDER BY id",
                (cutoff_id,),
            ) as cursor:
                async for r in cursor:
                    rec = {
                        "id": int(r["id"]),
                        "timestamp": r["timestamp"],
                        "actor": r["actor"],
                        "action": r["action"],
                        "result": r["result"],
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    written += 1

        # Trim old rows from DB
        await self.conn.execute("DELETE FROM logs WHERE id < ?", (cutoff_id,))
        await self.conn.commit()

        return {
            "archived": written,
            "total_before": total,
            "kept": keep_last,
            "cutoff_id": cutoff_id,
            "min_id": min_id,
            "max_id": max_id,
            "path": archive_path,
        }
    
    # ═══════════════════════════════════════════════════════════════════
    #                           SUPPORTERS
    # ═══════════════════════════════════════════════════════════════════
    
    async def get_supporter(self, uuid: str) -> Optional[dict]:
        """Get supporter by UUID"""
        async with self.conn.execute(
            "SELECT * FROM supporters WHERE uuid = ?", (uuid,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_supporter_dict(row)
        return None
    
    async def save_supporter(self, uuid: str, data: dict) -> bool:
        """Insert or update supporter"""
        try:
            await self.conn.execute("""
                INSERT INTO supporters (uuid, nickname, is_supporter, supporter_name, amount, granted_by, registered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET
                    nickname = excluded.nickname,
                    is_supporter = excluded.is_supporter,
                    supporter_name = excluded.supporter_name,
                    amount = excluded.amount,
                    granted_by = excluded.granted_by
            """, (
                uuid,
                data.get("nickname", "Unknown"),
                1 if data.get("is_supporter", True) else 0,
                data.get("supporter_name"),
                data.get("amount", 0),
                data.get("granted_by"),
                data.get("registered_at", datetime.now().isoformat())
            ))
            await self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] save_supporter: {e}")
            return False
    
    async def get_all_supporters(self) -> Dict[str, dict]:
        """Get all supporters as dict"""
        supporters = {
            "_README": "Add user UUIDs here to mark them as supporters.",
            "_example": "uuid-here: { \"nickname\": \"name\", \"is_supporter\": true }"
        }
        async with self.conn.execute("SELECT * FROM supporters") as cursor:
            async for row in cursor:
                supporters[row["uuid"]] = self._row_to_supporter_dict(row)
        return supporters
    
    def _row_to_supporter_dict(self, row) -> dict:
        """Convert DB row to supporter dict"""
        return {
            "nickname": row["nickname"],
            "is_supporter": bool(row["is_supporter"]),
            "supporter_name": row["supporter_name"],
            "amount": row["amount"],
            "granted_by": row["granted_by"],
            "registered_at": row["registered_at"]
        }
    
    # ═══════════════════════════════════════════════════════════════════
    #                           NATURAL ELEMENTS
    # ═══════════════════════════════════════════════════════════════════
    
    async def save_natural_element(self, name: str, data: dict) -> bool:
        """Insert or update natural element"""
        try:
            properties = json.dumps({k: v for k, v in data.items() 
                                    if k not in ["name", "type", "hardness", "density", "melting_point", "boiling_point", "flammable"]},
                                   ensure_ascii=False)
            await self.conn.execute("""
                INSERT INTO natural_elements (name, type, hardness, density, melting_point, boiling_point, flammable, properties)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    type = excluded.type,
                    hardness = excluded.hardness,
                    density = excluded.density,
                    melting_point = excluded.melting_point,
                    boiling_point = excluded.boiling_point,
                    flammable = excluded.flammable,
                    properties = excluded.properties
            """, (
                name,
                data.get("type", ""),
                data.get("hardness", 0),
                data.get("density", 0),
                data.get("melting_point"),
                data.get("boiling_point"),
                1 if data.get("flammable", False) else 0,
                properties
            ))
            await self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] save_natural_element: {e}")
            return False
    
    async def get_all_natural_elements(self) -> Dict[str, dict]:
        """Get all natural elements as dict"""
        elements = {}
        async with self.conn.execute("SELECT * FROM natural_elements") as cursor:
            async for row in cursor:
                elem = {
                    "name": row["name"],
                    "type": row["type"],
                    "hardness": row["hardness"],
                    "density": row["density"]
                }
                if row["melting_point"] is not None:
                    elem["melting_point"] = row["melting_point"]
                if row["boiling_point"] is not None:
                    elem["boiling_point"] = row["boiling_point"]
                if row["flammable"]:
                    elem["flammable"] = True
                extra = json.loads(row["properties"] or "{}")
                elem.update(extra)
                elements[row["name"].lower()] = elem
        return elements
    
    # ═══════════════════════════════════════════════════════════════════
    #                           RULES (Key-Value)
    # ═══════════════════════════════════════════════════════════════════
    
    async def get_rule(self, key: str) -> Optional[Any]:
        """Get rule value by key"""
        async with self.conn.execute(
            "SELECT value FROM rules WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row["value"])
        return None
    
    async def set_rule(self, key: str, value: Any) -> bool:
        """Set rule value"""
        try:
            value_json = json.dumps(value, ensure_ascii=False)
            await self.conn.execute("""
                INSERT INTO rules (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value_json))
            await self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] set_rule: {e}")
            return False
    
    async def get_all_rules(self) -> Dict[str, Any]:
        """Get all rules as dict"""
        rules = {}
        async with self.conn.execute("SELECT * FROM rules") as cursor:
            async for row in cursor:
                rules[row["key"]] = json.loads(row["value"])
        return rules
    
    # ═══════════════════════════════════════════════════════════════════
    #                    FULL WORLD STATE (API Compatible)
    # ═══════════════════════════════════════════════════════════════════
    
    async def get_full_world_state(self) -> dict:
        """Get complete world state in the original JSON format for API compatibility"""
        server_time = await self.get_rule("server_time_started")
        
        return {
            "objects": await self.get_all_objects(),
            "materials": await self.get_all_materials(),
            "object_types": await self.get_all_object_types(),
            "natural_elements": await self.get_all_natural_elements(),
            "biomes_discovered": await self.get_rule("biomes_discovered") or {},
            # Keep history bounded in RAM; full logs are stored in SQLite.
            "history": await self.get_recent_logs(limit=MAX_HISTORY_CACHE),
            "players": {},  # Legacy, kept empty
            "users": await self.get_all_users(),
            "supporters": await self.get_all_supporters(),
            "server_time_started": server_time or datetime.now().isoformat()
        }
    
    async def export_to_json(self) -> str:
        """Export full world state to JSON string (for backup)"""
        state = await self.get_full_world_state()
        return json.dumps(state, ensure_ascii=False, indent=2)


# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                         MIGRATION FUNCTIONS                                    ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

async def migrate_from_json(db: Database, json_data: dict):
    """Migrate data from world_data.json to SQLite database"""
    print("[MIGRATION] Starting migration from JSON to SQLite...")
    
    # Migrate users
    users = json_data.get("users", {})
    for uuid, user_data in users.items():
        if isinstance(user_data, str):
            # Old format: just nickname string
            user_data = {"nickname": user_data, "name_set": True}
        await db.save_user(uuid, user_data)
    print(f"[MIGRATION] Users: {len(users)} migrated")
    
    # Migrate objects
    objects = json_data.get("objects", {})
    for obj_id, obj_data in objects.items():
        await db.save_object(obj_id, obj_data)
    print(f"[MIGRATION] Objects: {len(objects)} migrated")
    
    # Migrate materials
    materials = json_data.get("materials", {})
    for mat_id, mat_data in materials.items():
        if mat_id != "_README" and isinstance(mat_data, dict):
            await db.save_material(mat_id, mat_data)
    print(f"[MIGRATION] Materials: {len([k for k in materials if k != '_README'])} migrated")
    
    # Migrate object types (blueprints)
    object_types = json_data.get("object_types", {})
    for type_id, type_data in object_types.items():
        if type_id != "_README" and isinstance(type_data, dict):
            await db.save_object_type(type_id, type_data)
    print(f"[MIGRATION] Object Types: {len([k for k in object_types if k != '_README'])} migrated")
    
    # Migrate history logs
    history = json_data.get("history", [])
    for entry in history:
        await db.add_log(
            timestamp=entry.get("timestamp", datetime.now().isoformat()),
            actor=entry.get("actor"),
            action=entry.get("action", ""),
            result=entry.get("result", "")
        )
    print(f"[MIGRATION] History logs: {len(history)} migrated")
    
    # Migrate supporters
    supporters = json_data.get("supporters", {})
    for uuid, sup_data in supporters.items():
        if uuid not in ["_README", "_example"] and isinstance(sup_data, dict):
            await db.save_supporter(uuid, sup_data)
    print(f"[MIGRATION] Supporters: {len([k for k in supporters if not k.startswith('_')])} migrated")
    
    # Migrate natural elements
    natural_elements = json_data.get("natural_elements", {})
    for name, elem_data in natural_elements.items():
        await db.save_natural_element(name, elem_data)
    print(f"[MIGRATION] Natural Elements: {len(natural_elements)} migrated")
    
    # Save rules
    await db.set_rule("server_time_started", json_data.get("server_time_started", datetime.now().isoformat()))
    await db.set_rule("biomes_discovered", json_data.get("biomes_discovered", {}))
    
    print("[MIGRATION] Migration completed successfully!")


# Global database instance
db: Optional[Database] = None

async def get_db() -> Database:
    """Get or create database instance"""
    global db
    if db is None:
        db = Database()
        await db.connect()
    return db

async def close_db():
    """Close database connection"""
    global db
    if db:
        await db.close()
        db = None

