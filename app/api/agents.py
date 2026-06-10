"""Agents API - autonomous monitoring management."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.agent import Agent
from app.models.agent_result import AgentResult
from app.models.notification import Notification
from app.models.user import AppUser

router = APIRouter(
    prefix="/agents",
    tags=["agents"],
    dependencies=[Depends(get_current_user)],
)


# ===== Schemas =====


class AgentCreate(BaseModel):
    name: str
    keywords: list[str]
    source_ids: list[str] = []
    collection_ids: list[str] = []
    search_mode: str = "smart"


class AgentUpdate(BaseModel):
    name: str | None = None
    keywords: list[str] | None = None
    source_ids: list[str] | None = None
    collection_ids: list[str] | None = None
    search_mode: str | None = None


class AgentResponse(BaseModel):
    id: str
    name: str
    keywords: list[str]
    source_ids: list[str]
    collection_ids: list[str]
    search_mode: str
    is_active: bool
    last_run_at: str | None
    results_count: int
    created_at: str


class NotificationResponse(BaseModel):
    id: str
    type: str
    agent_id: str
    title: str
    is_read: bool
    created_at: str


# ===== Endpoints =====


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    """Create new monitoring agent."""
    agent = Agent(
        user_id=user.id,
        name=body.name,
        keywords=body.keywords,
        source_ids=body.source_ids,
        collection_ids=body.collection_ids,
        search_mode=body.search_mode,
        cron_schedule="0 8-20 * * *",  # Fixed schedule
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return {
        "id": str(agent.id),
        "name": agent.name,
        "keywords": agent.keywords,
    }


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    """List all agents for current user."""
    result = await db.execute(
        select(Agent)
        .where(Agent.user_id == user.id)
        .order_by(Agent.created_at.desc())
    )
    agents = result.scalars().all()
    return [
        AgentResponse(
            id=str(a.id),
            name=a.name,
            keywords=a.keywords,
            source_ids=a.source_ids,
            collection_ids=a.collection_ids,
            search_mode=a.search_mode,
            is_active=a.is_active,
            last_run_at=a.last_run_at.isoformat() if a.last_run_at else None,
            results_count=a.results_count,
            created_at=a.created_at.isoformat(),
        )
        for a in agents
    ]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    """Get agent details."""
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        keywords=agent.keywords,
        source_ids=agent.source_ids,
        collection_ids=agent.collection_ids,
        search_mode=agent.search_mode,
        is_active=agent.is_active,
        last_run_at=agent.last_run_at.isoformat() if agent.last_run_at else None,
        results_count=agent.results_count,
        created_at=agent.created_at.isoformat(),
    )


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    """Update agent parameters."""
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    if body.name is not None:
        agent.name = body.name
    if body.keywords is not None:
        agent.keywords = body.keywords
    if body.source_ids is not None:
        agent.source_ids = body.source_ids
    if body.collection_ids is not None:
        agent.collection_ids = body.collection_ids
    if body.search_mode is not None:
        agent.search_mode = body.search_mode

    agent.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(agent)

    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        keywords=agent.keywords,
        source_ids=agent.source_ids,
        collection_ids=agent.collection_ids,
        search_mode=agent.search_mode,
        is_active=agent.is_active,
        last_run_at=agent.last_run_at.isoformat() if agent.last_run_at else None,
        results_count=agent.results_count,
        created_at=agent.created_at.isoformat(),
    )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    """Delete agent."""
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()


@router.post("/{agent_id}/toggle")
async def toggle_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    """Enable/disable agent."""
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = not agent.is_active
    await db.commit()
    return {"is_active": agent.is_active}


@router.get("/{agent_id}/results")
async def agent_results(
    agent_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    """Get results history for agent."""
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(AgentResult)
        .where(AgentResult.agent_id == agent_id)
        .order_by(AgentResult.created_at.desc())
        .limit(limit)
    )
    results = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "found_count": r.found_count,
            "matches_count": len(r.matches or []),
            "created_at": r.created_at.isoformat(),
        }
        for r in results
    ]


# ===== Notifications =====


@router.get("/notifications/list")
async def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    """Get notifications for current user."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    notifications = result.scalars().all()
    return [
        NotificationResponse(
            id=str(n.id),
            type=n.type,
            agent_id=str(n.agent_id),
            title=n.title,
            is_read=n.is_read,
            created_at=n.created_at.isoformat(),
        )
        for n in notifications
    ]


@router.patch("/notifications/{notif_id}/read")
async def mark_notification_read(
    notif_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    """Mark notification as read."""
    notification = await db.get(Notification, notif_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    await db.commit()
    return {"is_read": True}
