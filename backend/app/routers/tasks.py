from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth import get_current_user
from app.database import get_db
from app.models import TaskCreateRequest, TaskResponse, TaskStatus, TaskUpdateRequest
from app.services import task_service

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    project_id: UUID,
    status: Optional[TaskStatus] = Query(default=None),
    assignee_id: Optional[UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await task_service.list_tasks(
        conn,
        str(project_id),
        current_user["user_id"],
        status=status.value if status else None,
        assignee_id=str(assignee_id) if assignee_id else None,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    project_id: UUID,
    body: TaskCreateRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    task, _created = await task_service.create_task(
        conn,
        str(project_id),
        current_user["user_id"],
        body.model_dump(),
        idempotency_key=idempotency_key,
    )
    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    project_id: UUID,
    task_id: UUID,
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await task_service.get_task(conn, str(project_id), str(task_id), current_user["user_id"])


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    project_id: UUID,
    task_id: UUID,
    body: TaskUpdateRequest,
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)
    return await task_service.update_task(conn, str(project_id), str(task_id), current_user["user_id"], updates)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    project_id: UUID,
    task_id: UUID,
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    await task_service.delete_task(conn, str(project_id), str(task_id), current_user["user_id"])
