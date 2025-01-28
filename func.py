import aiosqlite
import aiohttp
import asyncio
from googletrans import Translator
from fastapi import HTTPException, Cookie
from fastapi.responses import RedirectResponse, RedirectResponse
import aiosqlite
import asyncio
from typing import Optional
from fastapi.staticfiles import StaticFiles
from func import *
from cardata import *
import jwt
import time
import os

SECRET_KEY = "SECRET_KEY"

def create_jwt(user_id: int, username: str, secret_key: str, expiration: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": time.time() + expiration,
    }
    encoded_jwt = jwt.encode(payload, secret_key, algorithm="HS256", headers=header)
    return encoded_jwt

def get_current_user(access_token: Optional[str] = Cookie(None)) -> dict:
    if not access_token:
        response = RedirectResponse(url="/login")
        response.status_code = 307
        raise HTTPException(status_code=307, detail="Redirect to login", headers={"Location": "/login"})
    try:
        if isinstance(access_token, bytes):
            access_token = access_token.decode('utf-8')

        payload = jwt.decode(access_token, SECRET_KEY, algorithms=["HS256"])
        return {
            "user_id": payload.get("user_id"),
            "username": payload.get("username"),
        }
    except jwt.ExpiredSignatureError:
        response = RedirectResponse(url="/login")
        response.status_code = 307
        raise HTTPException(status_code=307, detail="Redirect to login", headers={"Location": "/login"})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user_optional(access_token: Optional[str] = Cookie(None)) -> Optional[dict]:
    if not access_token:
        return None
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        username = payload.get("username")

        if user_id is None or username is None:
            print("Token has invalid data.")
            return None
        return {"user_id": user_id, "username": username}
    except jwt.ExpiredSignatureError:
        print("Token has expired.")
        return None
    except jwt.InvalidTokenError as e:
        print(f"Invalid token error: {e}")
        return None


#Інформація про користувача
async def get_user_by_id(user_id: int) -> dict:
    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                user_data = {
                    "id": row[0],
                    "Username": row[1],
                    "Email": row[2],
                    "Phone": row[3],
                    "Password": row[4],
                    "Surname": row[5],
                    "Name": row[6],
                    "Lastname": row[7],
                    "IsAdmin": row[8],
                }
                return user_data
    return None

#Перегляди
async def views(car_id: int):
    async with aiosqlite.connect('FAutoBase.db') as db:
        await db.execute('UPDATE cars SET Views = Views + 1 WHERE id = ?', (car_id,))
        await db.commit()

async def get_all_cars():
    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute('''
            SELECT c.id, c.make, c.model, c.year, c.price, c.mileage, ci.image_path
            FROM cars c
            LEFT JOIN car_images ci ON c.id = ci.car_id
            WHERE ci.id = (SELECT MAX(id) FROM car_images WHERE car_id = c.id)
        ''') as cursor:
            cars = await cursor.fetchall()

    car_list = []
    for car in cars:
        car_info = {
            "id": car[0],
            "make": car[1],
            "model": car[2],
            "year": car[3],
            "price": car[4],
            "mileage": car[5],
            "image_path": f"/static/{car[6]}" if car[6] else None
        }
        car_list.append(car_info)
    return car_list

async def VINinfo(vin):
    url = f'https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json'
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()

                make = None 
                model = None
                year = None
                country = None 
                vehicle_type = None
                engine_displacement = None
                transmition_type = None
                body_type = None
                fuel_type = None
                wheel_drive = None

                for item in data['Results']:
                    if item['Variable'] == 'Make':
                        make = item['Value']
                    elif item['Variable'] == 'Model':
                        model = item['Value']
                    elif item['Variable'] == 'Model Year':
                        year = item['Value']
                    elif item['Variable'] == 'Plant Country':
                        country = item['Value']
                    elif item['Variable'] == 'Vehicle Type':
                        vehicle_type = item['Value']
                    elif item['Variable'] == 'Displacement (L)':
                        engine_displacement = item['Value']
                    elif item['Variable'] == 'Transmission Style':
                        transmition_type = item['Value']
                    elif item['Variable'] == 'Body Class':
                        body_type = item['Value']
                    elif item['Variable'] == 'Doors':
                        doors = item['Value']
                    elif item['Variable'] == 'Fuel Type - Primary':
                        fuel_type = item['Value']
                    elif item['Variable'] == 'Drive Type':
                        wheel_drive = item['Value']

                translator = Translator()

                if country:
                    if country != "UNITED STATES (USA)":
                        country_uk = translator.translate(country, dest='uk').text
                    elif country == "UNITED STATES (USA)":
                        country_uk = "США"
                else:
                    country_uk = None

                if vehicle_type:
                    vehicle_type_uk = translator.translate(vehicle_type, dest='uk').text
                else:
                    vehicle_type_uk = None
                
                if transmition_type:
                    if transmition_type == "Automatic":
                        transmition_type_uk = "Автоматична"
                    elif transmition_type == "Manual/Standard":
                        transmition_type_uk = "Механічна/Ручна"
                    else:
                        transmition_type_uk = None
                else:
                    transmition_type_uk = None

                if body_type:
                    if body_type == "Convertible/Cabriolet":
                        body_type_uk = "Кабріолет"
                    elif body_type == "Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)":
                        body_type_uk = "Позашляховик/кросовер"
                    elif body_type == "Sedan/Saloon":
                        body_type_uk = "Седан"
                    else:
                        body_type_uk = translator.translate(body_type, dest='uk').text
                else:
                    body_type_uk = None

                if make:
                    make_t = make.title()
                else:
                    make_t = None

                if fuel_type:
                    fuel_type_uk = translator.translate(fuel_type, dest="uk").text
                else:
                    fuel_type_uk = None

                if wheel_drive:
                    if wheel_drive == "4WD/4-Wheel Drive/4x4":
                        wheel_drive_uk = "Повний (4WD)"
                    elif wheel_drive == "AWD/All-Wheel Drive":
                        wheel_drive_uk = "Повний (AWD)"
                    elif wheel_drive == "FWD/Front-Wheel Drive":
                        wheel_drive_uk = "Передній (FWD)"
                    elif wheel_drive == "RWD/Rear-Wheel Drive":
                        wheel_drive_uk = "Задній (RWD)"
                    else:
                        wheel_drive_uk = wheel_drive
                else:
                    wheel_drive_uk = None
                return {
                    "Тип автомобіля": vehicle_type_uk,
                    "Виробник": make_t,
                    "Модель": model,
                    "Рік виробництва": year,
                    "Країна виробництва": country_uk,
                    "Тип кузову": body_type_uk,
                    "Кількість дверей": doors,
                    "Привід": wheel_drive_uk,
                    "Об'єм двигуна (Л)": engine_displacement,
                    "Тип палива": fuel_type_uk,
                    "Тип трансмісії": transmition_type_uk
                }
            else:
                raise Exception(f"Помилка: {response.status}")

