from config.database import CassandraConnection
from models.user import UserRepository

if __name__ == "__main__":
    db = CassandraConnection()
    session = db.connect()

    repo = UserRepository(session)
    user_id = repo.create_user("noe@example.com", "Noé", "Wisselmann")

    user = repo.get_user(user_id)
    print(user)

    db.close()
