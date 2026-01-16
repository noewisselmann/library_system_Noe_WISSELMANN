📚 Système de Gestion de Bibliothèque Numérique


🧠 Présentation du projet

Ce projet consiste à concevoir et implémenter un système de gestion de bibliothèque numérique capable de gérer un grand volume de livres, d’utilisateurs et d’emprunts dans un contexte distribué.
L’objectif principal est de mettre en pratique :
la modélisation orientée requêtes avec Apache Cassandra
la gestion de la haute disponibilité et de la scalabilité horizontale
l’intégration de Cassandra avec une application Python structurée
une interface CLI permettant de manipuler le système
Le projet simule le fonctionnement d’une bibliothèque universitaire avec des milliers d’utilisateurs et de livres.


🎯 Objectifs techniques

Concevoir un modèle de données Cassandra optimisé
Éviter les anti-patterns NoSQL (JOIN, scans complets, ALLOW FILTERING)
Implémenter les fonctionnalités métier :
gestion des livres
gestion des utilisateurs
emprunts et retours
Déployer un cluster Cassandra à 3 nœuds
Fournir une interface CLI fonctionnelle


🗄️ Modélisation Cassandra

Le modèle suit le principe fondamental de Cassandra :
1 query pattern = 1 table
Tables principales
Table	Usage
books_by_id	Recherche par ISBN
books_by_category	Navigation par catégorie
books_by_author	Recherche par auteur
users_by_id	Profil utilisateur
users_by_email	Accès utilisateur par email
borrows_by_user	Historique des emprunts
borrows_by_book	Qui a emprunté un livre
active_borrows_by_user	Emprunts en cours

Bonnes pratiques appliquées
Partition keys explicites
Clustering keys pour l’ordonnancement
Dénormalisation assumée
Aucun ALLOW FILTERING
Aucun JOIN ou sous-requête


🐳 Déploiement Cassandra avec Docker

Prérequis
Docker
Docker Compose
Python 3.11

Lancer le cluster Cassandra
    docker compose up -d

Vérifier l’état du cluster
    docker exec -it cassandra1 nodetool status

Résultat attendu :
    UN cassandra1
    UN cassandra2
    UN cassandra3


🧩 Installation Python

Créer un environnement virtuel
    python -m venv .venv
    source .venv/bin/activate   # Linux / Mac
    .venv\Scripts\activate      # Windows

Installer les dépendances
    pip install -r requirements.txt


🗃️ Initialisation du schéma Cassandra
    python -m scripts.init_schema


Cette commande :
crée le keyspace library_system
initialise toutes les tables Cassandra


💻 Interface CLI
Lancer le CLI
    python -m cli.main

📘 Gestion des livres
Ajouter un livre
    python -m cli.main books add

Rechercher un livre par ISBN
    python -m cli.main books search

Lister les livres par catégorie
    python -m cli.main books list-by-category


👤 Gestion des utilisateurs
Inscrire un utilisateur
    python -m cli.main users register

Afficher un profil utilisateur
    python -m cli.main users profile


🔄 Gestion des emprunts
Emprunter un livre
    python -m cli.main borrows borrow

Retourner un livre
    python -m cli.main borrows return


Les règles métier sont respectées :
vérification des copies disponibles
mise à jour cohérente dans toutes les tables
suivi des emprunts actifs
mise à jour des compteurs utilisateur


🧪 Génération de données de test
    python -m scripts.generate_data


Ce script génère :
des livres réalistes (Faker)
des utilisateurs aléatoires


⚠️ Limites connues

Les écritures ne sont pas transactionnelles (propre à Cassandra)
Pas d’interface graphique (CLI uniquement)
Pas de système de réservation avancé (optionnel)


🚀 Améliorations possibles (bonus)

API REST (Flask / FastAPI)
Interface web
Réservations avec file d’attente
Statistiques temps réel


📚 Technologies utilisées

Python
Apache Cassandra 4.1
Docker / Docker Compose
cassandra-driver
Click (CLI)
Loguru
Faker


🏁 Conclusion

Ce projet démontre une utilisation correcte et raisonnée d’Apache Cassandra dans un contexte distribué, avec une modélisation adaptée aux contraintes NoSQL et une implémentation Python propre et modulaire.
Le système est fonctionnel, scalable et cohérent, répondant aux exigences du sujet.