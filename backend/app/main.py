from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from PIL import Image, ImageDraw, ImageFont
import io
import os
import shutil
import requests

from roboflow import Roboflow
from supabase import create_client, Client
from datetime import datetime


from dotenv import load_dotenv
load_dotenv()


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BUCKET_NAME = "images"
supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        supabase = None
        print("Warning: failed to create Supabase client:", e)

app = FastAPI()


os.makedirs("uploads", exist_ok=True)  


app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY")
ROBOFLOW_WORKSPACE = os.getenv("ROBOFLOW_WORKSPACE")
ROBOFLOW_PROJECT = os.getenv("ROBOFLOW_PROJECT")
ROBOFLOW_VERSION = int(os.getenv("ROBOFLOW_VERSION"))


rf = Roboflow(api_key=ROBOFLOW_API_KEY)
project = rf.workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT)
model = project.version(ROBOFLOW_VERSION).model

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/jpg",
    "image/webp",
}


# @app.post("/predict")
# async def predict(file: UploadFile = File(...)):
#     # Read image bytes
#     image_bytes = await file.read()
    
#     # Save temporary file for Roboflow predict method (if needed)
#     temp_filename = f"uploads/temp_{file.filename}"
#     with open(temp_filename, "wb") as f:
#         f.write(image_bytes)

#     # Roboflow inference
#     try:
#         prediction = model.predict(temp_filename).json()
#     except Exception as e:
#         # Clean up temp file
#         if os.path.exists(temp_filename):
#             os.remove(temp_filename)
#         return {"error": str(e)}

#     # Clean up temp file
#     if os.path.exists(temp_filename):
#         os.remove(temp_filename)

#     return {
#         "prediction": prediction,
#         "filename": file.filename,
#         "message": "Roboflow model inference successful."
#

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    
    image_bytes = await file.read()

    
    original_path = f"uploads/{file.filename}"
    with open(original_path, "wb") as f:
        f.write(image_bytes)

    
    try:
        result = model.predict(original_path).json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
    filtered_preds = [
        pred for pred in result.get("predictions", [])
        if pred.get("confidence", 0) >= 0.60
    ]
    
    img = Image.open(original_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()

    for pred in filtered_preds:
        x, y, w, h = pred["x"], pred["y"], pred["width"], pred["height"]

        
        x1 = x - w/2
        y1 = y - h/2
        x2 = x + w/2
        y2 = y + h/2

        
        draw.rectangle([(x1, y1), (x2, y2)], outline="green", width=3)


        label = f"{pred['class']} ({pred['confidence']:.2f})"

        
        draw.text(
            (x1, y1 - 25),
            label,
            fill="white",
            stroke_width=3,
            stroke_fill="black",
            font=font
        )

    
    annotated_path = f"uploads/annotated_{file.filename}"
    img.save(annotated_path)

    url = f"http://localhost:8000/uploads/annotated_{file.filename}"
    
    return JSONResponse({
        "prediction": filtered_preds,
        "message": "success",
        "annotated_image_url": url
    })

@app.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    note: str = Form(None),
):
    
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    if supabase is None:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    local_path = os.path.join("uploads", f"{timestamp}_{file.filename}")

    with open(local_path, "wb") as f:
        f.write(await file.read())


    storage_path = f"{user_id}/{timestamp}_{file.filename}"

    
    try:
        supabase.storage.from_("images").upload(
            path=storage_path,
            file=local_path  
        )
    except Exception as e:
        
        os.remove(local_path)
        raise HTTPException(status_code=500, detail=f"Supabase upload failed: {e}")

    
    public_url = supabase.storage.from_("images").get_public_url(storage_path)

    
    supabase.table("images").insert({
        "user_id": user_id,
        "filename": storage_path,
        "url": public_url,
        "note": note,
        "uploaded_at": datetime.now().isoformat()
    }).execute()

    
    os.remove(local_path)

    return {
        "message": "Image uploaded successfully",
        "url": public_url,
        "path": storage_path
    }

@app.post("/upload-image-rest")
async def upload_image_rest(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    note: str = Form(None),
):
    
    if file.content_type not in {"image/jpeg", "image/png", "image/jpg", "image/webp"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    contents = await file.read()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    storage_path = f"{user_id}/{timestamp}_{file.filename}"

    
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{storage_path}"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": file.content_type
    }

    response = requests.put(url, headers=headers, data=contents)

    if response.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Supabase upload failed: {response.text}")

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{storage_path}"

    
    # supabase.table("images").insert({
    #     "user_id": user_id,
    #     "filename": storage_path,
    #     "url": public_url,
    #     "note": note,
    #     "uploaded_at": datetime.now().isoformat()
    # }).execute()

    return {
        "message": "Image uploaded successfully",
        "url": public_url,
        "path": storage_path
    }
    
    