async def AUTHinfo(car_id):
    async with aiosqlite.connect('FAutoBase.db') as db:
        async with db.execute('SELECT * FROM cars WHERE id = ?', (car_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                type = row[1]
                make = row[2]
                model = row[3]
                generation = row[4]
                facelift = row[5]
                year = row[6]
                description = row[7]
                vin = row[8]
                price = row[9]
                color = row[10]
                color_state = row[11]
                body_type = row[12]
                doors = row[13]
                body_state = row[14]
                wheel_drive = row[15]
                engine_displacement = row[16]
                engine_type = row[17]
                transmition_type = row[18]
                mileage = row[19]
                interior = row[20]
                techstate = row[21]
                views = row[22]
                Is_Checked = row[23]
                user_id = row[24]

                # Получение последнего изображения
                async with db.execute(
                    "SELECT image_path FROM car_images WHERE car_id = ? ORDER BY id DESC LIMIT 1", 
                    (car_id,)
                ) as image_cursor:
                    last_image = await image_cursor.fetchone()
                    image_url = f"/static/{last_image[0]}" if last_image else None

                return {
                    "car_id": car_id, 
                    "type": type, 
                    "make": make, 
                    "model": model, 
                    "generation": generation, 
                    "facelift": facelift, 
                    "year": year, 
                    "description": description, 
                    "vin": vin, 
                    "price": price, 
                    "color": color, 
                    "color_state": color_state, 
                    "body_type": body_type, 
                    "doors": doors, 
                    "body_state": body_state, 
                    "wheel_drive": wheel_drive, 
                    "engine_displacement": engine_displacement, 
                    "engine_type": engine_type, 
                    "transmition_type": transmition_type, 
                    "mileage": mileage, 
                    "interior": interior, 
                    "techstate": techstate,
                    "views": views,
                    "Is_Checked": Is_Checked,
                    "user_id": user_id,
                    "image_url": image_url
                }
            else:
                raise Exception(status_code=404, detail=f"Авто з ID {car_id} не знайдено")

            
async def get_top_cars():
    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute("SELECT id, make, model, year, price, mileage FROM cars WHERE Is_Checked = 1 ORDER BY Views DESC LIMIT 5") as cursor:
            cars = await cursor.fetchall()

        top_cars = []
        for car in cars:
            car_id = car[0]
            async with db.execute("SELECT image_path FROM car_images WHERE car_id = ? ORDER BY id DESC LIMIT 1", (car_id,)) as image_cursor:
                last_image = await image_cursor.fetchone()
                image_url = f"/static/{last_image[0]}" if last_image else None

            top_cars.append({
                "id": car_id,
                "make": car[1],
                "model": car[2],
                "year": car[3],
                "price": car[4],
                "mileage": car[5],
                "image_url": image_url
            })

    return top_cars

async def get_avatar_by_user_id(user_id: int):
    async with aiosqlite.connect("FAutoBase.db") as db:
        async with db.execute("SELECT avatar FROM users WHERE id = ?", (user_id,)) as cursor:
            avatar = await cursor.fetchone()
    return avatar[0] if avatar else None

async def require_admin(access_token: Optional[str] = Cookie(None)) -> bool:
    try:
        user = get_current_user(access_token)
        user_id = user["user_id"]
        
        async with aiosqlite.connect("FAutoBase.db") as db:
            async with db.execute("SELECT IsAdmin FROM users WHERE id = ?", (user_id,)) as cursor:
                result = await cursor.fetchone()
                if result is None:
                    raise HTTPException(status_code=404, detail="User not found")
                
                is_admin = result[0]
                return is_admin == 1
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
 
async def create_directory(path):
    os.makedirs(path)