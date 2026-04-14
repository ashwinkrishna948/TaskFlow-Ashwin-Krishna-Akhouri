from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
    ProjectWithTasksResponse,
)
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await project_service.list_projects(
        conn, current_user["user_id"], page=page, page_size=page_size
    )


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreateRequest,
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await project_service.create_project(
        conn, current_user["user_id"], body.name, body.description
    )


@router.get("/{project_id}", response_model=ProjectWithTasksResponse)
async def get_project(
    project_id: UUID,
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    return await project_service.get_project(conn, str(project_id), current_user["user_id"])


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: ProjectUpdateRequest,
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)
    return await project_service.update_project(
        conn, str(project_id), current_user["user_id"], updates
    )


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    current_user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    await project_service.delete_project(conn, str(project_id), current_user["user_id"])
