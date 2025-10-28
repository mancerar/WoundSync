from fastapi import FastAPI, UploadFile, File, Depends
from sqlalchemy.orm import Session
import os
import shutil

from .database import db_engine, get_db, Base
from .model import Image, User

app = FastAPI()


os.makedirs("uploads", exist_ok=True) #make directory to store images uploaded locally (cloud based storage later on) 

#create tables needed
Base.metadata.create_all(bind=db_engine)

@app.post("/upload/") #upload through fast api using built in ui of FastAPI
async def upload_image(
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    
    file_path = f"uploads/{image.filename}"
    
    with open(file_path, "wb") as buffer:
        file_content = await image.read()
        buffer.write(file_content)
    
    file_size = len(file_content)
    new_image = Image(
        file_name = image.filename,
        file_path = file_path,
        file_type = image.content_type,
        file_size = file_size #in bytes
    )
    
    db.add(new_image)
    db.commit()
    db.refresh(new_image)
    
    return {
        "message": "Image uploaded successfully!",
        "filename": image.filename,
        "file_path": file_path,
        "file_type" : image.content_type,
        "file_size": file_size
    }

#uncomment below to see if database updates when you upload images
# @app.get("/check-images") #check what images are in the database
# def check_images(db: Session = Depends(get_db)):

#     images = db.query(Image).all()
    
#     return {
#         "total_images": len(images),
#         "images": [
#             {
#                 "image_id": img.image_id,
#                 "file_name": img.file_name,
#                 "file_type": img.file_type,
#                 "file_size": img.file_size,
#                 "time_stamp": img.time_stamp.isoformat() if img.time_stamp else None,
#             }
#             for img in images
#         ]
#     }