import click
from uuid import UUID

from config.database import CassandraConnection
from models.book import BookRepository, Book
from models.user import UserRepository
from models.borrow import BorrowRepository

from tabulate import tabulate



# ========= Bootstrap Cassandra =========
db = CassandraConnection()
session = db.connect()

book_repo = BookRepository(session)
user_repo = UserRepository(session)
borrow_repo = BorrowRepository(session)


@click.group()
def cli():
    """📚 Library System (Cassandra + Python)"""
    pass


# ================= BOOKS =================
@cli.group()
def books():
    """Gestion des livres"""
    pass


@books.command("add")
@click.option("--isbn", prompt=True)
@click.option("--title", prompt=True)
@click.option("--author", prompt=True)
@click.option("--category", prompt=True)
@click.option("--publisher", prompt=True)
@click.option("--year", prompt="Publication year", type=int)
@click.option("--copies", prompt="Total copies", type=int, default=1)
@click.option("--description", prompt=False, default="")
def books_add(isbn, title, author, category, publisher, year, copies, description):
    book = Book(
        isbn=isbn,
        title=title,
        author=author,
        category=category,
        publisher=publisher,
        publication_year=year,
        total_copies=copies,
        available_copies=copies,
        description=description
    )
    ok = book_repo.add_book(book)
    if ok:
        click.echo(click.style("✅ Livre ajouté", fg="green"))
    else:
        click.echo(click.style("❌ Erreur ajout livre", fg="red"))


@books.command("search")
@click.option("--isbn", prompt=True)
def books_search(isbn):
    book = book_repo.get_book_by_isbn(isbn)
    if not book:
        click.echo(click.style("❌ Livre introuvable", fg="red"))
        return

    data = [
        ["ISBN", book.isbn],
        ["Titre", book.title],
        ["Auteur", book.author],
        ["Catégorie", book.category],
        ["Éditeur", book.publisher],
        ["Année", book.publication_year],
        ["Disponibles", f"{book.available_copies}/{book.total_copies}"],
    ]
    click.echo("\n" + tabulate(data, tablefmt="grid"))


@books.command("list-by-category")
@click.option("--category", prompt=True)
def books_list_by_category(category):
    rows = book_repo.get_books_by_category(category)
    if not rows:
        click.echo(click.style("Aucun livre trouvé", fg="yellow"))
        return

    table = [[r["isbn"], r["title"], r["author"], r["available_copies"]] for r in rows]
    click.echo("\n" + tabulate(table, headers=["ISBN", "Titre", "Auteur", "Dispo"], tablefmt="grid"))


@books.command("list-by-author")
@click.option("--author", prompt=True)
def books_list_by_author(author):
    rows = book_repo.get_books_by_author(author)
    if not rows:
        click.echo(click.style("Aucun livre trouvé", fg="yellow"))
        return

    table = [[r["isbn"], r["title"], r["category"], r["available_copies"]] for r in rows]
    click.echo("\n" + tabulate(table, headers=["ISBN", "Titre", "Catégorie", "Dispo"], tablefmt="grid"))


# ================= USERS =================
@cli.group()
def users():
    """Gestion des utilisateurs"""
    pass


@users.command("register")
@click.option("--email", prompt=True)
@click.option("--first-name", prompt=True)
@click.option("--last-name", prompt=True)
@click.option("--phone", default="")
@click.option("--address", default="")
def users_register(email, first_name, last_name, phone, address):
    user_id = user_repo.create_user(email, first_name, last_name, phone, address)
    click.echo(click.style(f"✅ Utilisateur créé: {user_id}", fg="green"))


@users.command("profile")
@click.option("--user-id", prompt=True)
def users_profile(user_id):
    user = user_repo.get_user(UUID(user_id))
    if not user:
        click.echo(click.style("❌ Utilisateur introuvable", fg="red"))
        return

    data = [
        ["ID", user["user_id"]],
        ["Nom", f'{user["first_name"]} {user["last_name"]}'],
        ["Email", user["email"]],
        ["Inscription", user["registration_date"]],
        ["Emprunts totaux", user["total_borrows"]],
        ["Emprunts actifs", user["active_borrows"]],
    ]
    click.echo("\n" + tabulate(data, tablefmt="grid"))


# ================= BORROWS =================
@cli.group()
def borrows():
    """Gestion des emprunts"""
    pass



