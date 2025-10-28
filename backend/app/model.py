# creates tables for database for user info and image info
from .database import Base
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

class Image(Base): #stores image name and file paths
    __tablename__ = "images"
    
    image_id = Column(Integer, primary_key=True,  index=True) #primary key marks column as primary of table, index creates and indexed column
    #user_id = Column(Integer, nullable=False, index=True) # need to link user_id in image db to user db
    file_name = Column(String, nullable=False) #cannot be null
    file_path = Column(String, nullable=False)
    file_type = Column(String)
    file_size = Column(Integer, nullable=False)
    time_stamp = Column(DateTime(timezone=True), server_default=func.now()) #update row with time stamp when updated
    
    #could add session id to group photos together
    #
    

class User(Base): #stores names, emails , and id numbers
    __tablename__ = "users"
    
    user_id = Column(Integer,primary_key=True,  index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String)
    
    # need a way to link user db to image db
    
    
    