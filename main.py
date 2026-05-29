from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import src.models
from src.database import engine, SessionLocal
from sqlalchemy.orm import Session
from src.security import get_password_hash, verify_password, create_access_token
from datetime import datetime, timedelta
from jose import JWTError, jwt 
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("MY_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
src.models.Base.metadata.create_all(bind=engine)


"""
DEVELOPER NOTE / POST-MORTEM:
The local development database was dropped and rebuilt to resolve a schema mismatch. 
During development, structural changes were made to the models and Pydantic validation 
layers (fixing parameter casing/typographical naming conventions to resolve a 422 error). 
Because SQLAlchemy's metadata.create_all() does not alter tables in-place if they 
already exist, dropping the database was required to flush out the stale state and 
properly synchronize the new fields.
"""


app = FastAPI(title="SQL-Backed Task Tracker")


def get_db():
    print("open session")
    db = SessionLocal()
    try:
        yield db
    finally:
        print("close session")
        db.close()


from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(
        token: str = Depends(oauth2_scheme),
        db : Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username : str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(src.models.DBUser).filter(src.models.DBUser.username == username).first()
    if not user:
        raise credentials_exception
    return user

# --- PYDANTIC SCHEMA (For Data Incoming from HTTP requests) ---


class UserCreate(BaseModel):
    username : str
    password : str

class TaskCreate(BaseModel): #changed from TaskCreat to TaskCreate
    title: str
    description: Optional[str] = None
    is_completed: bool = False



# --- ROUTES ---

@app.post("/register/")
def create_account(
    user: UserCreate,
    db: Session = Depends(get_db)
):

    existing_user = db.query(src.models.DBUser).filter(src.models.DBUser.username == user.username).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="username already exists")
    
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="password too short < 8")
    
    hashed_password = get_password_hash(user.password)

    db_user = src.models.DBUser(
        username = user.username,
        hashed_password = hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return{
        "message" : "successfuly created an account",
        "username" : user.username
    }

@app.post("/login/")
def user_login(
    user_credentials : OAuth2PasswordRequestForm = Depends(),
    db : Session = Depends(get_db)
):
    user_exists = db.query(src.models.DBUser).filter(src.models.DBUser.username == user_credentials.username).first()
    
    if user_exists:
        password_verification = verify_password(user_credentials.password, user_exists.hashed_password)
        if password_verification:
            token_payload = {"sub" : user_exists.username}
            jwt_token = create_access_token(data=token_payload)
            return{
                "access_token" : jwt_token,
                "token_type" : "bearer",
                "status" : "login_success"
            }
        else:
            raise HTTPException(status_code=400, detail="invalid credentials")
    else:
        raise HTTPException(status_code=400, detail="invalid credentials")


@app.post("/tasks/")
def create_task(
    task : TaskCreate, 
    db : Session = Depends(get_db),
    current_user : src.models.DBUser = Depends(get_current_user)
):
    db_task = src.models.DBTask(
        title = task.title,
        description = task.description,
        is_completed = task.is_completed,
        owner_id = current_user.id
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return{
        "status": "Task created successfully",
        "data " : {
            "id" : db_task.id,
            "title": db_task.title,
            "description": db_task.description,
            "is_completed" : db_task.is_completed 
        }
    }


@app.get("/tasks/")
def get_all_tasks(
    db : Session = Depends(get_db),
    current_user: src.models.DBUser = Depends(get_current_user)
):
    all_items = db.query(src.models.DBTask).filter(src.models.DBTask.owner_id == current_user.id).all()
    return all_items



@app.get("/tasks/{task_id}")
def get_task(
    task_id : int,
    db : Session = Depends(get_db),
    current_user : src.models.DBUser = Depends(get_current_user)
):
    task = db.query(src.models.DBTask).filter(src.models.DBTask.id == task_id).first()

    if task and current_user.id == task.owner_id:
       return task
    else:
        raise HTTPException(status_code=404, detail="task with specific ID not found")
    
@app.put("/tasks/{task_id}")
def update_task(
    task_id : int,
    updated_task : TaskCreate,
    db : Session = Depends(get_db)
):
    task = db.query(src.models.DBTask).filter(src.models.DBTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task does not exist")
    
    task.title = updated_task.title
    task.description = updated_task.description
    task.is_completed = updated_task.is_completed

    db.commit()
    db.refresh(task)

    return {
        "status": "Task updated successfully",
        "data": task
    }

@app.delete("/delete/{task_id}")
def delete_task(
    task_id : int,
   # delete_task : TaskCreate,
    db : Session = Depends(get_db)
):
    task = db.query(src.models.DBTask).filter(src.models.DBTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="task does not exist")
    
    db.delete(task)
    db.commit()

    return{
        "status" : "success",
        "message" : f"successfully deleted the task with ID {task_id}"
    }