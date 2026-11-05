from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Task, User

app = FastAPI(title="Tasks API")
DB = Annotated[AsyncSession, Depends(get_session)]


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)


class UserOut(UserCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    done: bool = False
    owner_id: int = Field(gt=0)


class TaskOut(TaskCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TaskPatch(BaseModel):
    title: str = Field(default=None, min_length=1, max_length=200)
    description: str = Field(default=None)
    done: bool = Field(default=None)


@app.middleware("http")
async def process_time(request, call_next):
    start = perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(perf_counter() - start)
    return response


@app.post("/users", status_code=201, response_model=UserOut)
async def create_user(data: UserCreate, db: DB):
    user = User(**data.model_dump())
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Email already exists") from None
    return user


@app.post("/tasks", status_code=201, response_model=TaskOut)
async def create_task(data: TaskCreate, db: DB):
    if await db.get(User, data.owner_id) is None:
        raise HTTPException(404, "Owner not found")
    task = Task(**data.model_dump())
    db.add(task)
    await db.commit()
    return task


@app.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    db: DB,
    done: bool | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(Task).order_by(Task.id)
    if done is not None:
        query = query.where(Task.done == done)
    return (await db.scalars(query.offset(offset).limit(limit))).all()


async def find_task(task_id: int, db: AsyncSession):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@app.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task(task_id: int, db: DB):
    return await find_task(task_id, db)


@app.patch("/tasks/{task_id}", response_model=TaskOut)
async def patch_task(task_id: int, data: TaskPatch, db: DB):
    task = await find_task(task_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.commit()
    return task


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, db: DB):
    task = await find_task(task_id, db)
    await db.delete(task)
    await db.commit()
    return Response(status_code=204)
