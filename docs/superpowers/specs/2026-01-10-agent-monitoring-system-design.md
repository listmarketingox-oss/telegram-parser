# Agent-Based Monitoring System — Design Spec

**Date:** 2026-01-10  
**Status:** Design Approved  
**Priority:** High  

---

## Overview

Implement autonomous monitoring agents that periodically search for keywords in selected sources and notify users when matches are found. Each agent runs on a schedule (hourly, 8 AM–8 PM) and creates notifications in-app when results are discovered.

**Key capabilities:**
- Create agents with full control (keywords, sources, search mode)
- Enable/disable agents without deletion
- View agent history and statistics
- In-app notifications when matches found
- Edit agent parameters at any time

---

## User Requirements

**Agent creation flow:**
- User defines: name, keywords, sources/collections, search mode
- System assigns fixed schedule: hourly 8 AM–8 PM
- Agent runs automatically, no manual trigger needed

**Agent management:**
- Toggle enable/disable
- Edit parameters (keywords, sources, mode)
- Delete if no longer needed
- View results history
- See statistics (last run, total matches found)

**Notifications:**
- In-app only (no email/bot)
- Show when agent finds matches
- Clickable → view full results
- Mark as read
- Persist in DB

**Constraints:**
- Max 10 simultaneous active agents (per user or global — TBD in implementation)
- Search runs hourly within business hours (8–20)
- No manual trigger for ad-hoc runs

---

## Architecture

### System Flow

```
APScheduler (cron: every hour 8-20)
    ↓
Check active agents in DB
    ↓
For each active agent:
  Create Job(agent_id, keywords, sources, mode)
    ↓
Worker processes Job queue:
  1. Call live_search() for each keyword
  2. Collect all matches
  3. Save results to AgentResult
  4. Create Notification if matches > 0
  5. Update agent.last_run_at
    ↓
UI: Display notifications + results
```

### Database Models

#### Agent (new)
```python
class Agent(UUIDMixin, Base):
    __tablename__ = "agents"
    
    user_id: UUID              # Owner
    name: str                  # Display name
    keywords: list[str]        # JSONB array of search keywords
    source_ids: list[UUID]     # JSONB: which sources to search
    collection_ids: list[UUID] # JSONB: or which collections
    search_mode: str           # "exact" | "smart" | "aggressive"
    cron_schedule: str         # "0 8-20 * * *" (readonly)
    is_active: bool            # Enable/disable toggle
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None
    results_count: int         # Cumulative matches found
```

#### AgentResult (new)
```python
class AgentResult(UUIDMixin, Base):
    __tablename__ = "agent_results"
    
    agent_id: UUID
    found_count: int           # How many matches
    matches: list[dict]        # JSONB: serialized Match objects
    created_at: datetime
    
    # Links to notification if created
    notification_id: UUID | None
```

#### Notification (new)
```python
class Notification(UUIDMixin, Base):
    __tablename__ = "notifications"
    
    user_id: UUID
    type: str                  # "agent_found"
    agent_id: UUID
    agent_result_id: UUID
    title: str                 # "Agent 'Monitor ставка' found 3 matches"
    is_read: bool              # Default: False
    created_at: datetime
```

#### Job Model (update)
```python
# Add to JobType enum:
class JobType(str, enum.Enum):
    parse_source = "parse_source"
    first_pass = "first_pass"
    reauth = "reauth"
    agent_monitor = "agent_monitor"  # NEW
```

---

## Implementation Details

### 1. Scheduler (`app/worker.py`)

**Add APScheduler job:**
```python
@scheduler.scheduled_job('cron', hour='8-20', minute='0')
async def check_active_agents():
    """
    Run every hour 8 AM–8 PM.
    For each active agent, create Job in queue.
    """
    async with async_session() as db:
        result = await db.execute(
            select(Agent).where(Agent.is_active == True)
        )
        agents = result.scalars().all()
        
        for agent in agents:
            job = Job(
                type=JobType.agent_monitor,
                payload={
                    'agent_id': str(agent.id),
                    'keywords': agent.keywords,
                    'source_ids': agent.source_ids,
                    'collection_ids': agent.collection_ids,
                    'search_mode': agent.search_mode,
                },
                status=JobStatus.queued
            )
            db.add(job)
        await db.commit()
        logger.info("Created %d agent monitor jobs", len(agents))
```

### 2. Worker Processing (`app/worker.py`)

**Extend job processor:**
```python
elif job.type == JobType.agent_monitor:
    agent_id = UUID(job.payload['agent_id'])
    keywords = job.payload['keywords']
    source_ids = job.payload.get('source_ids', [])
    collection_ids = job.payload.get('collection_ids', [])
    mode = job.payload['search_mode']
    
    # Resolve collections → source_ids
    if collection_ids:
        source_ids.extend(await get_sources_from_collections(db, collection_ids))
    
    # Search all keywords, collect matches
    all_matches = []
    for keyword in keywords:
        try:
            matches = await live_search(
                keyword=keyword,
                source_ids=source_ids,
                mode=mode
            )
            all_matches.extend(matches)
        except Exception as e:
            logger.error(f"Agent {agent_id} keyword {keyword} failed: {e}")
            continue
    
    # Save results
    result = AgentResult(
        agent_id=agent_id,
        found_count=len(all_matches),
        matches=all_matches
    )
    db.add(result)
    await db.flush()  # Get result.id
    
    # Create notification if matches found
    agent = await db.get(Agent, agent_id)
    if all_matches:
        notification = Notification(
            user_id=agent.user_id,
            type='agent_found',
            agent_id=agent_id,
            agent_result_id=result.id,
            title=f"Agent '{agent.name}' found {len(all_matches)} matches"
        )
        db.add(notification)
    
    # Update agent stats
    agent.last_run_at = datetime.utcnow()
    agent.results_count += len(all_matches)
    
    # Mark job done
    job.status = JobStatus.done
    await db.commit()
    logger.info(f"Agent {agent_id} completed: {len(all_matches)} matches")
```

