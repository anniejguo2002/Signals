import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, body TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path)

    def save(self, report):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO reports VALUES (?, ?)', (report['id'], json.dumps(report)))

    def get(self, report_id):
        with self.connect() as db:
            row = db.execute('SELECT body FROM reports WHERE id = ?', (report_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self):
        with self.connect() as db:
            rows = db.execute('SELECT body FROM reports ORDER BY rowid DESC LIMIT 100').fetchall()
        return [json.loads(row[0]) for row in rows]
