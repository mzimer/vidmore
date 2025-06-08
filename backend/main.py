from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from db import SessionLocal
from models import User, UserStatus, Task, TaskStatus

app = FastAPI(
    title="Vidmore API",
    version="0.1.0",
    openapi_version="3.1.0",
    servers=[{"url": "/api"}]
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/users/register")
def register_user(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if user:
        return {"msg": "already_registered", "status": user.status.value}
    user = User(telegram_id=telegram_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"msg": "registered", "status": user.status.value}

@app.get("/api/users/{telegram_id}")
def get_user(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"telegram_id": user.telegram_id, "status": user.status.value}

@app.post("/api/users/update_status")
def update_user_status(
    telegram_id: str = Query(...),
    status: str = Query(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if status not in ["pending", "approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    user.status = UserStatus(status)
    db.commit()
    db.refresh(user)
    return {"msg": "status_updated", "telegram_id": user.telegram_id, "status": user.status.value}

@app.post("/api/tasks/create")
def create_task(
    telegram_id: str,
    video_url: str,
    action: str = "download",  # <--- добавили параметр
    db: Session = Depends(get_db)
):
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    task = Task(user_id=user.id, video_url=video_url, action=action)
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"msg": "task_created", "task_id": task.id, "status": task.status.value}

@app.get("/api/tasks/{telegram_id}")
def get_tasks(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    tasks = db.query(Task).filter_by(user_id=user.id).all()
    return [{"task_id": t.id, "video_url": t.video_url, "status": t.status.value} for t in tasks]

@app.get("/api/tasks/")
def get_all_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    return [{"task_id": t.id, "user_id": t.user_id, "video_url": t.video_url, "status": t.status.value} for t in tasks]

@app.post("/api/tasks/update_status")
def update_task_status(task_id: int, status: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if status not in [s.value for s in TaskStatus]:
        raise HTTPException(status_code=400, detail="Invalid status")
    task.status = TaskStatus(status)
    db.commit()
    db.refresh(task)
    return {"msg": "task_status_updated", "task_id": task.id, "status": task.status.value}

@app.get("/api/")
def root():
    return {"status": "ok"}