### 3. API Endpoints (`app/api/agents.py` — new)

```python
@router.post("", status_code=201)
async def create_agent(
    body: AgentCreate,  # name, keywords[], source_ids[], collection_ids[], mode
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create new monitoring agent."""
    agent = Agent(
        user_id=user.id,
        name=body.name,
        keywords=body.keywords,
        source_ids=body.source_ids,
        collection_ids=body.collection_ids,
        search_mode=body.mode,
        cron_schedule="0 8-20 * * *",  # Fixed
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    return {"id": str(agent.id), "name": agent.name}

@router.get("")
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all agents for current user."""
    result = await db.execute(
        select(Agent).where(Agent.user_id == user.id)
    )
    agents = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "keywords": a.keywords,
            "is_active": a.is_active,
            "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
            "results_count": a.results_count,
        }
        for a in agents
    ]

@router.get("/{agent_id}")
async def get_agent(agent_id: UUID, ...):
    """Get agent details."""

@router.patch("/{agent_id}")
async def update_agent(agent_id: UUID, body: AgentUpdate, ...):
    """Update agent (keywords, sources, mode, name)."""

@router.delete("/{agent_id}")
async def delete_agent(agent_id: UUID, ...):
    """Delete agent."""

@router.post("/{agent_id}/toggle")
async def toggle_agent(agent_id: UUID, ...):
    """Enable/disable agent."""

@router.get("/{agent_id}/results")
async def agent_results(agent_id: UUID, limit: int = 50, ...):
    """Get results history for agent."""

@router.get("/notifications")
async def get_notifications(db: AsyncSession, user: User):
    """Get unread notifications for user."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()

@router.patch("/notifications/{notif_id}")
async def mark_notification_read(notif_id: UUID, ...):
    """Mark notification as read."""
```

### 4. UI Pages

#### `/agents` — Main Agents Page

**Three sections:**

1. **Agents List**
   - Table: Name | Keywords | Sources | Mode | Status | Last Run | Results
   - Buttons: Create | Edit | Delete | Toggle

2. **Create/Edit Agent Form**
   - Name (text input)
   - Keywords (multi-select or textarea)
   - Sources or Collections (multi-select)
   - Search Mode (radio: exact/smart/aggressive)
   - Schedule (readonly: "Every hour 8 AM–8 PM")
   - Submit button

3. **Notifications Panel**
   - List of unread notifications
   - Click → view results for that agent
   - Mark as read button

#### `/agents/{id}/results` — Agent Results Detail

- Full results table (like search results)
- Date range filter
- Export CSV/XLSX
- Back to agents list

---

## Testing Strategy

**Unit tests** (`tests/services/test_agents.py`):
- Create agent with valid data
- Update agent parameters
- Toggle enable/disable
- Delete agent
- Resolve collections → source_ids

**Integration tests** (`tests/api/test_agents_api.py`):
- POST /agents creates agent
- PATCH /agents/{id} updates
- DELETE removes
- GET returns list

**Worker tests** (`tests/test_worker_agent_monitor.py`):
- Job created for each active agent
- Search executed with correct params
- Results saved to AgentResult
- Notification created if matches > 0
- agent.last_run_at updated

**Manual testing:**
- Create 3 agents with different keywords
- Wait for hourly run (or mock scheduler)
- Verify notifications appear
- Click notification → view results
- Edit agent → re-run
- Toggle disable → stops running

---

## Rollout Plan

**Phase 1:**
- Add Agent, AgentResult, Notification models
- Implement API CRUD endpoints
- Create basic UI

**Phase 2:**
- Add scheduler job (check_active_agents)
- Add worker job processing (agent_monitor)
- Test end-to-end

**Phase 3:**
- Polish UI (notifications panel, results view)
- Add statistics dashboard
- Deploy to Railway

---

## Performance Considerations

**Scaling:**
- Max 10 active agents per user ✓ (constraint)
- 12 jobs per agent per day (hourly 8-20)
- Each job: ~30-60s (depends on keyword count and sources)
- DB: agents table ~50 rows, agent_results ~1000s per day, notifications pruned weekly

**Optimization:**
- Parallelize keyword searches within agent (asyncio.gather)
- Index: Agent(user_id, is_active), AgentResult(agent_id, created_at)
- Notification cleanup: keep last 100 per user

---

## Future Enhancements

- Custom schedules (not just hourly 8-20)
- Pause/resume (vs enable/disable)
- Alert thresholds (only notify if > N matches)
- Digest mode (daily summary instead of per-run)
- Agent groups/folders
- Sharing agents with team members
- Rate limiting per agent

---

## Acceptance Criteria

✅ Agent CRUD works (create, read, update, delete)  
✅ Schedule runs hourly 8 AM–8 PM automatically  
✅ Notifications created when matches found  
✅ UI shows agents list + notifications  
✅ Can edit agent parameters  
✅ Results persist and are viewable  
✅ No performance regression on live_search  
✅ Tests pass (unit + integration + manual)  

---

## Timeline

- **Effort:** ~12-16 hours
- **Complexity:** Medium-High (DB models, scheduler, worker, UI)
- **Risk:** Medium (scheduler reliability, concurrency in worker)
