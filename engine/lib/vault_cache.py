"""Search cache: each page's term frequencies, kept in SQLite between runs.

Tokenizing every page is most of what a search costs, and a page's terms only
change when its text does. The cache keys each page by its path and a hash of
its text, so an edited page is recomputed and an unchanged one is not; a
change to the tokenizer or field weights (CACHE_VERSION) starts it over.

    <brain>/.cache/search.sqlite    rebuilt on demand, never committed

The cache is never the source of truth. If it cannot be opened, read or
written (read-only disk, a corrupt file, another process holding a lock),
search computes everything in memory exactly as without it. BRAIN_CACHE=0
turns it off.
"""
import hashlib
import json
import os
import sqlite3

# Raise when tokens(), stem(), STOP_WORDS or FIELD_WEIGHTS change meaning:
# every cached row was computed by the old rules.
CACHE_VERSION = "2"
CACHE_DIR = ".cache"
CACHE_FILE = "search.sqlite"


def cache_path(root):
    return os.path.join(root, CACHE_DIR, CACHE_FILE)


def enabled():
    return os.environ.get("BRAIN_CACHE", "1").strip().lower() not in ("0", "off", "false", "no")


def digest(text):
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


class TermCache:
    """Term frequencies by page; `get_many` is the only call search needs."""

    def __init__(self, root):
        self.root = root
        self.path = cache_path(root)
        self.db = None
        if enabled():
            try:
                self.db = self._open()
            except (sqlite3.Error, OSError):
                self.db = None

    def _open(self, again=True):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        db = sqlite3.connect(self.path, timeout=2)
        try:
            db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS terms (rel TEXT PRIMARY KEY, digest TEXT NOT NULL, tf TEXT NOT NULL)")
            row = db.execute("SELECT value FROM meta WHERE key = 'version'").fetchone()
            if row is None or row[0] != CACHE_VERSION:
                with db:
                    db.execute("DELETE FROM terms")
                    db.execute("INSERT OR REPLACE INTO meta VALUES ('version', ?)", (CACHE_VERSION,))
        except sqlite3.OperationalError:
            # Locked by another process, or read-only: the file may be sound, so it is left
            # alone and this run goes without it.
            db.close()
            raise
        except sqlite3.DatabaseError:
            db.close()
            if not again:
                raise  # the fresh file failed too: go without, rather than start over for ever
            # Not a database, or a damaged one: it is only a cache, start it over, once.
            os.remove(self.path)
            return self._open(again=False)
        return db

    def get_many(self, pages, compute):
        """{page: tf} for every page, from the cache where its text is unchanged, else compute(page)."""
        out, stale = {}, []
        stored = self._rows()
        for p in pages:
            d = digest(p.text)
            hit = stored.get(p.rel)
            if hit and hit[0] == d:
                try:
                    out[p] = json.loads(hit[1])
                    continue
                except ValueError:
                    pass
            out[p] = compute(p)
            stale.append((p.rel, d, json.dumps(out[p], separators=(",", ":"))))
        # Rows for files that are gone (deleted or renamed pages) are dropped as they are seen.
        wanted = {p.rel for p in pages}
        gone = [rel for rel in stored if rel not in wanted and not os.path.exists(os.path.join(self.root, rel))]
        if stale or gone:
            self._write(stale, gone)
        return out

    def _rows(self):
        if self.db is None:
            return {}
        try:
            return {rel: (d, tf) for rel, d, tf in self.db.execute("SELECT rel, digest, tf FROM terms")}
        except sqlite3.Error:
            return {}

    def _write(self, rows, gone=()):
        if self.db is None:
            return
        try:
            with self.db:
                self.db.executemany("INSERT OR REPLACE INTO terms VALUES (?, ?, ?)", rows)
                self.db.executemany("DELETE FROM terms WHERE rel = ?", [(rel,) for rel in gone])
        except sqlite3.Error:
            pass  # read-only or locked: the answer is already computed

    def stats(self):
        rows = 0
        if self.db is not None:
            try:
                rows = self.db.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
            except sqlite3.Error:
                pass
        size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
        return {"path": self.path, "enabled": enabled(), "open": self.db is not None,
                "version": CACHE_VERSION, "pages": rows, "bytes": size}

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None


def clear(root):
    """Delete the cache file; returns True if there was one."""
    path = cache_path(root)
    found = False
    for p in (path, path + "-journal", path + "-wal", path + "-shm"):
        if os.path.exists(p):
            os.remove(p)
            found = True
    return found
