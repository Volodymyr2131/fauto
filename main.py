from fastapi import FastAPI, HTTPException, Form, Depends, Cookie, Query, UploadFile, File, WebSocket, WebSocketDisconnect, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, RedirectResponse
from fastapi.requests import Request
from fastapi.security import OAuth2PasswordBearer
import aiosqlite
import asyncio
from typing import Optional
import os
import aiofiles
import bcrypt
from fastapi.staticfiles import StaticFiles
from func import *
from cardata import *
import json
from PIL import Image, UnidentifiedImageError

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
IMAGE_FOLDER = os.path.join(os.getcwd(), "static/Pictures")
app.mount("/avatars", StaticFiles(directory="static/avatars"), name="avatars")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

current_user = None

#Домашня сторінка
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, current_user: Optional[dict] = Depends(get_current_user_optional)):
    top_cars = await get_top_cars()

    user_info = None
    username = None
    email = None
    user_id = None
    avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            username, email, avatar_url_db = user_info
            if avatar_url_db:
                avatar_url = avatar_url_db

    return templates.TemplateResponse("index.html", {
        "request": request,
        "cars": top_cars,
        "user_id": user_id,
        "username": username,
        "email": email,
        "avatar": avatar_url
    })

@app.get("/car/{car_id}", response_class=HTMLResponse)
async def car_detail(request: Request, car_id: int, current_user: Optional[dict] = Depends(get_current_user_optional)):
    user_info = None
    username = None
    email = None
    user_id = None
    avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            username, email, avatar_url_db = user_info
            if avatar_url_db:
                avatar_url = avatar_url_db

    await views(car_id)
    car_info = await AUTHinfo(car_id)

    if not car_info["Is_Checked"]:
        return templates.TemplateResponse("error.html", {"request": request, "message": "Авто не пройшло перевірку."})

    car_vin = car_info["vin"]
    car_info_vin = await VINinfo(car_vin)

    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute("SELECT image_path FROM car_images WHERE car_id = ?", (car_id,)) as image_cursor:
            images = await image_cursor.fetchall()
        async with db.execute("SELECT damage_description, accident_date FROM car_accidents WHERE car_id = ?", (car_id,)) as accidents_cursor:
            accidents = await accidents_cursor.fetchall()

    image_urls = [f"/static/{img[0]}" for img in images]

    user_id_seller = car_info.get("user_id")
    seller_info = await get_user_by_id(user_id_seller)
    seller_avatar_url = await get_avatar_by_user_id(user_id_seller)
    
    is_seller = user_id == user_id_seller

    return templates.TemplateResponse("car.html", {
        "request": request,
        "car": car_info,
        "vin": car_info_vin,
        "image_urls": image_urls,
        "seller_info": seller_info,
        "avatar_url": seller_avatar_url,
        "user_id": user_id,
        "username": username,
        "email": email,
        "car_id": car_id,
        "avatar": avatar_url,
        "is_seller": is_seller,
        "accidents": [{"damage": acc[0], "date": acc[1]} for acc in accidents]
    })

@app.get("/registration", response_class=HTMLResponse)
async def get_registration_page(request: Request):
    return templates.TemplateResponse("registration.html", {"request": request})

@app.post("/registration/")
async def register_user(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), phone: int = Form(...), surname: str = Form(...), name: str = Form(...), lastname:str = Form(...)):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    is_admin = False
    
    async with aiosqlite.connect("FAutoBase.db") as conn:
        cursor = await conn.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = await cursor.fetchone()

        if existing_user:
            error_message = "Ця електронна адреса вже зареєстрована."
            return templates.TemplateResponse("registration.html", {"request": request, "error": error_message})

        await conn.execute("INSERT INTO users (Username, Email, Phone, Password, Surname, Name, Lastname, IsAdmin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                           (username, email, phone, hashed_password, surname, name, lastname, is_admin))
        await conn.commit()

    return RedirectResponse(url="/login?success=true", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse("authorisation.html", {"request": request})

@app.post("/login")
async def login_user(request: Request, email: str = Form(...), password: str = Form(...)):
    async with aiosqlite.connect("FAutoBase.db") as conn:
        cursor = await conn.execute("SELECT id, Password FROM users WHERE Email = ?", (email,))
        user = await cursor.fetchone()
    if user and bcrypt.checkpw(password.encode('utf-8'), user[1].encode('utf-8')):
        token = create_jwt(user_id=user[0], username=email, secret_key=SECRET_KEY)

        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            max_age=60 * 60 * 24,
            samesite="Lax",
            secure=True
        )
        return response
    else:
        error_message = "Invalid email or password."
        return templates.TemplateResponse("authorisation.html", {"request": request, "errors": error_message})

@app.get("/logout")
async def logout_user():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="access_token")
    return response

