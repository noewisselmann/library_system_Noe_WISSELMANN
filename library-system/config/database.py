from cassandra.cluster import Cluster
from loguru import logger

class CassandraConnection:
    def __init__(self, hosts=None, port=9042, keyspace="library_system"):
        self.hosts = hosts or ["127.0.0.1"]
        self.port = port
        self.keyspace = keyspace
        self.cluster = None
        self.session = None

    def connect(self, set_keyspace=True):
        self.cluster = Cluster(contact_points=self.hosts, port=self.port)
        self.session = self.cluster.connect()
        logger.success(f"Connecté à Cassandra: {self.hosts}:{self.port}")

        if set_keyspace:
            self.session.set_keyspace(self.keyspace)
            logger.success(f"Keyspace actif: {self.keyspace}")

        return self.session

    def close(self):
        if self.cluster:
            self.cluster.shutdown()
            logger.info("Connexion Cassandra fermée")
