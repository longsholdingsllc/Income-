"""Data layer for the Income (Autopilot) backend.

Three backends behind one async API shaped like the subset of Motor the
app uses:

- If ``MONGO_URL`` is set, the real Motor/MongoDB client is used (original
  production behavior on Emergent).
- Else if ``DATABASE_URL`` is set, a Postgres store (same docs-table design)
  is used — this is the durable hosted option.
- Otherwise a built-in SQLite store is used, so the app runs anywhere with
  zero external services. Data lives in ``DATA_FILE`` (default
  ``backend/data.sqlite3``).

Supported operations (exactly what server.py uses):
find_one, find().sort().limit().to_list(), insert_one, update_one
($set/$inc, upsert), delete_one, delete_many, aggregate($match + $group/$sum).
Filters: equality plus $gte/$gt/$lte/$lt/$ne/$in. Projections: exclusion
({"_id": 0}) and simple inclusion ({"pro_until": 1}).
"""

import asyncio
import json
import os
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).parent


def get_db():
    """Return (client, db). client has a close() method in both modes."""
    mongo_url = os.environ.get("MONGO_URL", "").strip()
    if mongo_url:
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(mongo_url)
        db = client[os.environ.get("DB_NAME", "autopilot")]
        return client, db
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        pg = _PgDB(database_url)
        return pg, pg
    db_file = os.environ.get("DATA_FILE", str(ROOT_DIR / "data.sqlite3"))
    local = _LocalDB(db_file)
    return local, local


# ---------------- SQLite-backed implementation ----------------


def _matches(doc: dict, filt: dict) -> bool:
    for key, cond in (filt or {}).items():
        val = doc.get(key)
        if isinstance(cond, dict):
            for op, operand in cond.items():
                if op == "$gte":
                    if val is None or not val >= operand:
                        return False
                elif op == "$gt":
                    if val is None or not val > operand:
                        return False
                elif op == "$lte":
                    if val is None or not val <= operand:
                        return False
                elif op == "$lt":
                    if val is None or not val < operand:
                        return False
                elif op == "$ne":
                    if val == operand:
                        return False
                elif op == "$in":
                    if val not in operand:
                        return False
                else:
                    raise ValueError(f"Unsupported filter operator: {op}")
        else:
            if val != cond:
                return False
    return True


def _project(doc: dict, projection: dict | None) -> dict:
    if not projection:
        return dict(doc)
    inclusion = any(v == 1 for k, v in projection.items() if k != "_id")
    if inclusion:
        out = {k: doc[k] for k, v in projection.items() if v == 1 and k in doc}
        if projection.get("_id", 1) != 0 and "_id" in doc:
            out["_id"] = doc["_id"]
        return out
    out = dict(doc)
    for k, v in projection.items():
        if v == 0:
            out.pop(k, None)
    return out


