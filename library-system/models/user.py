from dataclasses import dataclass
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from cassandra.query import PreparedStatement
from loguru import logger


@dataclass
class User:
    user_id: UUID
    email: str
    first_name: str
    last_name: str
    phone: str = ""
    address: str = ""
    registration_date: datetime = None
    total_borrows: int = 0
    active_borrows: int = 0


class UserRepository:
    def __init__(self, session):
        self.session = session

        self._ins: PreparedStatement = session.prepare("""
            INSERT INTO users_by_id (
              user_id, email, first_name, last_name, phone, address,
              registration_date, total_borrows, active_borrows
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """)

        self._sel: PreparedStatement = session.prepare("""
            SELECT * FROM users_by_id WHERE user_id = ?
        """)

        self._upd_counts: PreparedStatement = session.prepare("""
            UPDATE users_by_id
            SET total_borrows = ?, active_borrows = ?
            WHERE user_id = ?
        """)

        self._insert_user_by_email = session.prepare("""
            INSERT INTO users_by_email (email, user_id, first_name, last_name, registration_date)
            VALUES (?, ?, ?, ?, ?)
        """)


    def create_user(self, email: str, first_name: str, last_name: str,
                    phone: str = "", address: str = ""):
        user_id = uuid4()
        registration_date = datetime.now(timezone.utc)

        try:
            self.session.execute(self._ins, (
                user_id, email, first_name, last_name, phone, address,
                registration_date, 0, 0
            ))
            self.session.execute(self._insert_user_by_email, (
                email, user_id, first_name, last_name, registration_date
            ))

            logger.success(f"✅ Utilisateur créé: {user_id}")
            return user_id
        except Exception as e:
            logger.error(f"❌ create_user failed: {e}")
            raise

    def get_user(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        row = self.session.execute(self._sel, (user_id,)).one()
        return dict(row._asdict()) if row else None

    def set_counts(self, user_id: UUID, total_borrows: int, active_borrows: int) -> None:
        self.session.execute(self._upd_counts, (total_borrows, active_borrows, user_id))

    def get_user_id_by_email(self, email: str):
        row = self.session.execute(
            "SELECT user_id FROM users_by_email WHERE email=%s",
            (email,)
        ).one()
        return row.user_id if row else None

