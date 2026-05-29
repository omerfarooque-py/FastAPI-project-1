from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


class DBUser(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username  = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    tasks = relationship("DBTask", back_populates="owner")


class DBTask(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key= True, index = True, autoincrement=True)
    title = Column(String, nullable =False)
    description = Column(String, nullable = False)
    is_completed = Column(Boolean, default= False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("DBUser", back_populates="tasks")
