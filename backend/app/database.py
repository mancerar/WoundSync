# this file creates an empty database for processung in another file
from sqlalchemy import create_engine
# sqlalchemy lets me work with databases using python objects
from sqlalchemy.orm import sessionmaker, declarative_base



SQL_DATABASE = "sqlite:///../wound.db" #database URL
# sqlite is being used with sqlalchemy, creates a database in folder above

db_engine = create_engine( #craetes an empty databae with the database name above
    SQL_DATABASE, 
    connect_args={"check_same_thread": False} #allows multiple threads to database (multithreading)
) 

Session = sessionmaker(autoflush=False, bind=db_engine)
#session maker gives every connection their own workspace in the database

Base = declarative_base() #parent

def get_db(): #function provides database sessions when called
    db = Session()
    try:
        yield db
    finally:
        db.close()
# 