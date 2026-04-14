import os
import sys

import psycopg2
from psycopg2.extras import RealDictCursor
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        cursor_factory=RealDictCursor,
    )


def run():
    conn = get_conn()
    try:
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email = 'test@example.com'")
        existing = cur.fetchone()
        if existing:
            print("Seed data already present — skipping.")
            return

        hashed = pwd_context.hash("password123")
        cur.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s) RETURNING id",
            ("Test User", "test@example.com", hashed),
        )
        user_id = cur.fetchone()["id"]
        print(f"Created seed user: test@example.com (id={user_id})")

        cur.execute(
            "INSERT INTO projects (name, description, owner_id) VALUES (%s, %s, %s) RETURNING id",
            ("Demo Project", "A sample project created by the seed script.", user_id),
        )
        project_id = cur.fetchone()["id"]
        print(f"Created seed project: Demo Project (id={project_id})")

        tasks = [
            ("Set up project repository", "todo",        "high"),
            ("Implement authentication",  "in_progress", "high"),
            ("Write API documentation",   "done",        "medium"),
        ]
        for title, status, priority in tasks:
            cur.execute(
                """
                INSERT INTO tasks (title, status, priority, project_id, created_by)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (title, status, priority, project_id, user_id),
            )
            print(f"  Created task: '{title}' [{status}]")

        conn.commit()
        print("Seed complete.")
    except Exception as exc:
        conn.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
