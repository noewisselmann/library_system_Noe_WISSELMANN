from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from typing import List, Dict, Any

from cassandra.query import PreparedStatement
from loguru import logger


@dataclass
class BorrowResult:
    ok: bool
    message: str


class BorrowRepository:
    """
    Emprunt / Retour.
    Hypothèse: books_by_id contient available_copies + title + author + category.
    """

    def __init__(self, session):
        self.session = session

        # ====== Books ======
        self._sel_book: PreparedStatement = session.prepare(
            "SELECT isbn, title, author, category, available_copies, total_copies "
            "FROM books_by_id WHERE isbn = ?"
        )

        self._upd_book_copies: PreparedStatement = session.prepare(
            "UPDATE books_by_id SET available_copies = ? WHERE isbn = ?"
        )

        self._upd_book_cat_copies: PreparedStatement = session.prepare(
            "UPDATE books_by_category SET available_copies = ? "
            "WHERE category = ? AND title = ? AND isbn = ?"
        )

        self._upd_book_author_copies: PreparedStatement = session.prepare(
            "UPDATE books_by_author SET available_copies = ? "
            "WHERE author = ? AND title = ? AND isbn = ?"
        )

        # ====== Users ======
        self._sel_user: PreparedStatement = session.prepare(
            "SELECT user_id, first_name, last_name, total_borrows, active_borrows "
            "FROM users_by_id WHERE user_id = ?"
        )

        self._upd_user_counts: PreparedStatement = session.prepare(
            "UPDATE users_by_id SET total_borrows = ?, active_borrows = ? WHERE user_id = ?"
        )

        # ====== Borrows tables ======
        self._ins_borrow_user: PreparedStatement = session.prepare(
            "INSERT INTO borrows_by_user "
            "(user_id, borrow_date, isbn, book_title, status, due_date, return_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )

        self._ins_borrow_book: PreparedStatement = session.prepare(
            "INSERT INTO borrows_by_book "
            "(isbn, borrow_date, user_id, user_name, status, due_date, return_date, book_title) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )

        self._ins_active: PreparedStatement = session.prepare(
            "INSERT INTO active_borrows_by_user "
            "(user_id, borrow_date, isbn, book_title, due_date) "
            "VALUES (?, ?, ?, ?, ?)"
        )

        self._del_active: PreparedStatement = session.prepare(
            "DELETE FROM active_borrows_by_user WHERE user_id = ? AND borrow_date = ? AND isbn = ?"
        )

        self._upd_borrow_user_return: PreparedStatement = session.prepare(
            "UPDATE borrows_by_user SET status = ?, return_date = ? "
            "WHERE user_id = ? AND borrow_date = ? AND isbn = ?"
        )

        self._upd_borrow_book_return: PreparedStatement = session.prepare(
            "UPDATE borrows_by_book SET status = ?, return_date = ? "
            "WHERE isbn = ? AND borrow_date = ? AND user_id = ?"
        )

        # Pour retrouver l'emprunt actif du user sur un isbn (sans scan)
        self._sel_active_by_user: PreparedStatement = session.prepare(
            "SELECT borrow_date, isbn, book_title, due_date "
            "FROM active_borrows_by_user WHERE user_id = ?"
        )

    def borrow_book(self, user_id: UUID, isbn: str, loan_days: int = 14) -> BorrowResult:
        # 1) Lire book
        book = self.session.execute(self._sel_book, (isbn,)).one()
        if not book:
            return BorrowResult(False, "Livre introuvable")

        if book.available_copies is None or book.available_copies <= 0:
            return BorrowResult(False, "Aucune copie disponible")

        # 2) Lire user
        user = self.session.execute(self._sel_user, (user_id,)).one()
        if not user:
            return BorrowResult(False, "Utilisateur introuvable")

        user_name = f"{user.first_name} {user.last_name}".strip()

        now = datetime.now(timezone.utc)
        due = now + timedelta(days=loan_days)

        # 3) Ecritures (best effort, pas transaction)
        try:
            new_avail = int(book.available_copies) - 1

            # Update copies in 3 tables
            self.session.execute(self._upd_book_copies, (new_avail, isbn))
            self.session.execute(self._upd_book_cat_copies, (new_avail, book.category, book.title, isbn))
            self.session.execute(self._upd_book_author_copies, (new_avail, book.author, book.title, isbn))

            # Insert borrow history
            self.session.execute(self._ins_borrow_user, (user_id, now, isbn, book.title, "BORROWED", due, None))
            self.session.execute(self._ins_borrow_book, (isbn, now, user_id, user_name, "BORROWED", due, None, book.title))

            # Insert active borrow
            self.session.execute(self._ins_active, (user_id, now, isbn, book.title, due))

            # Update user counters
            total_b = int(user.total_borrows or 0) + 1
            active_b = int(user.active_borrows or 0) + 1
            self.session.execute(self._upd_user_counts, (total_b, active_b, user_id))

            logger.success(f"✅ Emprunt OK: {user_id} -> {isbn}")
            return BorrowResult(True, "Emprunt effectué")
        except Exception as e:
            logger.error(f"❌ borrow_book failed: {e}")
            return BorrowResult(False, f"Erreur emprunt: {e}")

    def return_book(self, user_id: UUID, isbn: str) -> BorrowResult:
        # 1) Trouver l'emprunt actif correspondant (on lit la partition user_id)
        active_rows = list(self.session.execute(self._sel_active_by_user, (user_id,)))
        match = None
        for r in active_rows:
            if r.isbn == isbn:
                match = r
                break

        if not match:
            return BorrowResult(False, "Aucun emprunt actif trouvé pour ce livre")

        borrow_date = match.borrow_date

        # 2) Lire book (pour remettre copies)
        book = self.session.execute(self._sel_book, (isbn,)).one()
        if not book:
            return BorrowResult(False, "Livre introuvable (books_by_id)")

        # 3) Lire user
        user = self.session.execute(self._sel_user, (user_id,)).one()
        if not user:
            return BorrowResult(False, "Utilisateur introuvable")

        now = datetime.now(timezone.utc)

        try:
            new_avail = int(book.available_copies or 0) + 1
            # Clamp: ne pas dépasser total_copies si présent
            if book.total_copies is not None:
                new_avail = min(new_avail, int(book.total_copies))

            # Update copies in 3 tables
            self.session.execute(self._upd_book_copies, (new_avail, isbn))
            self.session.execute(self._upd_book_cat_copies, (new_avail, book.category, book.title, isbn))
            self.session.execute(self._upd_book_author_copies, (new_avail, book.author, book.title, isbn))

            # Update statuses
            self.session.execute(self._upd_borrow_user_return, ("RETURNED", now, user_id, borrow_date, isbn))
            self.session.execute(self._upd_borrow_book_return, ("RETURNED", now, isbn, borrow_date, user_id))

            # Remove active borrow
            self.session.execute(self._del_active, (user_id, borrow_date, isbn))

            # Update user counters
            total_b = int(user.total_borrows or 0)
            active_b = max(0, int(user.active_borrows or 0) - 1)
            self.session.execute(self._upd_user_counts, (total_b, active_b, user_id))

            logger.success(f"✅ Retour OK: {user_id} -> {isbn}")
            return BorrowResult(True, "Livre retourné")
        except Exception as e:
            logger.error(f"❌ return_book failed: {e}")
            return BorrowResult(False, f"Erreur retour: {e}")

    def get_active_borrows_by_user(self, user_id: UUID) -> List[Dict[str, Any]]:
        rows = self.session.execute(
            "SELECT user_id, borrow_date, isbn, book_title, due_date "
            "FROM active_borrows_by_user WHERE user_id = %s",
            (user_id,)
        )
        return [dict(r._asdict()) for r in rows]