# 📚 Library Management System

Desktop application for library management built with Python, PostgreSQL, and PyQt6.

## Features

* User authentication and authorization
* Multiple roles:

  * Administrator
  * Librarian
  * Reader
* Book catalog management
* Search books by title, author, ISBN, and publisher
* Add, edit, and delete books
* Book cover support
* Library reports generation
* PostgreSQL database integration

## Tech Stack

* Python
* PostgreSQL
* PyQt6
* psycopg2
* python-dotenv

## Project Structure

```text
.
├── main.py
├── db.py
├── config.py
├── utils.py
├── ui/
│   ├── login_window.py
│   ├── app_window.py
│   ├── catalog_tab.py
│   ├── account_tab.py
│   ├── librarian_tab.py
│   └── admin_tab.py
```

## Installation

Clone the repository:

```bash
git clone https://github.com/tether999/bookstore-python-postgresql.git
cd bookstore-python-postgresql
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=library_project
DB_USER=postgres
DB_PASSWORD=your_password
```

Run the application:

```bash
python main.py
```

## Learning Goals

This project was created to practice:

* Object-Oriented Programming
* Database design
* PostgreSQL integration
* GUI development with PyQt6
* Role-based access control
* CRUD operations
