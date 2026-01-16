CREATE KEYSPACE IF NOT EXISTS library_system
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 3};

USE library_system;

CREATE TABLE IF NOT EXISTS books_by_id (
  isbn text PRIMARY KEY,
  title text,
  author text,
  category text,
  publisher text,
  publication_year int,
  total_copies int,
  available_copies int,
  description text
);

CREATE TABLE IF NOT EXISTS users_by_id (
  user_id uuid PRIMARY KEY,
  email text,
  first_name text,
  last_name text,
  phone text,
  address text,
  registration_date timestamp,
  total_borrows int,
  active_borrows int
);

CREATE TABLE IF NOT EXISTS borrows_by_user (
  user_id uuid,
  borrow_date timestamp,
  isbn text,
  book_title text,
  status text,
  due_date timestamp,
  return_date timestamp,
  PRIMARY KEY ((user_id), borrow_date, isbn)
) WITH CLUSTERING ORDER BY (borrow_date DESC, isbn ASC);
