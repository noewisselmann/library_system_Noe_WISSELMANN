from config.database import CassandraConnection
from models.book import BookRepository, Book

if __name__ == "__main__":
    db = CassandraConnection()
    session = db.connect()

    repo = BookRepository(session)

    dune = Book(
        isbn="978-0-123456-78-9",
        title="Dune",
        author="Frank Herbert",
        category="Science Fiction",
        publisher="Ace",
        publication_year=1965,
        total_copies=3,
        available_copies=3,
        description="Roman SF classique"
    )

    repo.add_book(dune)

    print(repo.get_book_by_isbn(dune.isbn))
    print(repo.get_books_by_category("Science Fiction"))
    print(repo.get_books_by_author("Frank Herbert"))

    db.close()