class _Result:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Cursor:
    def __init__(self, docs):
        self._docs = docs
        self._sort = None
        self._limit = None

    def sort(self, key, direction=1):
        self._sort = (key, direction)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _materialize(self):
        docs = list(self._docs)
        if self._sort:
            key, direction = self._sort
            docs.sort(key=lambda d: (d.get(key) is None, d.get(key)), reverse=(direction < 0))
        if self._limit is not None:
            docs = docs[: self._limit]
        return docs

    async def to_list(self, n=None):
        docs = self._materialize()
        if n is not None:
            docs = docs[:n]
        return docs

    def __aiter__(self):
        self._iter = iter(self._materialize())
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _Collection:
    def __init__(self, db: "_LocalDB", name: str):
        self._db = db
        self._name = name

    # -- internal helpers (run inside the db lock) --
    def _all_docs(self):
        rows = self._db._exec(
            f"SELECT body FROM docs WHERE collection = ? ORDER BY {self._db._id_col}", (self._name,)
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def _save(self, doc):
        body = json.dumps(doc)
        pk = str(doc.get("id") or doc.get("user_id") or "")
        self._db._exec(
            "INSERT INTO docs (collection, pk, body) VALUES (?, ?, ?)",
            (self._name, pk, body),
        )
        self._db._conn.commit()

    def _replace_first(self, filt, new_doc):
        idc = self._db._id_col
        rows = self._db._exec(
            f"SELECT {idc}, body FROM docs WHERE collection = ? ORDER BY {idc}", (self._name,)
        ).fetchall()
        for row_id, body in rows:
            if _matches(json.loads(body), filt):
                self._db._exec(
                    f"UPDATE docs SET body = ? WHERE {idc} = ?", (json.dumps(new_doc), row_id)
                )
                self._db._conn.commit()
                return True
        return False

    def _delete_matching(self, filt, limit_one=False):
        idc = self._db._id_col
        rows = self._db._exec(
            f"SELECT {idc}, body FROM docs WHERE collection = ? ORDER BY {idc}", (self._name,)
        ).fetchall()
        count = 0
        for row_id, body in rows:
            if _matches(json.loads(body), filt):
                self._db._exec(f"DELETE FROM docs WHERE {idc} = ?", (row_id,))
                count += 1
                if limit_one:
                    break
        self._db._conn.commit()
        return count

    # -- public Motor-shaped API --
    async def find_one(self, filt=None, projection=None):
        async with self._db._lock:
            for doc in self._all_docs():
                if _matches(doc, filt or {}):
                    return _project(doc, projection)
            return None

    def find(self, filt=None, projection=None):
        docs = self._db._snapshot(self._name, filt or {}, projection)
        return _Cursor(docs)

    async def insert_one(self, doc):
        async with self._db._lock:
            self._save(dict(doc))
        return _Result(inserted_id=doc.get("id"))

    async def update_one(self, filt, update, upsert=False):
        async with self._db._lock:
            docs = self._all_docs()
            target = None
            for doc in docs:
                if _matches(doc, filt or {}):
                    target = doc
                    break
            if target is None:
                if not upsert:
                    return _Result(matched_count=0, modified_count=0, upserted_id=None)
                target = {k: v for k, v in (filt or {}).items() if not isinstance(v, dict)}
                for k, v in update.get("$set", {}).items():
                    target[k] = v
                for k, v in update.get("$inc", {}).items():
                    target[k] = float(target.get(k, 0)) + float(v)
                self._save(target)
                return _Result(matched_count=0, modified_count=0, upserted_id=target.get("id"))
            new_doc = dict(target)
            for k, v in update.get("$set", {}).items():
                new_doc[k] = v
            for k, v in update.get("$inc", {}).items():
                new_doc[k] = float(new_doc.get(k, 0)) + float(v)
            self._replace_first(filt, new_doc)
            return _Result(matched_count=1, modified_count=1, upserted_id=None)

    async def delete_one(self, filt):
        async with self._db._lock:
            n = self._delete_matching(filt or {}, limit_one=True)
        return _Result(deleted_count=n)

    async def delete_many(self, filt):
        async with self._db._lock:
            n = self._delete_matching(filt or {})
        return _Result(deleted_count=n)

    def aggregate(self, pipeline):
        docs = self._db._snapshot(self._name, {}, None)
        for stage in pipeline:
            if "$match" in stage:
                docs = [d for d in docs if _matches(d, stage["$match"])]
            elif "$group" in stage:
                spec = stage["$group"]
                id_expr = spec.get("_id")
                groups: dict = {}
                order: list = []
                for doc in docs:
                    if id_expr is None:
                        key = None
                    elif isinstance(id_expr, str) and id_expr.startswith("$"):
                        key = doc.get(id_expr[1:])
                    else:
                        key = id_expr
                    if key not in groups:
                        groups[key] = {"_id": key}
                        order.append(key)
                    out = groups[key]
                    for out_field, agg in spec.items():
                        if out_field == "_id":
                            continue
                        if "$sum" in agg:
                            expr = agg["$sum"]
                            if isinstance(expr, str) and expr.startswith("$"):
                                val = doc.get(expr[1:], 0) or 0
                            else:
                                val = expr
                            out[out_field] = out.get(out_field, 0) + float(val)
                docs = [groups[k] for k in order]
            else:
                raise ValueError(f"Unsupported aggregate stage: {stage}")
        return _Cursor(docs)


class _LocalDB:
    _pg = False

    def __init__(self, path: str):
        self._path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS docs (collection TEXT, pk TEXT, body TEXT)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_docs_collection ON docs (collection)"
        )
        self._conn.commit()
        self._lock = asyncio.Lock()
        self._collections: dict[str, _Collection] = {}

    @property
    def _id_col(self):
        return "seq" if self._pg else "rowid"

    def _q(self, sql: str) -> str:
        """Translate ? placeholders for the active dialect."""
        return sql.replace("?", "%s") if self._pg else sql

    def _exec(self, sql: str, params=()):
        return self._conn.execute(self._q(sql), params)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._collections:
            self._collections[name] = _Collection(self, name)
        return self._collections[name]

    def _snapshot(self, collection, filt, projection):
        rows = self._exec(
            f"SELECT body FROM docs WHERE collection = ? ORDER BY {self._id_col}", (collection,)
        ).fetchall()
        out = []
        for (body,) in rows:
            doc = json.loads(body)
            if _matches(doc, filt):
                out.append(_project(doc, projection))
        return out

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


class _PgDB(_LocalDB):
    """Postgres-backed docs store (psycopg 3). Same table design as SQLite,
    plus a BIGSERIAL sequence standing in for SQLite's rowid."""

    _pg = True

    def __init__(self, url: str):
        import psycopg

        self._path = url
        self._conn = psycopg.connect(url, autocommit=True)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS docs ("
            "seq BIGSERIAL PRIMARY KEY, collection TEXT, pk TEXT, body TEXT)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_docs_collection ON docs (collection)"
        )
        self._lock = asyncio.Lock()
        self._collections: dict[str, _Collection] = {}