#Створення оголошення       
@app.get("/add_car", response_class=HTMLResponse)
async def add_car_page(request: Request, current_user: str = Depends(get_current_user)):
    user_info = None
    username = None
    email = None
    user_id = None
    avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            username, email, avatar_url_db = user_info
            if avatar_url_db:
                avatar_url = avatar_url_db
    return templates.TemplateResponse("add_car.html",
                                      {"request": request,
                                       "car_manufacturers": car_manufacturers, 
                                       "car_colors": car_colors,
                                       "color_condition": color_condition, 
                                       "body_condition": body_condition, 
                                       "tech_condition": tech_condition, 
                                       "interior_material": interior_material, 
                                       "body_types": body_types,
                                       "years": years,
                                       "wheel_drive_list": wheel_drive_list,
                                       "engine_volumes": engine_volumes,
                                       "car_generations": car_generations,
                                       "car_facelifts": car_facelifts,
                                       "engine_types": engine_types,
                                       "car_types": car_types,
                                       "transimiton_list": transimiton_list,
                                       "doors": doors,
                                       "user_id": user_id,
                                       "username": username,
                                       "email": email,
                                       "avatar": avatar_url})
@app.post("/create_car")
async def add_car(
                    Type: str = Form(...),
                    Make: str = Form(...), 
                    Model: str = Form(...),
                    Generation: int = Form(...),
                    Facelift: int = Form(...),
                    Year: int = Form(...),
                    Description: str = Form(...),
                    VIN: str = Form(...),
                    Price: float = Form(...),
                    Color: str = Form(...),
                    ColorState: str = Form(...),
                    BodyType: str = Form(...),
                    Doors: str = Form(...),
                    BodyState: str = Form(...),
                    Transmition: str = Form(...),
                    WheelDrive: str = Form(...),
                    EngineType: str = Form(...),
                    EngineVolume: float = Form(...),
                    Mileage: str = Form(...),
                    Interior: str = Form(...),
                    TechState: str = Form(...),
                    images: list[UploadFile] = File(...),
                    current_user: dict = Depends(get_current_user)):
    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute('SELECT 1 FROM cars WHERE VIN = ?', (VIN,)) as cursor:
            vin = await cursor.fetchone()
            if vin:
                raise HTTPException(status_code=400, detail="VIN вже використовується.")
        user_id = current_user["user_id"]
        await db.execute('''INSERT INTO cars (Make,
                    Type,
                    Model,
                    Generation, 
                    Facelift, 
                    Year, 
                    Description, 
                    VIN, 
                    Price, 
                    Color,
                    ColorState, 
                    BodyType, 
                    Doors,
                    BodyState, 
                    WheelDrive, 
                    EngineDisplacement, 
                    EngineType,
                    TransmitionType,
                    Mileage, 
                    Interior, 
                    TechState, 
                    Is_Checked, 
                    user_id) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                    Make,
                    Type, 
                    Model, 
                    Generation, 
                    Facelift, 
                    Year, 
                    Description, 
                    VIN, 
                    Price, 
                    Color, 
                    ColorState, 
                    BodyType,
                    Doors, 
                    BodyState, 
                    WheelDrive, 
                    EngineVolume, 
                    EngineType,
                    Transmition,
                    Mileage, 
                    Interior, 
                    TechState, 
                    False, 
                    user_id))
        await db.commit()

        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cursor:
            car_id = await cursor.fetchone()
            car_id = car_id[0]

        car_image_folder = os.path.join(IMAGE_FOLDER, str(car_id))
        await create_directory(car_image_folder)

        for idx, image in enumerate(images):
            image_filename = f"{idx + 1}.png"
            image_path = os.path.join(car_image_folder, image_filename)

            async with aiofiles.open(image_path, 'wb') as out_file:
                content = await image.read()
                await out_file.write(content)

            relative_image_path = os.path.relpath(image_path, start="static")
            await db.execute(
                "INSERT INTO car_images (car_id, image_path) VALUES (?, ?)",
                (car_id, relative_image_path)
            )
        
        await db.commit()

    return {"message": "Succesfully", "car_id": car_id}

@app.get("/admin")
async def admin_panel(request: Request, current_user: dict = Depends(require_admin)):
    if not current_user:
        raise HTTPException(status_code=403, detail="Admins only")
    
    try:
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT * FROM cars WHERE Is_Checked = ?", (False,)) as cursor:
                cars = await cursor.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    ads = []
    for car in cars:
        vin_info = await VINinfo(car[8])
        orig_info = await AUTHinfo(car[0])
        car_id = car[0]

        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT image_path FROM car_images WHERE car_id = ?", (car_id,)) as image_cursor:
                images = await image_cursor.fetchall()

        image_urls = [f"/static/{img[0]}" for img in images]

        ads.append({
            "id": car_id,
            "orig_info": orig_info,
            "vin_info": vin_info,
            "image_urls": image_urls
        })

    return templates.TemplateResponse("admin_panel.html", {"request": request, "ads": ads})

@app.post("/approve/{ad_id}")
async def approve_ad(ad_id: int, current_user: dict = Depends(require_admin)):
    if not current_user:
        raise HTTPException(status_code=403, detail="Admins only")
    
    async with aiosqlite.connect("FAutoBase.db") as db:
        await db.execute("UPDATE cars SET Is_Checked = ? WHERE id = ?", (True, ad_id))
        await db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/reject/{ad_id}")
async def reject_ad(ad_id: int, current_user: dict = Depends(require_admin)):
    if not current_user:
        raise HTTPException(status_code=403, detail="Admins only")
    
    async with aiosqlite.connect("FAutoBase.db") as db:
        result = await db.execute("DELETE FROM cars WHERE id = ?", (ad_id,))
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Advertisement not found")
    
    return RedirectResponse(url="/admin", status_code=303)

class ConnectionManager:
    def __init__(self):
        self.chat_connections = {}

    async def connect(self, websocket: WebSocket, chat_id: int):
        await websocket.accept()
        if chat_id not in self.chat_connections:
            self.chat_connections[chat_id] = []
        self.chat_connections[chat_id].append(websocket)

    async def disconnect(self, websocket: WebSocket, chat_id: int):
        if chat_id in self.chat_connections:
            self.chat_connections[chat_id].remove(websocket)
            if not self.chat_connections[chat_id]:
                del self.chat_connections[chat_id]

    async def broadcast(self, chat_id: int, message: dict):
        if chat_id in self.chat_connections:
            for connection in self.chat_connections[chat_id]:
                await connection.send_text(json.dumps(message))

manager = ConnectionManager()

@app.get("/chats", response_class=HTMLResponse)
async def list_and_view_chat(
    request: Request, 
    chat_id: Optional[int] = None, 
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    user_info = None
    username = None
    email = None
    user_id = None
    avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            username, email, avatar_url_db = user_info
            if avatar_url_db:
                avatar_url = avatar_url_db

    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute("""SELECT c.id, u.username AS participant, c.car_id FROM chats c JOIN users u ON (u.id = c.participant1_id OR u.id = c.participant2_id) WHERE (c.participant1_id = ? OR c.participant2_id = ?) AND u.id != ?""", (user_id, user_id, user_id)) as cursor:
            chats = await cursor.fetchall()

        chat_list = []
        for chat in chats:
            ad_id = chat[2]
            async with db.execute("""SELECT make, model, year, description FROM cars WHERE id = ?""", (ad_id,)) as car_cursor:
                ad_info = await car_cursor.fetchone()

            async with db.execute(
                """SELECT image_path 
                   FROM car_images 
                   WHERE car_id = ? 
                   ORDER BY id DESC LIMIT 1""",
                (ad_id,)
            ) as image_cursor:
                ad_image = await image_cursor.fetchone()

            chat_list.append({
                "id": chat[0],
                "participant": chat[1],
                "ad": {
                    "make": ad_info[0] if ad_info else None,
                    "model": ad_info[1] if ad_info else None,
                    "year": ad_info[2] if ad_info else None,
                    "description": ad_info[3] if ad_info else None,
                    "image_url": f"/static/{ad_image[0]}" if ad_image else None,
                    "car_id": ad_id
                }
            })

    messages_list = []
    if chat_id:
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute(
                """SELECT u.username, m.message, m.timestamp 
                   FROM chat_messages m
                   JOIN users u ON m.sender_id = u.id
                   WHERE m.chat_id = ? 
                   ORDER BY m.timestamp ASC""",
                (chat_id,)
            ) as cursor:
                messages = await cursor.fetchall()

            messages_list = [{"username": msg[0], "message": msg[1], "timestamp": msg[2]} for msg in messages]

    return templates.TemplateResponse("chat_list_and_chat.html", {
        "request": request,
        "chats": chat_list,
        "messages": messages_list,
        "chat_id": chat_id,
        "user_id": user_id,
        "username": username,
        "email": email,
        "avatar": avatar_url
    })


@app.post("/chats/get_or_create_by_ad")
async def get_or_create_chat_by_car(
    car_id: int = Form(...), current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute(
            "SELECT user_id FROM cars WHERE id = ?", (car_id,)
        ) as cursor:
            car = await cursor.fetchone()

        if not car:
            raise HTTPException(status_code=404, detail="Car not found")

        owner_id = car[0]

        if owner_id == user_id:
            raise HTTPException(status_code=400, detail="You cannot start a chat about your own car.")

        async with db.execute(
            "SELECT id FROM chats WHERE car_id = ? AND ((participant1_id = ? AND participant2_id = ?) OR (participant1_id = ? AND participant2_id = ?))",
            (car_id, user_id, owner_id, owner_id, user_id)
        ) as cursor:
            chat = await cursor.fetchone()

        if chat:
            chat_id = chat[0]
        else:
            await db.execute(
                "INSERT INTO chats (participant1_id, participant2_id, car_id) VALUES (?, ?, ?)",
                (user_id, owner_id, car_id)
            )
            await db.commit()

            async with db.execute("SELECT last_insert_rowid()") as cursor:
                chat_id = (await cursor.fetchone())[0]

        return RedirectResponse(url=f"/chats?chat_id={chat_id}", status_code=303)

@app.websocket("/ws/chat/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]

    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute(
            "SELECT id FROM chats WHERE id = ? AND (participant1_id = ? OR participant2_id = ?)",
            (chat_id, user_id, user_id)
        ) as cursor:
            chat = await cursor.fetchone()

    if not chat:
        await websocket.close()
        return

    await manager.connect(websocket, chat_id)

    try:
        async with aiosqlite.connect("FAutoBase.db") as db:
            while True:
                data = await websocket.receive_text()

                await db.execute(
                    "INSERT INTO chat_messages (chat_id, sender_id, message, timestamp) VALUES (?, ?, ?, datetime('now'))",
                    (chat_id, user_id, data)
                )
                await db.commit()

                async with db.execute(
                    "SELECT username FROM users WHERE id = ?", (user_id,)
                ) as cursor:
                    sender_username = (await cursor.fetchone())[0]

                message_to_send = {
                    "username": sender_username,
                    "message": data,
                    "timestamp": "now"
                }

                await manager.broadcast(chat_id, message_to_send)
    except WebSocketDisconnect:
        await manager.disconnect(websocket, chat_id)

@app.get("/vin_check", response_class=HTMLResponse)
async def vin_check(request: Request, vin: str = Query(None, min_length=17, max_length=17, pattern="^[A-HJ-NPR-Z0-9]+$"), current_user: Optional[dict] = Depends(get_current_user_optional)):
    vin_info = None
    error = None

    user_info = None
    username = None
    email = None
    user_id = None
    avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            username, email, avatar_url_db = user_info
            if avatar_url_db:
                avatar_url = avatar_url_db

    if vin:
        try:
            vin_info = await VINinfo(vin)
        except Exception as e:
            error = f"Не вдалося отримати інформацію для VIN {vin}: {str(e)}"

    return templates.TemplateResponse("vin_check.html", {"request": request, "vin_info": vin_info, "error": error, "user_id": user_id, "username": username, "email": email, "avatar": avatar_url})

@app.post("/admin/add_car_model")
async def add_car_model(make: str = Form(...), model: str = Form(...), current_user: dict = Depends(require_admin)):
    if not current_user:
        raise HTTPException(status_code=403, detail="Admins only")
    
    try:
        with open("car_models.json", "r", encoding="utf-8") as file:
            car_data = json.load(file)

        if make in car_data:
            if model not in car_data[make]:
                car_data[make].append(model)
            else:
                raise HTTPException(status_code=400, detail="Ця модель вже існує.")
        else:
            car_data[make] = [model]

        with open("car_models.json", "w", encoding="utf-8") as file:
            json.dump(car_data, file, ensure_ascii=False, indent=4)

        return RedirectResponse(url="/admin", status_code=303)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка при оновленні JSON: {str(e)}")

@app.post("/admin/delete_car_model")
async def delete_car_model( make: str = Form(...), model: str = Form(None), current_user: dict = Depends(require_admin)):
    if not current_user:
        raise HTTPException(status_code=403, detail="Admins only")
    
    try:
        with open("car_models.json", "r", encoding="utf-8") as file:
            car_data = json.load(file)

        if make not in car_data:
            raise HTTPException(status_code=404, detail="Марка не знайдена.")

        if model:
            if model in car_data[make]:
                car_data[make].remove(model)
                if not car_data[make]:
                    del car_data[make]
            else:
                raise HTTPException(status_code=404, detail="Модель не знайдена.")
        else:
            del car_data[make]

        with open("car_models.json", "w", encoding="utf-8") as file:
            json.dump(car_data, file, ensure_ascii=False, indent=4)

        return RedirectResponse(url="/admin", status_code=303)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка при оновленні JSON: {str(e)}")

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, type: Optional[str] = Query(None), make: Optional[str] = Query(None), model: Optional[str] = Query(None), year_min: Optional[str] = Query(None), year_max: Optional[str] = Query(None), price_min: Optional[str] = Query(None), price_max: Optional[str] = Query(None), mileage_max: Optional[str] = Query(None), current_user: Optional[dict] = Depends(get_current_user_optional)):
    def none_fix(value, to_type):
        try:
            return to_type(value)
        except (ValueError, TypeError):
            return None
        
    year_min = none_fix(year_min, int)
    year_max = none_fix(year_max, int)
    price_min = none_fix(price_min, float)
    price_max = none_fix(price_max, float)
    mileage_max = none_fix(mileage_max, float)

    query = "SELECT id FROM cars WHERE 1=1 and Is_Checked = 1"
    params = []
    if type:
        query += " AND Type = ?"
        params.append(type)
    if make:
        query += " AND Make = ?"
        params.append(make)
    if model:
        query += " AND Model = ?"
        params.append(model)
    if year_min is not None:
        query += " AND Year >= ?"
        params.append(year_min)
    if year_max is not None:
        query += " AND Year <= ?"
        params.append(year_max)
    if price_min is not None:
        query += " AND Price >= ?"
        params.append(price_min)
    if price_max is not None:
        query += " AND Price <= ?"
        params.append(price_max)
    if mileage_max is not None:
        query += " AND Mileage <= ?"
        params.append(mileage_max)

    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute(query, params) as cursor:
            car_ids = await cursor.fetchall()

    cars = []
    for i in car_ids:
        car_id = i[0]
        car_info = await AUTHinfo(car_id)
        if isinstance(car_info, dict):
            car_info["id"] = car_id
            cars.append(car_info)

    user_info = None
    username = None
    email = None
    user_id = None
    avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (user_id,)) as cursor:
                user_info = await cursor.fetchone()
        if user_info:
            username, email, avatar_url_db = user_info
            if avatar_url_db:
                avatar_url = avatar_url_db
    return templates.TemplateResponse("search.html",{"request": request, "car_manufacturers": car_manufacturers, "car_colors": car_colors, "color_condition": color_condition, "body_condition": body_condition, "tech_condition": tech_condition, "interior_material": interior_material, "body_types": body_types, "years": years, "wheel_drive_list": wheel_drive_list, "engine_volumes": engine_volumes, "car_generations": car_generations, "car_facelifts": car_facelifts, "engine_types": engine_types, "car_types": car_types, "transimiton_list": transimiton_list, "doors": doors, "results": cars, "user_id": user_id,"username": username, "email": email, "avatar": avatar_url})

@app.get("/profile/{user_id}", response_class=HTMLResponse)
async def get_profile_page(request: Request, user_id: int, current_user: dict = Depends(get_current_user), admin_user: Optional[dict] = Depends(require_admin)):
    if admin_user:
        pass
    elif current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    async with aiosqlite.connect("FAutoBase.db") as conn:

        async with conn.execute("SELECT username, email, phone, avatar, surname, name, lastname, avatar FROM users WHERE id = ?", (user_id,)) as cursor:
            user_data = await cursor.fetchone()

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        surname = user_data[4]
        name = user_data[5]
        lastname = user_data[6]
        fullname = f"{surname} {name} {lastname}" if surname and name and lastname else "Невідоме ПІБ"

        async with conn.execute("""SELECT id, make, model, year, price, mileage FROM cars WHERE user_id = ?""", (user_id,)) as cursor:
            user_ads = await cursor.fetchall()

        ads_with_images = []
        for ad in user_ads:
            car_id = ad[0]
            async with conn.execute("""SELECT image_path FROM car_images WHERE car_id = ? ORDER BY id DESC LIMIT 1""", (car_id,)) as image_cursor:
                last_image = await image_cursor.fetchone()
                image_url = f"/static/{last_image[0]}" if last_image else None

            ads_with_images.append({
                "id": car_id,
                "make": ad[1],
                "model": ad[2],
                "year": ad[3],
                "price": ad[4],
                "mileage": ad[5],
                "image_url": image_url
            })

    user_info = None
    current_avatar_url = "/static/default-avatar.jpg"
    if current_user and current_user.get("user_id"):
        current_user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (current_user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            username, email, current_avatar_url_db = user_info
            if current_avatar_url_db:
                current_avatar_url = current_avatar_url_db

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": {
            "id": user_id,
            "username": user_data[0],
            "email": user_data[1],
            "phone": user_data[2],
            "avatar": user_data[7],
            "surname": user_data[4],
            "name": user_data[5],
            "lastname": user_data[6],
            "fullname": fullname
        },
        "ads": ads_with_images,
        "user_id": current_user_id,
        "username": username,
        "email": email,
        "avatar": current_avatar_url,
        "is_admin": admin_user
    })

@app.post("/profile/{user_id}")
async def update_profile(
    request: Request,
    user_id: int,
    username: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    surname: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    lastname: Optional[str] = Form(None),
    avatar: UploadFile = File(None),
    current_user: dict = Depends(get_current_user),
    admin_user: Optional[dict] = Depends(require_admin),
):
    if not admin_user and current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    async with aiosqlite.connect("FAutoBase.db") as conn:
        async with conn.execute(
            "SELECT username, email, phone FROM users WHERE id = ?",
            (user_id,),
        ) as cursor:
            current_data = await cursor.fetchone()
            if not current_data:
                raise HTTPException(status_code=404, detail="User not found")

        current_username, current_email, current_phone = current_data

        if email != current_email:
            async with conn.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?",
                (email, user_id),
            ) as cursor:
                existing_user = await cursor.fetchone()
                if existing_user:
                    raise HTTPException(status_code=400, detail="Email already taken")

        if phone != current_phone:
            async with conn.execute(
                "SELECT id FROM users WHERE phone = ? AND id != ?",
                (phone, user_id),
            ) as cursor:
                existing_user_phone = await cursor.fetchone()
                if existing_user_phone:
                    raise HTTPException(status_code=400, detail="Phone number already taken")

        if username != current_username:
            async with conn.execute(
                "SELECT id FROM users WHERE username = ? AND id != ?",
                (username, user_id),
            ) as cursor:
                existing_user_name = await cursor.fetchone()
                if existing_user_name:
                    raise HTTPException(status_code=400, detail="Username already taken")

    avatar_url = None
    if avatar and avatar.filename:
        if avatar.content_type.startswith("image/"):
            try:
                avatar_folder = "static/avatars"
                avatar_url = os.path.join(avatar_folder, f"{user_id}.jpg")
    
                image = Image.open(avatar.file)
    
                size = min(image.size)
                left = (image.width - size) / 2
                top = (image.height - size) / 2
                right = (image.width + size) / 2
                bottom = (image.height + size) / 2
    
                image = image.crop((left, top, right, bottom))
                image = image.resize((512, 512))
                image.save(avatar_url, "JPEG")
            except UnidentifiedImageError:
                raise HTTPException(status_code=400, detail="Uploaded file is not a valid image")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
    else:
        avatar_url = None

    async with aiosqlite.connect("FAutoBase.db") as conn:
        if admin_user:
            if avatar_url:
                await conn.execute(
                    """UPDATE users 
                       SET username = ?, email = ?, phone = ?, avatar = ?, surname = ?, name = ?, lastname = ? 
                       WHERE id = ?""",
                    (username, email, phone, avatar_url, surname, name, lastname, user_id)
                )
            else:
                await conn.execute(
                    """UPDATE users 
                       SET username = ?, email = ?, phone = ?, surname = ?, name = ?, lastname = ? 
                       WHERE id = ?""",
                    (username, email, phone, surname, name, lastname, user_id)
                )
        else:
            if avatar_url:
                await conn.execute(
                    "UPDATE users SET username = ?, email = ?, phone = ?, avatar = ? WHERE id = ?",
                    (username, email, phone, avatar_url, user_id)
                )
            else:
                await conn.execute(
                    "UPDATE users SET username = ?, email = ?, phone = ? WHERE id = ?",
                    (username, email, phone, user_id)
                )
        await conn.commit()

    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)


@app.get("/car/edit/{car_id}", response_class=HTMLResponse)
async def get_edit_car_page(request: Request, car_id: int, current_user: dict = Depends(get_current_user)):
    user_info = None
    username = None
    email = None
    user_id = None
    avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (user_id,)) as cursor:
                user_info = await cursor.fetchone()
        if user_info:
            username, email, avatar_url_db = user_info
            if avatar_url_db:
                avatar_url = avatar_url_db
    
    car_info = await AUTHinfo(car_id)
    
    if car_info["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return templates.TemplateResponse("edit_car.html", {
        "request": request,
        "car_id": car_id,
        "car_details": car_info, "user_id": user_id,"username": username, "email": email, "avatar": avatar_url
    })

@app.post("/car/edit/{car_id}")
async def update_car(
    car_id: int,
    description: str = Form(...),
    price: float = Form(...),
    mileage: str = Form(...),
    current_user: dict = Depends(get_current_user)):
    car_info = await AUTHinfo(car_id)
    
    if car_info["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    async with aiosqlite.connect("FAutoBase.db") as conn:
        await conn.execute('''UPDATE cars SET Description = ?, Price = ?, Mileage = ?, Is_Checked = ? WHERE id = ?''',(description, price, mileage, 0, car_id))
        await conn.commit()

    return RedirectResponse(url=f"/profile/{current_user['user_id']}", status_code=303)

@app.get("/car/delete/{car_id}")
async def delete_car(car_id: int, current_user: dict = Depends(get_current_user)):
    car_info = await AUTHinfo(car_id)

    if car_info["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    async with aiosqlite.connect("FAutoBase.db") as conn:
        await conn.execute("DELETE FROM cars WHERE id = ?", (car_id,))
        await conn.commit()

    return RedirectResponse(url=f"/profile/{current_user['user_id']}", status_code=303)

@app.get("/support/request/new", response_class=HTMLResponse)
async def new_request_page(request: Request, current_user: dict = Depends(get_current_user)):
    user_info = None
    current_username = None
    current_email = None
    current_user_id = None
    current_avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        current_user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (current_user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            cuurent_username, current_email, avatar_url_db = user_info
            if avatar_url_db:
                current_avatar_url = avatar_url_db
    return templates.TemplateResponse("create_request.html", {"request": request, "current_user_id": current_user_id, "current_username": current_username, "current_email": current_email, "current_avatar_url": current_avatar_url})

@app.post("/support/request")
async def create_support_request(subject: str = Form(...), message: str = Form(...), email: str = Form(...), current_user: dict = Depends(get_current_user)):
    try:
        async with aiosqlite.connect("FAutoBase.db") as db:
            await db.execute("""INSERT INTO support_requests (user_id, email, subject, message) VALUES (?, ?, ?, ?)""", (current_user["user_id"], email, subject, message))
            await db.commit()

        return RedirectResponse(url="/support/my-requests", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")

@app.get("/support/requests", response_class=HTMLResponse)
async def admin_requests_page(request: Request, admin_user: dict = Depends(require_admin), current_user: dict = Depends(get_current_user)):
    if not admin_user:
        raise HTTPException(status_code=403, detail="Access denied")
    
    user_info = None
    current_username = None
    current_email = None
    current_user_id = None
    current_avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        current_user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (current_user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            cuurent_username, current_email, avatar_url_db = user_info
            if avatar_url_db:
                current_avatar_url = avatar_url_db
    
    try:
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT * FROM support_requests WHERE status != 'closed'") as cursor:
                requests = await cursor.fetchall()

        support_requests = []
        for req in requests:
            request_id, user_id, email, subject, message, created_at, status = req
            support_requests.append({
                "request_id": request_id,
                "subject": subject,
                "email": email,
                "status": status,
                "link": f"/support/request/{request_id}"
            })

        return templates.TemplateResponse("admin_requests.html", {"request": request, "requests": support_requests, "current_user_id": current_user_id, "current_username": current_username, "current_email": current_email, "current_avatar_url": current_avatar_url,})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")

@app.get("/support/request/{request_id}", response_class=HTMLResponse)
async def request_detail_page(request: Request, request_id: int, current_user: dict = Depends(get_current_user)):
    user_info = None
    current_username = None
    current_email = None
    current_user_id = None
    current_avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        current_user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (current_user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            cuurent_username, current_email, current_avatar_url_db = user_info
            if current_avatar_url_db:
                current_avatar_url = current_avatar_url_db
    try:
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT * FROM support_requests WHERE id = ?", (request_id,)) as cursor:
                request_row = await cursor.fetchone()

            if not request_row:
                raise HTTPException(status_code=404, detail="Request not found")

            request_id, user_id, email, subject, first_message, created_at, status = request_row

            async with db.execute("SELECT * FROM support_messages WHERE request_id = ?", (request_id,)) as cursor:
                messages = await cursor.fetchall()

        messages_list = []
        for msg in messages:
            message_id, request_id, sender_id, message, created_at = msg
            sender = await get_user_by_id(sender_id)
            messages_list.append({
                "sender_id": sender_id,
                "message": message,
                "created_at": created_at,
                "sender": sender["Username"]
            })
        return templates.TemplateResponse("request_detail.html", {
            "request_t": {"subject": subject, "message": first_message, "email": email, "status": status},
            "messages": messages_list,
            "request_id": request_id,
            "request": request, "current_user_id": current_user_id, "current_username": current_username, "current_email": current_email, "current_avatar_url": current_avatar_url,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")

@app.post("/support/reply/{request_id}")
async def reply_to_support_request(request_id: int, reply_message: str = Form(...), current_user: dict = Depends(get_current_user),):

    user_info = None
    username = None
    email = None
    user_id = None
    avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            username, email, avatar_url_db = user_info
            if avatar_url_db:
                avatar_url = avatar_url_db
    try:
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT * FROM support_requests WHERE id = ?", (request_id,)) as cursor:
                request_data = await cursor.fetchone()
                if not request_data:
                    raise HTTPException(status_code=404, detail="Support request not found")

            async with db.execute(
                "INSERT INTO support_messages (request_id, sender_id, message) VALUES (?, ?, ?)",
                (request_id, user_id, reply_message)
            ):
                await db.commit()

        return RedirectResponse(url=f"/support/request/{request_id}", status_code=303)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while replying: {str(e)}")

@app.get("/support/my-requests", response_class=HTMLResponse)
async def get_user_requests(request: Request, current_user: dict = Depends(get_current_user)):
    user_info = None
    current_username = None
    current_email = None
    current_user_id = None
    current_avatar_url = "/static/default-avatar.jpg"

    if current_user and current_user.get("user_id"):
        current_user_id = current_user["user_id"]
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT Username, Email, avatar FROM users WHERE id = ?", (current_user_id,)) as cursor:
                user_info = await cursor.fetchone()

        if user_info:
            cuurent_username, current_email, avatar_url_db = user_info
            if avatar_url_db:
                current_avatar_url = avatar_url_db
    
    try:
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute(
                "SELECT id, subject, status FROM support_requests WHERE user_id = ?",
                (current_user["user_id"],)
            ) as cursor:
                requests = await cursor.fetchall()

        user_requests = [
            {"id": req[0], "subject": req[1], "status": req[2]} for req in requests
        ]

        return templates.TemplateResponse(
            "user_requests.html",
            {"request": request, "user_requests": user_requests, "current_user": current_user, "current_user_id": current_user_id, "current_username": current_username, "current_email": current_email, "current_avatar_url": current_avatar_url},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user requests: {str(e)}")

@app.post("/support/close_request/{request_id}")
async def close_request(request_id: int, current_user: dict = Depends(get_current_user), admin_user: dict = Depends(require_admin)):
    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute("SELECT user_id FROM support_requests WHERE id = ?", (request_id,)) as cursor:
            request = await cursor.fetchone()
        
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        sender_id = request[0]

    if current_user["user_id"] != sender_id:
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT IsAdmin FROM users WHERE id = ?", (current_user["user_id"],)) as cursor:
                user_data = await cursor.fetchone()
            
            if user_data is None or user_data[0] != 1:
                raise HTTPException(status_code=403, detail="Not authorized to close this request")

    async with aiosqlite.connect("FAutoBase.db") as db:
        await db.execute("UPDATE support_requests SET status = ? WHERE id = ?", ("closed", request_id))
        await db.commit()
    if admin_user:
        return RedirectResponse(url="/support/requests", status_code=302)
    else:
        return RedirectResponse(url="/support/my-requests", status_code=302)

@app.get("/add-accident/{car_id}", response_class=HTMLResponse)
async def add_accident_form(request: Request, car_id: int, admin_user: Optional[dict] = Depends(require_admin)):
    if not admin_user:
        raise HTTPException(status_code=403, detail="Access denied")
    return templates.TemplateResponse("add_accident.html", {"request": request, "damage": damage, "car_id": car_id})

@app.post("/add-accident/{car_id}")
async def add_accident(car_id: int, damage: str = Form(...), date: str = Form(None), admin_user: Optional[dict] = Depends(require_admin)):
    if not admin_user:
        raise HTTPException(status_code=403, detail="Access denied")
    async with aiosqlite.connect("FAutoBase.db") as db:
        await db.execute('''INSERT INTO car_accidents (car_id, damage_description, accident_date) VALUES (?, ?, ?)''', (car_id, damage, date))
        await db.commit()

    return RedirectResponse(url=f"/car/{car_id}", status_code=302)

@app.get("/delete_accident/{car_id}")
async def delete_accident(car_id: int, current_user: dict = Depends(get_current_user), admin_user: Optional[dict] = Depends(require_admin)):
    if not admin_user:
        raise HTTPException(status_code=403, detail="Access denied")
    async with aiosqlite.connect("FAutoBase.db") as db:
        await db.execute("DELETE FROM car_accidents WHERE id = ?", (car_id,))
        await db.commit()

    return RedirectResponse(url=f"/car/{car_id}", status_code=302)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)