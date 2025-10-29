from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import os
import shutil

from .database import db_engine, get_db, Base
from .model import Image, User
from .analysis import measure_wound, estimated_centimetres, ASSUMED_PIXELS_PER_CM

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

    measurements = measure_wound(file_path)
    if measurements:
        new_image.wound_area_px = measurements.get("wound_area_px")
        new_image.wound_width_px = measurements.get("wound_width_px")
        new_image.wound_height_px = measurements.get("wound_height_px")
    
    db.add(new_image)
    db.commit()
    db.refresh(new_image)
    
    return {
        "message": "Image uploaded successfully!",
        "filename": image.filename,
        "file_path": file_path,
        "file_type" : image.content_type,
        "file_size": file_size,
        "assumed_pixels_per_cm": ASSUMED_PIXELS_PER_CM,
        "measurements": measurements
    }


@app.get("/images/{image_id}")
def get_image(image_id: int, db: Session = Depends(get_db)):
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    cm_metrics = estimated_centimetres(image.wound_area_px, image.wound_width_px, image.wound_height_px)

    return {
        "image_id": image.image_id,
        "file_name": image.file_name,
        "file_type": image.file_type,
        "file_size": image.file_size,
        "time_stamp": image.time_stamp.isoformat() if image.time_stamp else None,
        "wound_area_px": image.wound_area_px,
        "wound_width_px": image.wound_width_px,
        "wound_height_px": image.wound_height_px,
        "assumed_pixels_per_cm": ASSUMED_PIXELS_PER_CM,
        "estimated_measurements": cm_metrics,
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