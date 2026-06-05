"""
Baza podataka za BooklyTTS.

ARCH-06: init_db() se poziva samo jednom pri startu aplikacije (iz create_app()),
         ne unutar svake funkcije. Sve javne funkcije pretpostavljaju da je baza
         već inicijalizirana.
"""
import sqlite3

DB_PATH = 'booklytts.db'


def init_db():
    """Kreira tablice ako ne postoje. Poziva se jednom iz create_app()."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                epub_name TEXT,
                voice TEXT,
                chapters_count INTEGER,
                output_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()


def save_conversion(epub_name, voice, chapters_count, output_file):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO conversions (epub_name, voice, chapters_count, '
            'output_file) VALUES (?,?,?,?)',
            (epub_name, voice, chapters_count, output_file)
        )
        conn.commit()


def get_history(limit=20):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            'SELECT epub_name, voice, chapters_count, output_file, '
            'created_at FROM conversions ORDER BY id DESC LIMIT ?',
            (limit,)
        ).fetchall()
    return [
        {'epub': r[0], 'voice': r[1], 'chapters': r[2],
         'file': r[3], 'date': r[4]}
        for r in rows
    ]


def save_setting(key, value):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',
                     (key, value))
        conn.commit()


def get_setting(key, default=None):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            'SELECT value FROM settings WHERE key=?', (key,)
        ).fetchone()
    return row[0] if row else default
