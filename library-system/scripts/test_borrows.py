from config.database import CassandraConnection
from models.book import BookRepository, Book
from models.user import UserRepository
from models.borrow import BorrowRepository

if __name__ == "__main__":
    print("🔌 Connexion Cassandra...")
    db = CassandraConnection()
    session = db.connect()

    book_repo = BookRepository(session)
    user_repo = UserRepository(session)
    borrow_repo = BorrowRepository(session)

    # 1) Créer un user (ne dépend d’aucun user existant)
    print("👤 Création utilisateur...")
    user_id = user_repo.create_user(
        email="noe.test.borrow@example.com",
        first_name="Noé",
        last_name="BorrowTest",
        phone="",
        address=""
    )
    print("✅ user_id =", user_id)

    # 2) S'assurer qu'un livre existe (sinon on le crée)
    print("📘 Vérification / création livre...")
    isbn = "978-0-123456-78-9"

    book = book_repo.get_book_by_isbn(isbn)
    if not book:
        dune = Book(
            isbn=isbn,
            title="Dune",
            author="Frank Herbert",
            category="Science Fiction",
            publisher="Ace",
            publication_year=1965,
            total_copies=3,
            available_copies=3,
            description="Roman SF classique"
        )
        book_repo.add_book(dune)
        book = book_repo.get_book_by_isbn(isbn)

    print("✅ Livre:", book)

    # 3) Emprunter
    print("📕 Emprunt...")
    res = borrow_repo.borrow_book(user_id, isbn, loan_days=14)
    print("➡️", res)

    # 4) Vérifier le livre après emprunt
    book_after = book_repo.get_book_by_isbn(isbn)
    print("📉 Après emprunt:", book_after)

    # 5) Retourner
    print("📗 Retour...")
    res2 = borrow_repo.return_book(user_id, isbn)
    print("➡️", res2)

    # 6) Vérifier le livre après retour
    book_after2 = book_repo.get_book_by_isbn(isbn)
    print("📈 Après retour:", book_after2)

    db.close()
