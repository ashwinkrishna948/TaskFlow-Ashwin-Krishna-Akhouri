import json
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


VALID_TRANSITIONS: dict[str, set[str]] = {
    "todo": {"in_progress", "done"},
    "in_progress": {"todo", "done"},
    "done": {"todo", "in_progress"},
}


async def list_tasks(
    conn: AsyncConnection,
    project_id: str,
    user_id: str,
    status: Optional[str] = None,
    assignee_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> list[dict]:
    access = await conn.execute(
        text("""
            SELECT 1
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id AND t.deleted_at IS NULL
            WHERE p.id = :pid
              AND (p.owner_id = :uid OR t.assignee_id = :uid)
            LIMIT 1
        """),
        {"pid": project_id, "uid": user_id},
    )
    if not access.fetchone():
        raise HTTPException(status_code=404, detail="not found")

    where_clauses = ["project_id = :pid", "deleted_at IS NULL"]
    params: dict = {"pid": project_id}

    if status is not None:
        where_clauses.append("status = :status")
        params["status"] = status

    if assignee_id is not None:
        where_clauses.append("assignee_id = :assignee_id")
        params["assignee_id"] = assignee_id

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    where = " AND ".join(where_clauses)
    result = await conn.execute(
        text(f"""
            SELECT * FROM tasks
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    return [dict(r._mapping) for r in result]


async def create_task(
    conn: AsyncConnection,
    project_id: str,
    user_id: str,
    data: dict,
    idempotency_key: Optional[str] = None,
) -> tuple[dict, bool]:
    """
    Returns (task_dict, created) where created=False means idempotency cache hit.
    """
    await _require_project_owner(conn, project_id, user_id)

    if idempotency_key:
        cached = await conn.execute(
            text("""
                SELECT response_body
                FROM idempotency_keys
                WHERE user_id = :uid AND idempotency_key = :key
            """),
            {"uid": user_id, "key": idempotency_key},
        )
        cached_row = cached.fetchone()
        if cached_row:
            return json.loads(cached_row._mapping["response_body"]), False

    result = await conn.execute(
        text("""
            INSERT INTO tasks (
                title, description, status, priority,
                project_id, assignee_id, due_date, created_by
            )
            VALUES (
                :title, :description, :status, :priority,
                :project_id, :assignee_id, :due_date, :created_by
            )
            RETURNING *
        """),
        {
            "title": data["title"],
            "description": data.get("description"),
            "status": data.get("status", "todo"),
            "priority": data.get("priority", "medium"),
            "project_id": project_id,
            "assignee_id": str(data["assignee_id"]) if data.get("assignee_id") else None,
            "due_date": data.get("due_date"),
            "created_by": user_id,
        },
    )
    task = dict(result.fetchone()._mapping)

    if idempotency_key:
        await conn.execute(
            text("""
                INSERT INTO idempotency_keys (user_id, idempotency_key, response_body)
                VALUES (:uid, :key, :body)
                ON CONFLICT (user_id, idempotency_key) DO NOTHING
            """),
            {
                "uid": user_id,
                "key": idempotency_key,
                "body": json.dumps(task, default=str),
            },
        )

    return task, True


async def get_task(
    conn: AsyncConnection, project_id: str, task_id: str, user_id: str
) -> dict:
    """
    Returns a live task only if the user is the project owner or assignee,
    and the task belongs to the given project.
    Soft-deleted tasks return 404 — same as non-existent tasks.
    """
    result = await conn.execute(
        text("""
            SELECT t.*
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            WHERE t.id = :tid
              AND t.project_id = :pid
              AND t.deleted_at IS NULL
              AND (p.owner_id = :uid OR t.assignee_id = :uid)
        """),
        {"tid": task_id, "pid": project_id, "uid": user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return dict(row._mapping)


async def update_task(
    conn: AsyncConnection, project_id: str, task_id: str, user_id: str, updates: dict
) -> dict:
    current = await _require_task_access(conn, project_id, task_id, user_id)

    if not updates:
        return current

    if "status" in updates:
        current_status = current["status"]
        new_status = updates["status"]
        if new_status != current_status:
            allowed = VALID_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                raise HTTPException(
                    status_code=422,
                    detail=f"invalid status transition: {current_status} → {new_status}",
                )

    allowed_cols = {"title", "description", "status", "priority", "assignee_id", "due_date"}
    safe = {k: v for k, v in updates.items() if k in allowed_cols}

    if not safe:
        return current

    if "assignee_id" in safe and safe["assignee_id"] is not None:
        safe["assignee_id"] = str(safe["assignee_id"])

    set_clause = ", ".join(f"{col} = :{col}" for col in safe)
    safe["tid"] = task_id

    result = await conn.execute(
        text(f"UPDATE tasks SET {set_clause}, updated_at = NOW() WHERE id = :tid RETURNING *"),
        safe,
    )
    return dict(result.fetchone()._mapping)


async def delete_task(
    conn: AsyncConnection, project_id: str, task_id: str, user_id: str
) -> None:
    """Soft delete: sets deleted_at rather than removing the row. Returns 404 on subsequent reads."""
    result = await conn.execute(
        text("""
            SELECT t.id, t.created_by, p.owner_id
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            WHERE t.id = :tid AND t.project_id = :pid AND t.deleted_at IS NULL
        """),
        {"tid": task_id, "pid": project_id},
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="not found")

    is_project_owner = str(row._mapping["owner_id"]) == user_id
    is_task_creator = str(row._mapping["created_by"]) == user_id
    if not is_project_owner and not is_task_creator:
        raise HTTPException(status_code=403, detail="forbidden")

    await conn.execute(
        text("UPDATE tasks SET deleted_at = NOW() WHERE id = :tid"),
        {"tid": task_id},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _require_project_owner(
    conn: AsyncConnection, project_id: str, user_id: str
) -> None:
    result = await conn.execute(
        text("SELECT owner_id FROM projects WHERE id = :pid"), {"pid": project_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    if str(row._mapping["owner_id"]) != user_id:
        raise HTTPException(status_code=403, detail="forbidden")


async def _require_task_access(
    conn: AsyncConnection, project_id: str, task_id: str, user_id: str
) -> dict:
    """Returns task dict if user is project owner or assignee, task is live, and belongs to project."""
    result = await conn.execute(
        text("""
            SELECT t.*
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            WHERE t.id = :tid
              AND t.project_id = :pid
              AND t.deleted_at IS NULL
              AND (p.owner_id = :uid OR t.assignee_id = :uid)
        """),
        {"tid": task_id, "pid": project_id, "uid": user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return dict(row._mapping)
