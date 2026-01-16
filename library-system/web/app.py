from flask import Flask, render_template, request, redirect, url_for, flash, Response
from uuid import UUID
from datetime import datetime, timezone

from config.database import CassandraConnection
from models.book import BookRepository
from models.user import UserRepository
from models.borrow import BorrowRepository

app = Flask(__name__)
app.secret_key = "dev-secret-key"  # ok pour une démo

# Connexion Cassandra (une session partagée suffit pour une démo)
db = CassandraConnection()
session = db.connect()

book_repo = BookRepository(session)
user_repo = UserRepository(session)
borrow_repo = BorrowRepository(session)


@app.route("/")
def index():
    return render_template("index.html")




# ---------- USERS ----------
@app.route("/users/register", methods=["GET", "POST"])
def users_register():
    if request.method == "POST":
        email = request.form["email"].strip()
        first_name = request.form["first_name"].strip()
        last_name = request.form["last_name"].strip()


        user_id = user_repo.create_user(email, first_name, last_name)
        flash(f"Utilisateur créé: {user_id}", "success")
        return redirect(url_for("users_register"))


    return render_template("users_register.html")


# ---------- BOOKS ----------
@app.route("/books/search", methods=["GET", "POST"])
def books_search():
    book = None
    books = None
    limit = 100

    if request.method == "POST":
        action = request.form.get("action")

        if action == "search":
            isbn = request.form.get("isbn", "").strip()
            if isbn:
                book = book_repo.get_book_by_isbn(isbn)

        elif action == "list":
            limit = int(request.form.get("limit", 100))
            books = book_repo.list_books(limit=limit)

    return render_template(
        "books_search.html",
        book=book,
        books=books,
        limit=limit
    )



# @app.route("/books/search", methods=["GET", "POST"])
# def books_search():
    # book = None
    # if request.method == "POST":
        # isbn = request.form["isbn"].strip()
        # book_dict = book_repo.get_book_by_isbn(isbn)
        # book = book_dict  # dict
        # if not book:
            # flash("Livre introuvable", "error")
# 
    # return render_template("books_search.html", book=book)


# ---------- BORROW / RETURN ----------
@app.route("/borrows", methods=["GET", "POST"])
def borrows():
    """
    Form unique:
    - emprunter via email + isbn
    - retourner via email + isbn
    """
    if request.method == "POST":
        action = request.form["action"]
        email = request.form["email"].strip()
        isbn = request.form["isbn"].strip()

        user_id = user_repo.get_user_id_by_email(email)
        if not user_id:
            flash("Utilisateur introuvable (email)", "error")
            return redirect(url_for("borrows"))

        if action == "borrow":
            res = borrow_repo.borrow_book(UUID(str(user_id)), isbn, loan_days=14)
            flash(res.message, "success" if res.ok else "error")
        elif action == "return":
            res = borrow_repo.return_book(UUID(str(user_id)), isbn)
            flash(res.message, "success" if res.ok else "error")

        return redirect(url_for("borrows"))

    return render_template("borrow.html")

@app.route("/borrows/active", methods=["GET", "POST"])
def borrows_active():
    borrows = None
    user_id_str = ""

    if request.method == "POST":
        user_id_str = request.form.get("user_id", "").strip()

        try:
            user_id = UUID(user_id_str)
        except Exception:
            flash("User ID invalide (UUID attendu)", "error")
            return render_template(
                "borrows_active.html",
                borrows=None,
                user_id=user_id_str,
                now=datetime.utcnow(),
            )

        borrows = borrow_repo.get_active_borrows_by_user(user_id)

        if not borrows:
            flash("Aucun emprunt actif pour cet utilisateur.", "info")

    return render_template(
        "borrows_active.html",
        borrows=borrows,
        user_id=user_id_str,
        now=datetime.utcnow(),
    )



@app.teardown_appcontext
def shutdown_session(exception=None):
    # Pour une démo, on garde la connexion ouverte.
    # Si tu préfères fermer proprement à l’arrêt du process, laisse comme ça.
    pass

@app.route("/favicon.ico")
def favicon():
    return Response(status=204)

if __name__ == "__main__":
    # http://127.0.0.1:5000
    app.run(debug=False)
