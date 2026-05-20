import sqlite3
import json


class PortfolioDB:
    def __init__(self):
        conn = sqlite3.connect("portfolio.db")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                wallet TEXT,
                score INTEGER,
                risk TEXT,
                assets TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                user_id TEXT PRIMARY KEY,
                threshold INTEGER
            )
        """)

        conn.commit()
        conn.close()

    def save_snapshot(self, user_id, wallet, score, risk, assets):
        conn = sqlite3.connect("portfolio.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO history (user_id, wallet, score, risk, assets)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            wallet,
            score,
            risk,
            json.dumps(assets)
        ))

        conn.commit()
        conn.close()

    def get_history(self, user_id):
        conn = sqlite3.connect("portfolio.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT score, risk, assets, timestamp
            FROM history
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        history = []

        for row in rows:
            score, risk, assets, ts = row

            try:
                assets = json.loads(assets)
            except:
                assets = []

            history.append((score, risk, assets, ts))

        return history

    def save_alert(self, user_id, threshold):
        conn = sqlite3.connect("portfolio.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO alerts (user_id, threshold)
            VALUES (?, ?)
        """, (user_id, threshold))

        conn.commit()
        conn.close()

    def get_alert(self, user_id):
        conn = sqlite3.connect("portfolio.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT threshold FROM alerts WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None