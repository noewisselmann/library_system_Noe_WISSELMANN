from pathlib import Path
from loguru import logger
from config.database import CassandraConnection

def run_cql_file(session, path: str):
    cql = Path(path).read_text(encoding="utf-8")
    for stmt in cql.split(";"):
        stmt = stmt.strip()
        if stmt:
            session.execute(stmt)

if __name__ == "__main__":
    db = CassandraConnection(keyspace="system")
    session = db.connect(set_keyspace=False)
    run_cql_file(session, "schema/schema.cql")
    logger.success("Schéma initialisé")
    db.close()