@borrows.command("borrow")
@click.option("--user-id", default=None, help="UUID utilisateur")
@click.option("--email", default=None, help="Email utilisateur")
@click.option("--isbn", prompt=True)
@click.option("--days", default=14, show_default=True, type=int)
def borrows_borrow(user_id, email, isbn, days):
    if not user_id and not email:
        raise click.UsageError("Il faut fournir --user-id OU --email")

    if email:
        uid = user_repo.get_user_id_by_email(email)
        if not uid:
            click.echo(click.style("❌ Email introuvable", fg="red"))
            return
    else:
        uid = UUID(user_id)

    res = borrow_repo.borrow_book(uid, isbn, loan_days=days)
    if res.ok:
        click.echo(click.style(f"✅ {res.message}", fg="green"))
    else:
        click.echo(click.style(f"❌ {res.message}", fg="red"))










@borrows.command("return")
@click.option("--user-id", prompt=True)
@click.option("--isbn", prompt=True)
def borrows_return(user_id, isbn):
    res = borrow_repo.return_book(UUID(user_id), isbn)
    if res.ok:
        click.echo(click.style(f"✅ {res.message}", fg="green"))
    else:
        click.echo(click.style(f"❌ {res.message}", fg="red"))


@borrows.command("borrow-email")
def borrows_borrow_email():
    """Emprunter un livre avec l'email utilisateur"""
    user_repo = UserRepository(db.session)
    borrow_repo = BorrowRepository(db.session)

    email = input("Email: ").strip()
    isbn = input("Isbn: ").strip()
    days_str = input("Loan days [14]: ").strip()
    days = int(days_str) if days_str else 14

    user_id = user_repo.get_user_id_by_email(email)
    if not user_id:
        print("❌ Utilisateur introuvable pour cet email")
        return

    res = borrow_repo.borrow_book(UUID(str(user_id)), isbn, loan_days=days)
    print(("✅ " if res.ok else "❌ ") + res.message)

@books.command("list-by-category")
def books_list_by_category():
    """Lister les livres d'une catégorie"""
    repo = BookRepository(db.session)  # adapte si ton objet db s'appelle autrement
    category = input("Category: ").strip()

    rows = repo.get_books_by_category(category)
    if not rows:
        print("Aucun livre trouvé.")
        return

    for b in rows:
        print(f"- {b['title']} | ISBN={b['isbn']} | author={b['author']} | avail={b['available_copies']}/{b['total_copies']}")

@books.command("list-by-author")
def books_list_by_author():
    """Lister les livres d'un auteur"""
    repo = BookRepository(db.session)
    author = input("Author: ").strip()

    rows = repo.get_books_by_author(author)
    if not rows:
        print("Aucun livre trouvé.")
        return

    for b in rows:
        print(f"- {b['title']} | ISBN={b['isbn']} | category={b['category']} | avail={b['available_copies']}/{b['total_copies']}")

@users.command("show")
def users_show():
    """Afficher un utilisateur via email"""
    user_repo = UserRepository(db.session)
    email = input("Email: ").strip()

    user_id = user_repo.get_user_id_by_email(email)
    if not user_id:
        print("Utilisateur introuvable.")
        return

    user = user_repo.get_user(user_id)
    print(user)

@users.command("active-borrows")
def users_active_borrows():
    """Lister les emprunts actifs d'un user via email"""
    user_repo = UserRepository(db.session)
    email = input("Email: ").strip()

    user_id = user_repo.get_user_id_by_email(email)
    if not user_id:
        print("Utilisateur introuvable.")
        return

    rows = db.session.execute(
        "SELECT borrow_date, isbn, book_title, due_date FROM active_borrows_by_user WHERE user_id=%s",
        (user_id,)
    )

    rows = list(rows)
    if not rows:
        print("Aucun emprunt actif.")
        return

    for r in rows:
        print(f"- {r.book_title} | ISBN={r.isbn} | borrow_date={r.borrow_date} | due={r.due_date}")

@users.command("borrows-history")
def users_borrows_history():
    """Historique complet des emprunts d'un user via email"""
    user_repo = UserRepository(db.session)
    email = input("Email: ").strip()

    user_id = user_repo.get_user_id_by_email(email)
    if not user_id:
        print("Utilisateur introuvable.")
        return

    rows = db.session.execute(
        "SELECT borrow_date, isbn, book_title, status, due_date, return_date "
        "FROM borrows_by_user WHERE user_id=%s",
        (user_id,)
    )

    rows = list(rows)
    if not rows:
        print("Aucun historique.")
        return

    for r in rows:
        print(f"- {r.book_title} | ISBN={r.isbn} | {r.status} | borrow={r.borrow_date} | due={r.due_date} | return={r.return_date}")



@cli.command("close")
def close_conn():
    """Fermer la connexion Cassandra (utile si tu lances le CLI en debug)"""
    db.close()
    click.echo("🔌 Connexion fermée")


if __name__ == "__main__":
    try:
        cli()
    finally:
        db.close()
