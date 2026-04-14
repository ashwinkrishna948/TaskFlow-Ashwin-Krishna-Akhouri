from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def list_projects(
    conn: AsyncConnection, user_id: str, page: int = 1, page_size: int = 20
) -> list[dict]:
    offset = (page - 1) * page_size
    result = await conn.execute(
        text("""
            SELECT DISTINCT p.*
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id AND t.deleted_at IS NULL
            WHERE p.owner_id = :uid OR t.assignee_id = :uid
            ORDER BY p.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"uid": user_id, "limit": page_size, "offset": offset},
    )
    return [dict(r._mapping) for r in result]


async def create_project(
    conn: AsyncConnection, user_id: str, name: str, description
) -> dict:
    result = await conn.execute(
        text("""
            INSERT INTO projects (name, description, owner_id)
            VALUES (:name, :description, :owner_id)
            RETURNING *
        """),
        {"name": name, "description": description, "owner_id": user_id},
    )
    row = result.fetchone()
    return dict(row._mapping)


async def get_project(
    conn: AsyncConnection, project_id: str, user_id: str
) -> dict:
    result = await conn.execute(
        text("""
            SELECT DISTINCT p.*
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id AND t.deleted_at IS NULL
            WHERE p.id = :pid
              AND (p.owner_id = :uid OR t.assignee_id = :uid)
        """),
        {"pid": project_id, "uid": user_id},
    )
    project_row = result.fetchone()

    if not project_row:
        raise HTTPException(status_code=404, detail="not found")

    tasks_result = await conn.execute(
        text("""
            SELECT * FROM tasks
            WHERE project_id = :pid AND deleted_at IS NULL
            ORDER BY created_at DESC
        """),
        {"pid": project_id},
    )
    result_dict = dict(project_row._mapping)
    result_dict["tasks"] = [dict(r._mapping) for r in tasks_result]
    return result_dict


async def update_project(
    conn: AsyncConnection, project_id: str, user_id: str, updates: dict
) -> dict:
    await _require_owner(conn, project_id, user_id)

    if not updates:
        result = await conn.execute(
            text("SELECT * FROM projects WHERE id = :pid"), {"pid": project_id}
        )
        return dict(result.fetchone()._mapping)

    allowed = {"name", "description"}
    safe = {k: v for k, v in updates.items() if k in allowed}
    set_clause = ", ".join(f"{col} = :{col}" for col in safe)
    safe["pid"] = project_id

    result = await conn.execute(
        text(f"UPDATE projects SET {set_clause} WHERE id = :pid RETURNING *"),
        safe,
    )
    return dict(result.fetchone()._mapping)


async def delete_project(
    conn: AsyncConnection, project_id: str, user_id: str
) -> None:
    await _require_owner(conn, project_id, user_id)
    await conn.execute(
        text("DELETE FROM projects WHERE id = :pid"), {"pid": project_id}
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _require_owner(
    conn: AsyncConnection, project_id: str, user_id: str
) -> dict:
    result = await conn.execute(
        text("SELECT owner_id FROM projects WHERE id = :pid"), {"pid": project_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    if str(row._mapping["owner_id"]) != user_id:
        raise HTTPException(status_code=404, detail="not found")
    return dict(row._mapping)
