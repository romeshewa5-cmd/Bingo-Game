import sqlite3
from contextlib import contextmanager

class Database:
    def __init__(self, db_path="bingo.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def conn(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _init_db(self):
        with self.conn() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username    TEXT    DEFAULT '',
                    name        TEXT    DEFAULT '',
                    balance     REAL    DEFAULT 0,
                    registered_at TEXT  DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS deposits (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    amount     REAL    NOT NULL,
                    method     TEXT    NOT NULL,
                    sms_proof  TEXT    DEFAULT '',
                    status     TEXT    DEFAULT 'pending',
                    created_at TEXT    DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    amount     REAL    NOT NULL,
                    phone      TEXT    NOT NULL,
                    status     TEXT    DEFAULT 'pending',
                    created_at TEXT    DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    type        TEXT    NOT NULL,
                    amount      REAL    NOT NULL,
                    description TEXT    DEFAULT '',
                    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS game_entries (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    bet_amount  REAL    NOT NULL,
                    card_number INTEGER NOT NULL,
                    status      TEXT    DEFAULT 'active',
                    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def register_user(self, tid, username, name):
        with self.conn() as con:
            con.execute("INSERT OR IGNORE INTO users (telegram_id,username,name) VALUES (?,?,?)", (tid,username,name))
            con.execute("UPDATE users SET username=?,name=? WHERE telegram_id=?", (username,name,tid))

    def get_balance(self, tid):
        with self.conn() as con:
            r = con.execute("SELECT balance FROM users WHERE telegram_id=?", (tid,)).fetchone()
            return float(r["balance"]) if r else 0.0

    def credit_balance(self, tid, amount, description="Credit"):
        with self.conn() as con:
            con.execute("UPDATE users SET balance=balance+? WHERE telegram_id=?", (amount,tid))
            con.execute("INSERT INTO transactions(user_id,type,amount,description) VALUES(?,?,?,?)", (tid,"credit",amount,description))

    def debit_balance(self, tid, amount, description="Debit"):
        with self.conn() as con:
            con.execute("UPDATE users SET balance=balance-? WHERE telegram_id=?", (amount,tid))
            con.execute("INSERT INTO transactions(user_id,type,amount,description) VALUES(?,?,?,?)", (tid,"debit",amount,description))

    def find_user(self, identifier):
        with self.conn() as con:
            r = con.execute("SELECT * FROM users WHERE username=? OR telegram_id=?", (identifier,identifier)).fetchone()
            return dict(r) if r else None

    def create_pending_deposit(self, user_id, amount, method, sms):
        with self.conn() as con:
            cur = con.execute("INSERT INTO deposits(user_id,amount,method,sms_proof) VALUES(?,?,?,?)", (user_id,amount,method,sms))
            return cur.lastrowid

    def get_deposit(self, dep_id):
        with self.conn() as con:
            r = con.execute("SELECT * FROM deposits WHERE id=?", (dep_id,)).fetchone()
            return dict(r) if r else None

    def approve_deposit(self, dep_id):
        with self.conn() as con:
            con.execute("UPDATE deposits SET status='approved' WHERE id=?", (dep_id,))

    def reject_deposit(self, dep_id):
        with self.conn() as con:
            con.execute("UPDATE deposits SET status='rejected' WHERE id=?", (dep_id,))

    def get_pending_deposits(self):
        with self.conn() as con:
            return [dict(r) for r in con.execute("SELECT * FROM deposits WHERE status='pending' ORDER BY created_at DESC").fetchall()]

    def create_pending_withdrawal(self, user_id, amount, phone):
        with self.conn() as con:
            con.execute("INSERT INTO withdrawals(user_id,amount,phone) VALUES(?,?,?)", (user_id,amount,phone))

    def get_transactions(self, user_id, limit=10):
        with self.conn() as con:
            return [dict(r) for r in con.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id,limit)).fetchall()]

    def record_game_entry(self, user_id, bet, card):
        with self.conn() as con:
            con.execute("INSERT INTO game_entries(user_id,bet_amount,card_number) VALUES(?,?,?)", (user_id,bet,card))
