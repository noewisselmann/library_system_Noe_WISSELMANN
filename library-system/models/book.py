from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from cassandra.query import PreparedStatement
from loguru import logger

@dataclass
class Book:
    isbn: str
    title: str
    author: str
    category: str
    publisher: str
    publication_year: int
    total_copies: int
    available_copies: int
    description: str = ""

class BookRepository:
    def __init__(self, session):
        self.session = session

        self._ins_by_id: PreparedStatement = session.prepare("""
            INSERT INTO books_by_id (
              isbn, title, author, category, publisher, publication_year,
              total_copies, available_copies, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """)

        self._ins_by_category: PreparedStatement = session.prepare("""
            INSERT INTO books_by_category (
              category, title, isbn, author, publication_year,
              available_copies, total_copies
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """)

        self._ins_by_author: PreparedStatement = session.prepare("""
            INSERT INTO books_by_author (
              author, title, isbn, category, publication_year,
              available_copies, total_copies
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """)

        self._sel_by_isbn: PreparedStatement = session.prepare("""
            SELECT * FROM books_by_id WHERE isbn = ?
        """)

        self._sel_by_category: PreparedStatement = session.prepare("""
            SELECT * FROM books_by_category WHERE category = ?
        """)

        self._sel_by_author: PreparedStatement = session.prepare("""
            SELECT * FROM books_by_author WHERE author = ?
        """)

    def add_book(self, book: Book) -> bool:
        try:
            self.session.execute(self._ins_by_id, (
                book.isbn, book.title, book.author, book.category,
                book.publisher, book.publication_year,
                book.total_copies, book.available_copies, book.description
            ))

            self.session.execute(self._ins_by_category, (
                book.category, book.title, book.isbn, book.author,
                book.publication_year, book.available_copies, book.total_copies
            ))

            self.session.execute(self._ins_by_author, (
                book.author, book.title, book.isbn, book.category,
                book.publication_year, book.available_copies, book.total_copies
            ))

            logger.success(f"✅ Livre ajouté: {book.title} ({book.isbn})")
            return True
        except Exception as e:
            logger.error(f"❌ add_book failed: {e}")
            return False

    def get_book_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        row = self.session.execute(self._sel_by_isbn, (isbn,)).one()
        return dict(row._asdict()) if row else None

    def get_books_by_category(self, category: str) -> List[Dict[str, Any]]:
        rows = self.session.execute(self._sel_by_category, (category,))
        return [dict(r._asdict()) for r in rows]

    def get_books_by_author(self, author: str) -> List[Dict[str, Any]]:
        rows = self.session.execute(self._sel_by_author, (author,))
        return [dict(r._asdict()) for r in rows]
    
    # def list_books(self, limit: int = 100) -> List[Dict[str, Any]]:
        # rows = self.session.execute(
            # f"SELECT isbn, title, author, category, available_copies, total_copies "
            # f"FROM books_by_id LIMIT {int(limit)}"
        # )
        # return [dict(r._asdict()) for r in rows]
    
    def list_books(self, limit: int = 100):
        # ⚠️ Cassandra: LIMIT sans partition key = scan.
        # OK pour une démo / petit dataset, pas pour prod.
        query = "SELECT isbn, title, author, category, available_copies, total_copies FROM books_by_id LIMIT %s"
        rows = self.session.execute(query, (int(limit),))
        return [dict(r._asdict()) for r in rows]
