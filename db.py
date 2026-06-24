import hashlib
import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def hash_password(password: str) -> str:
    return hashlib.sha512(password.encode('utf-8')).hexdigest()


class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'library_project'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            client_encoding='UTF8',
        )
        self.conn.autocommit = False

    @contextmanager
    def cursor(self, dict_rows=False):
        cur = self.conn.cursor(cursor_factory=RealDictCursor if dict_rows else None)
        try:
            yield cur
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def fetch_all(self, sql, params=()):
        with self.cursor(dict_rows=True) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def fetch_one(self, sql, params=()):
        with self.cursor(dict_rows=True) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def execute(self, sql, params=()):
        with self.cursor() as cur:
            cur.execute(sql, params)
            return True

    def normalize_role_name(self, role_name):
        aliases = {
            'client': 'client',
            'reader': 'client',
            'читатель': 'client',
            'librarian': 'librarian',
            'библиотекарь': 'librarian',
            'admin': 'admin',
            'админ': 'admin',
            'administrator': 'admin',
        }
        return aliases.get((role_name or '').strip().lower(), (role_name or '').strip())

    def get_role_id(self, role_name):
        canonical = self.normalize_role_name(role_name)
        aliases = {
            'client': ('client', 'читатель', 'reader'),
            'librarian': ('librarian', 'библиотекарь'),
            'admin': ('admin', 'админ', 'administrator'),
        }.get(canonical, (canonical,))
        row = self.fetch_one(
            'SELECT id FROM roles WHERE name = ANY(%s) ORDER BY CASE name WHEN %s THEN 0 ELSE 1 END, id LIMIT 1',
            (list(aliases), canonical)
        )
        return row['id'] if row else None

    def check_user_exists(self, login):
        return bool(self.fetch_one('SELECT id FROM users WHERE login = %s', (login,)))

    def add_user(self, login, password, email='', role_name='client'):
        login = login.strip()
        email = email.strip()
        if not login or not password or not email:
            return False, 'Для регистрации нужны логин, пароль и почта'
        role_id = self.get_role_id(role_name) or self.get_role_id('client')
        password_hash = password if len(password) == 128 else hash_password(password)
        try:
            with self.cursor() as cur:
                cur.execute("""
                    INSERT INTO users(login, password_hash, role_id, email)
                    VALUES (%s, %s, %s, %s)
                """, (login, password_hash, role_id, email))
            return True, 'Пользователь зарегистрирован'
        except psycopg2.IntegrityError as exc:
            if 'users_email_key' in str(exc):
                return False, 'Такая почта уже используется'
            return False, 'Такой логин уже занят'
        except Exception as exc:
            return False, f'Ошибка регистрации: {exc}'

    def authenticate_user(self, login, password):
        password_hash = password if len(password) == 128 else hash_password(password)
        return self.fetch_one("""
            SELECT u.*,
                   CASE
                       WHEN lower(r.name) IN ('admin', 'админ', 'administrator') THEN 'admin'
                       WHEN lower(r.name) IN ('librarian', 'библиотекарь') THEN 'librarian'
                       WHEN lower(r.name) IN ('client', 'reader', 'читатель') THEN 'client'
                       ELSE r.name
                   END AS role_name,
                   r.name AS source_role_name,
                   u.login AS full_name
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE u.login = %s AND u.password_hash = %s AND u.is_active = true
        """, (login.strip(), password_hash))

    def get_books(self, search_text=''):
        where = ''
        params = []
        if search_text:
            where = "WHERE b.title ILIKE %s OR b.isbn ILIKE %s OR a.name ILIKE %s OR p.name ILIKE %s"
            params = [f'%{search_text}%'] * 4
        return self.fetch_all(f"""
            SELECT b.id, b.title, COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS authors,
                   b.isbn, COALESCE(p.name, '') AS publisher_name, b.publish_year, b.description,
                   b.total_copies, b.available_copies, b.cover_path
            FROM books b
            LEFT JOIN publishers p ON p.id = b.publisher_id
            LEFT JOIN book_authors ba ON ba.book_id = b.id
            LEFT JOIN authors a ON a.id = ba.author_id
            {where}
            GROUP BY b.id, p.name
            ORDER BY b.title
        """, params)

    def get_available_books_for_issue(self, search_text=''):
        where = 'WHERE b.available_copies > 0'
        params = []
        if search_text:
            where += " AND (b.title ILIKE %s OR b.isbn ILIKE %s OR a.name ILIKE %s OR p.name ILIKE %s)"
            params = [f'%{search_text}%'] * 4
        return self.fetch_all(f"""
            SELECT b.id, b.title, COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS authors,
                   b.isbn, COALESCE(p.name, '') AS publisher_name, b.publish_year,
                   b.total_copies, b.available_copies
            FROM books b
            LEFT JOIN publishers p ON p.id = b.publisher_id
            LEFT JOIN book_authors ba ON ba.book_id = b.id
            LEFT JOIN authors a ON a.id = ba.author_id
            {where}
            GROUP BY b.id, p.name
            ORDER BY b.title
            LIMIT 100
        """, params)

    def get_book(self, book_id):
        rows = self.get_books('')
        for row in rows:
            if row['id'] == int(book_id):
                return row
        return None

    def _get_or_create(self, table, name):
        clean = (name or '').strip()
        if not clean:
            return None
        with self.cursor() as cur:
            cur.execute(f'SELECT id FROM {table} WHERE name = %s', (clean,))
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(f'INSERT INTO {table}(name) VALUES (%s) RETURNING id', (clean,))
            return cur.fetchone()[0]

    def add_book(self, title, authors_text='', isbn='', publisher_name='', publish_year=None, description='', total_copies=1, cover_path=None):
        try:
            publisher_id = self._get_or_create('publishers', publisher_name)
            isbn_value = isbn.strip() or None
            year_value = int(publish_year) if str(publish_year or '').strip() else None
            copies = max(1, int(total_copies))
            with self.cursor() as cur:
                cur.execute("""
                    INSERT INTO books(title, isbn, publisher_id, publish_year, description, total_copies, available_copies, cover_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (title.strip(), isbn_value, publisher_id, year_value, description.strip(), copies, copies, cover_path))
                book_id = cur.fetchone()[0]
                for author in [a.strip() for a in authors_text.split(',') if a.strip()]:
                    author_id = self._get_or_create('authors', author)
                    cur.execute('INSERT INTO book_authors(book_id, author_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', (book_id, author_id))
            return True, f'Книга добавлена, ID: {book_id}'
        except Exception as exc:
            return False, f'Ошибка добавления книги: {exc}'

    def delete_book(self, book_id):
        try:
            with self.cursor() as cur:
                cur.execute('DELETE FROM books WHERE id = %s RETURNING id', (int(book_id),))
                deleted = cur.fetchone()
            return (True, 'Книга удалена') if deleted else (False, 'Книга не найдена')
        except psycopg2.IntegrityError:
            return False, 'Нельзя удалить книгу, по которой уже были выдачи'
        except Exception as exc:
            return False, f'Ошибка удаления: {exc}'

    def get_loan_conditions(self):
        return self.fetch_all('SELECT * FROM loan_conditions ORDER BY is_default DESC, id')

    def find_user_by_login(self, login):
        return self.fetch_one("""
            SELECT u.*,
                   CASE
                       WHEN lower(r.name) IN ('admin', 'админ', 'administrator') THEN 'admin'
                       WHEN lower(r.name) IN ('librarian', 'библиотекарь') THEN 'librarian'
                       WHEN lower(r.name) IN ('client', 'reader', 'читатель') THEN 'client'
                       ELSE r.name
                   END AS role_name,
                   r.name AS source_role_name,
                   u.login AS full_name
            FROM users u JOIN roles r ON r.id = u.role_id
            WHERE u.login = %s AND u.is_active = true
        """, (login.strip(),))

    def issue_book(self, user_login, book_id, librarian_id, condition_id=None):
        try:
            with self.cursor() as cur:
                cur.execute('SELECT id FROM users WHERE login = %s AND is_active = true', (user_login.strip(),))
                user = cur.fetchone()
                if not user:
                    return False, 'Пользователь не найден'
                cur.execute('SELECT available_copies, title FROM books WHERE id = %s FOR UPDATE', (int(book_id),))
                book = cur.fetchone()
                if not book:
                    return False, 'Книга не найдена'
                if book[0] <= 0:
                    return False, 'Нет доступных экземпляров'
                if not condition_id:
                    cur.execute('SELECT id FROM loan_conditions WHERE is_default = true ORDER BY id LIMIT 1')
                    condition_id = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO loans(user_id, book_id, issued_by, condition_id)
                    VALUES (%s, %s, %s, %s)
                """, (user[0], int(book_id), int(librarian_id), int(condition_id)))
                cur.execute('UPDATE books SET available_copies = available_copies - 1 WHERE id = %s', (int(book_id),))
                cur.execute("""
                    INSERT INTO notifications(user_id, title, message)
                    VALUES (%s, %s, %s)
                """, (user[0], 'Книга выдана', f'Вам выдали книгу: {book[1]}'))
            return True, 'Выдача оформлена'
        except Exception as exc:
            return False, f'Ошибка выдачи: {exc}'

    def update_overdue_loans_and_fines(self):
        with self.cursor() as cur:
            cur.execute("""
                UPDATE loans l
                SET status = 'просрочена'
                FROM loan_conditions lc
                WHERE lc.id = l.condition_id
                  AND l.status = 'выдана'
                  AND l.returned_at IS NULL
                  AND CURRENT_DATE > (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date
            """)
            cur.execute("""
                INSERT INTO fines(loan_id, user_id, amount, reason)
                SELECT l.id, l.user_id,
                       ((CURRENT_DATE - (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date) * lc.fine_per_day)::numeric(10,2),
                       'Автоштраф за просрочку книги'
                FROM loans l
                JOIN loan_conditions lc ON lc.id = l.condition_id
                WHERE l.status = 'просрочена'
                  AND l.returned_at IS NULL
                  AND CURRENT_DATE > (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date
                  AND NOT EXISTS (
                      SELECT 1 FROM fines f WHERE f.loan_id = l.id AND f.status = 'не_оплачен'
                  )
            """)
        return True

    def get_active_loans(self, user_id):
        self.update_overdue_loans_and_fines()
        return self.fetch_all("""
            SELECT l.id AS loan_id, b.title, COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS authors,
                   l.issue_date::date AS issue_date,
                   (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date AS due_date,
                   l.status AS loan_status,
                   COALESCE(rr.status, '') AS return_status,
                   GREATEST(0, CURRENT_DATE - (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date) AS overdue_days,
                   (GREATEST(0, CURRENT_DATE - (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date) * lc.fine_per_day)::numeric(10,2) AS current_fine
            FROM loans l
            JOIN books b ON b.id = l.book_id
            JOIN loan_conditions lc ON lc.id = l.condition_id
            LEFT JOIN book_authors ba ON ba.book_id = b.id
            LEFT JOIN authors a ON a.id = ba.author_id
            LEFT JOIN return_requests rr ON rr.loan_id = l.id AND rr.status = 'ожидает'
            WHERE l.user_id = %s AND l.returned_at IS NULL AND l.status IN ('выдана', 'просрочена')
            GROUP BY l.id, b.id, lc.id, rr.status
            ORDER BY due_date
        """, (int(user_id),))

    def get_loan_history(self, user_id):
        return self.fetch_all("""
            SELECT b.title, COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS authors,
                   l.issue_date::date AS issue_date, l.returned_at::date AS returned_at, l.status
            FROM loans l
            JOIN books b ON b.id = l.book_id
            LEFT JOIN book_authors ba ON ba.book_id = b.id
            LEFT JOIN authors a ON a.id = ba.author_id
            WHERE l.user_id = %s AND l.returned_at IS NOT NULL
            GROUP BY l.id, b.id
            ORDER BY l.returned_at DESC
        """, (int(user_id),))

    def add_notification(self, user_id, title, message):
        return self.execute('INSERT INTO notifications(user_id, title, message) VALUES (%s, %s, %s)', (int(user_id), title, message))

    def notify_librarians(self, title, message):
        librarians = self.fetch_all("""
            SELECT u.id FROM users u JOIN roles r ON r.id = u.role_id
            WHERE lower(r.name) IN ('librarian', 'библиотекарь') AND u.is_active = true
        """)
        for librarian in librarians:
            self.add_notification(librarian['id'], title, message)

    def get_notifications(self, user_id):
        return self.fetch_all('SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT 30', (int(user_id),))

    def mark_notifications_read(self, user_id):
        return self.execute('UPDATE notifications SET is_read = true WHERE user_id = %s', (int(user_id),))

    def cleanup_processed_return_requests(self):
        """Убирает из очереди возврата старые заявки по уже возвращенным книгам.
        Структуру базы не меняет: только переводит зависшие заявки из 'ожидает' в 'одобрен'.
        """
        return self.execute("""
            UPDATE return_requests rr
            SET status = 'одобрен'
            FROM loans l
            WHERE l.id = rr.loan_id
              AND rr.status = 'ожидает'
              AND l.returned_at IS NOT NULL
        """)

    def remove_return_request_notifications(self, book_title=None):
        """Удаляет служебные уведомления о запросе возврата после обработки заявки.
        Это не трогает уведомление клиента о принятии/отклонении возврата.
        """
        params = []
        title_filter = ''
        if book_title:
            title_filter = ' AND message ILIKE %s'
            params.append(f'%{book_title}%')
        return self.execute(f"""
            DELETE FROM notifications
            WHERE title = 'Запрос возврата'
            {title_filter}
        """, tuple(params))

    def add_return_request(self, loan_id, user_id=None):
        try:
            with self.cursor() as cur:
                if user_id is not None:
                    cur.execute("""
                        SELECT l.id, u.login, b.title
                        FROM loans l
                        JOIN users u ON u.id = l.user_id
                        JOIN books b ON b.id = l.book_id
                        WHERE l.id = %s AND l.user_id = %s AND l.returned_at IS NULL
                    """, (int(loan_id), int(user_id)))
                else:
                    cur.execute("""
                        SELECT l.id, u.login, b.title
                        FROM loans l
                        JOIN users u ON u.id = l.user_id
                        JOIN books b ON b.id = l.book_id
                        WHERE l.id = %s AND l.returned_at IS NULL
                    """, (int(loan_id),))
                row = cur.fetchone()
                if not row:
                    return False, 'Активная выдача не найдена'
                cur.execute("""
                    INSERT INTO return_requests(loan_id) VALUES (%s)
                    ON CONFLICT(loan_id) DO UPDATE SET status = 'ожидает', requested_at = now()
                """, (int(loan_id),))
            self.notify_librarians('Запрос возврата', f'Пользователь {row[1]} просит принять книгу: {row[2]}')
            return True, 'Запрос на возврат отправлен библиотекарю'
        except Exception as exc:
            return False, f'Ошибка запроса возврата: {exc}'

    def get_pending_return_requests(self):
        self.update_overdue_loans_and_fines()
        self.cleanup_processed_return_requests()
        return self.fetch_all("""
            SELECT rr.id AS request_id, rr.requested_at, l.id AS loan_id, u.login,
                   u.login AS reader,
                   b.title, l.issue_date::date AS issue_date,
                   (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date AS due_date,
                   GREATEST(0, CURRENT_DATE - (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date) AS overdue_days,
                   lc.fine_per_day,
                   (GREATEST(0, CURRENT_DATE - (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date) * lc.fine_per_day)::numeric(10,2) AS fine_amount,
                   CASE
                       WHEN CURRENT_DATE > (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date
                       THEN 'Есть штраф: ' || GREATEST(0, CURRENT_DATE - (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date)::text ||
                            ' дн. × ' || lc.fine_per_day::text || ' руб. = ' ||
                            (GREATEST(0, CURRENT_DATE - (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date) * lc.fine_per_day)::numeric(10,2)::text || ' руб.'
                       ELSE 'Штрафа нет'
                   END AS fine_info,
                   l.status AS loan_status
            FROM return_requests rr
            JOIN loans l ON l.id = rr.loan_id
            JOIN users u ON u.id = l.user_id
            JOIN books b ON b.id = l.book_id
            JOIN loan_conditions lc ON lc.id = l.condition_id
            WHERE rr.status = 'ожидает' AND l.returned_at IS NULL
            ORDER BY rr.requested_at
        """)

    def accept_return_request(self, request_id, librarian_id):
        try:
            with self.cursor() as cur:
                cur.execute("""
                    SELECT rr.loan_id, l.book_id, l.user_id, b.title
                    FROM return_requests rr
                    JOIN loans l ON l.id = rr.loan_id
                    JOIN books b ON b.id = l.book_id
                    WHERE rr.id = %s AND rr.status = 'ожидает' AND l.returned_at IS NULL
                    FOR UPDATE
                """, (int(request_id),))
                row = cur.fetchone()
                if not row:
                    return False, 'Запрос не найден'
                loan_id, book_id, user_id, title = row
                cur.execute("""
                    UPDATE loans SET status = 'возвращена', returned_at = now(), accepted_by = %s
                    WHERE id = %s
                """, (int(librarian_id), loan_id))
                cur.execute("UPDATE return_requests SET status = 'одобрен' WHERE loan_id = %s AND status = 'ожидает'", (loan_id,))
                cur.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id = %s", (book_id,))
                cur.execute("INSERT INTO notifications(user_id, title, message) VALUES (%s, %s, %s)", (user_id, 'Возврат принят', f'Библиотекарь принял книгу: {title}'))
                cur.execute("DELETE FROM notifications WHERE title = 'Запрос возврата' AND message ILIKE %s", (f'%{title}%',))
            return True, 'Возврат принят'
        except Exception as exc:
            return False, f'Ошибка приемки: {exc}'

    def reject_return_request(self, request_id, librarian_id, reason='Возврат отклонен библиотекарем'):
        try:
            with self.cursor() as cur:
                cur.execute("""
                    SELECT rr.loan_id, l.user_id, b.title FROM return_requests rr
                    JOIN loans l ON l.id = rr.loan_id
                    JOIN books b ON b.id = l.book_id
                    WHERE rr.id = %s AND rr.status = 'ожидает' AND l.returned_at IS NULL
                """, (int(request_id),))
                row = cur.fetchone()
                if not row:
                    return False, 'Запрос не найден'
                loan_id, user_id, title = row
                cur.execute("UPDATE return_requests SET status = 'отклонен' WHERE loan_id = %s AND status = 'ожидает'", (loan_id,))
                cur.execute("INSERT INTO notifications(user_id, title, message) VALUES (%s, %s, %s)", (user_id, 'Возврат отклонен', f'{title}: {reason}'))
                cur.execute("DELETE FROM notifications WHERE title = 'Запрос возврата' AND message ILIKE %s", (f'%{title}%',))
            return True, 'Возврат отклонен'
        except Exception as exc:
            return False, f'Ошибка отклонения: {exc}'

    def get_debtors_report(self):
        self.update_overdue_loans_and_fines()
        return self.fetch_all("""
            SELECT u.login, u.login AS reader,
                   b.title, l.issue_date::date AS issue_date,
                   (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date AS due_date,
                   GREATEST(0, CURRENT_DATE - (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date) AS overdue_days,
                   (GREATEST(0, CURRENT_DATE - (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date) * lc.fine_per_day)::numeric(10,2) AS fine
            FROM loans l
            JOIN users u ON u.id = l.user_id
            JOIN books b ON b.id = l.book_id
            JOIN loan_conditions lc ON lc.id = l.condition_id
            WHERE l.returned_at IS NULL AND CURRENT_DATE > (l.issue_date + lc.days_allowed * INTERVAL '1 day')::date
            ORDER BY overdue_days DESC
        """)

    def get_most_popular_book_report(self, year, month):
        return self.fetch_all("""
            SELECT b.title, COUNT(l.id) AS loans_count
            FROM loans l JOIN books b ON b.id = l.book_id
            WHERE EXTRACT(YEAR FROM l.issue_date) = %s AND EXTRACT(MONTH FROM l.issue_date) = %s
            GROUP BY b.id, b.title
            ORDER BY loans_count DESC, b.title
            LIMIT 10
        """, (int(year), int(month)))

    def get_librarian_activity_report(self, year, month):
        return self.fetch_all("""
            SELECT u.login, u.login AS librarian,
                   COUNT(DISTINCT issued.id) AS issued_count,
                   COUNT(DISTINCT accepted.id) AS accepted_count
            FROM users u
            JOIN roles r ON r.id = u.role_id
            LEFT JOIN loans issued ON issued.issued_by = u.id
                AND EXTRACT(YEAR FROM issued.issue_date) = %s AND EXTRACT(MONTH FROM issued.issue_date) = %s
            LEFT JOIN loans accepted ON accepted.accepted_by = u.id
                AND accepted.returned_at IS NOT NULL
                AND EXTRACT(YEAR FROM accepted.returned_at) = %s AND EXTRACT(MONTH FROM accepted.returned_at) = %s
            WHERE lower(r.name) IN ('librarian', 'библиотекарь', 'admin', 'админ')
            GROUP BY u.id
            ORDER BY issued_count DESC, accepted_count DESC
        """, (int(year), int(month), int(year), int(month)))

    def get_books_not_issued_year_report(self):
        return self.fetch_all("""
            SELECT b.id, b.title, COALESCE(MAX(l.issue_date)::date::text, 'никогда') AS last_issue_date
            FROM books b
            LEFT JOIN loans l ON l.book_id = b.id
            GROUP BY b.id, b.title
            HAVING MAX(l.issue_date) IS NULL OR MAX(l.issue_date) < now() - INTERVAL '1 year'
            ORDER BY b.title
        """)

    def close(self):
        if self.conn:
            self.conn.close()
