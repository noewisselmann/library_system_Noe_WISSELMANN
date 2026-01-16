# scripts/generate_data.py
from __future__ import annotations

from random import choice, randint, sample
from uuid import UUID
from faker import Faker
from loguru import logger

from config.database import CassandraConnection
from models.book import BookRepository, Book
from models.user import UserRepository
from models.borrow import BorrowRepository


fake = Faker("fr_FR")


def generate_books(book_repo: BookRepository, n: int = 100) -> list[str]:
    categories = [
        "Science Fiction", "Fantasy", "Thriller", "Romance",
        "Histoire", "Science", "Biographie", "Philosophie", "Horreur"
    ]
    publishers = ["Gallimard", "Flammarion", "Hachette", "Albin Michel", "Seuil", "Actes Sud"]

    isbns: list[str] = []

    logger.info(f"📚 Génération de {n} livres...")
    for i in range(n):
        isbn = f"978-{randint(0,9)}-{randint(100000,999999)}-{randint(10,99)}-{randint(0,9)}"
        title = fake.sentence(nb_words=4).rstrip(".")
        author = fake.name()
        category = choice(categories)
        publisher = choice(publishers)
        year = randint(1950, 2025)
        total = randint(1, 5)
        desc = fake.text(max_nb_chars=180)

        book = Book(
            isbn=isbn,
            title=title,
            author=author,
            category=category,
            publisher=publisher,
            publication_year=year,
            total_copies=total,
            available_copies=total,   # on démarre avec toutes les copies dispo
            description=desc
        )

        ok = book_repo.add_book(book)
        if ok:
            isbns.append(isbn)

        if (i + 1) % 20 == 0:
            logger.info(f"  ✅ {i+1}/{n} livres générés")

    logger.success(f"✅ Livres générés: {len(isbns)}")
    return isbns


def generate_users(user_repo: UserRepository, n: int = 50) -> list[UUID]:
    logger.info(f"👤 Génération de {n} utilisateurs...")
    user_ids: list[UUID] = []

    for i in range(n):
        email = fake.unique.email()
        first = fake.first_name()
        last = fake.last_name().upper()
        phone = fake.phone_number()
        address = fake.address().replace("\n", ", ")

        user_id = user_repo.create_user(
            email=email,
            first_name=first,
            last_name=last,
            phone=phone,
            address=address
        )
        user_ids.append(user_id)

        if (i + 1) % 10 == 0:
            logger.info(f"  ✅ {i+1}/{n} utilisateurs générés")

    logger.success(f"✅ Utilisateurs générés: {len(user_ids)}")
    return user_ids


def generate_borrows(
    borrow_repo: BorrowRepository,
    user_ids: list[UUID],
    isbns: list[str],
    n: int = 30,
    loan_days: int = 14
) -> None:
    """
    Génère des emprunts en appelant BorrowRepository.borrow_book()
    => cohérent avec ta logique (copies + tables borrows + active_borrows + compteurs users).
    """
    if not user_ids or not isbns:
        logger.warning("⚠️ Impossible de générer des emprunts: pas de users ou pas de livres.")
        return

    logger.info(f"📦 Génération de {n} emprunts...")

    for i in range(n):
        user_id = choice(user_ids)
        isbn = choice(isbns)

        res = borrow_repo.borrow_book(user_id, isbn, loan_days=loan_days)
        if (i + 1) % 10 == 0:
            logger.info(f"  ▶ {i+1}/{n} emprunts tentés (dernier: {res.ok} - {res.message})")

    logger.success("✅ Emprunts générés (best effort).")


def main():
    db = CassandraConnection()  # keyspace=library_system par défaut chez toi
    session = db.connect()

    book_repo = BookRepository(session)
    user_repo = UserRepository(session)
    borrow_repo = BorrowRepository(session)

    # Ajuste les volumes si tu veux
    isbns = generate_books(book_repo, n=100)
    user_ids = generate_users(user_repo, n=50)
    generate_borrows(borrow_repo, user_ids, isbns, n=30)

    db.close()


if __name__ == "__main__":
    main()
