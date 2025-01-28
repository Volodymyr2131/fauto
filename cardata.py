from datetime import datetime
import json
#Типи авто
car_types = ['Легкова', 'Вантажівка', 'Автобус', 'Причіп', 'Інший']

#Список виробників авто
#car_manufacturers = ['Acura', 'Alfa Romeo', 'Aston Martin', 'Audi', 'BMW', 'Bentley', 'Buick', 'Cadillac', 'Chery', 'Chevrolet', 'Chrysler', 'Daewoo', 'Dodge', 'Fiat', 'Ford', 'GMC', 'Geely', 'Honda', 'Hummer', 'Hyundai', 'Infiniti', 'Isuzu', 'Iveco', 'Iveco', 'JAC', 'Jaguar', 'Jeep', 'Kia', 'Lamborghini', 'Lancia', 'Land Rover', 'Lexus', 'Lincoln', 'MINI', 'Maserati', 'Mazda', 'Mercedes-Benz', 'Mitsubishi', 'Nissan', 'Opel', 'Pontiac', 'Porsche', 'Rolls-Royce', 'Scania', 'Skoda', 'Smart', 'Subaru', 'Suzuki', 'Tesla', 'Toyota', 'Volkswagen', 'Volvo', 'КамАЗ', 'ЗіЛ', 'ЗАЗ', 'Лада', 'Богдан', 'ГАЗ']
with open("car_models.json", "r", encoding="utf-8") as file:
    car_manufacturers = json.load(file)

#Список кольорів авто
car_colors = ['Білий', 'Чорний', 'Сірий', 'Червоний', 'Зелений', 'Синій', 'Помаранчевий', 'Фіолетовий', 'Інший']

#Пошкодження фарби
color_condition = ['Повністью ціле', 'Виправлене', 'Не виправлене']

#Стан кузову
body_condition = ['Повністью цілий', 'Відремонтований', 'Не відремонтований']

#Стан ходової
tech_condition = ['Повністью ціла', 'Відремонтована', 'Не відремонтована', 'Не на ходу']

#Матеріал салону
interior_material = ['Тканина', 'Шкіра', 'Шкіра та тканина', 'Алькантра', 'Інший']

#Типи кузову
body_types = ['Кабріолет', 'Мінівен','Купе', 'Хетчбек/Ліфтбек', 'Позашляховик (SUV)', 'Кросовер', 'Фургон', 'Родстер', 'Вантажівка', 'Седан', 'Універсал', 'Автобус', 'Пікап', 'Причіп']

#Кількість дверей
doors = list(range(1, 11))

#Список привіду авто
wheel_drive_list = ['Передній (FWD)', 'Задній (RWD)', 'Повний (AWD)', 'Повний (4WD)', 'Інший']

damage = ['Передній лівий удар', 'Передній правий удар', 'Боковий лівий удар', 'Боковий правий удар', 'Задній лівий удар', 'Задній правий удар', 'Затоплення', 'Інший']

#Список років виробницта від 1950 по сьогоднішній
current_year = datetime.now().year
years = list(range(current_year, 1949, -1))

#Об'єм двигуна
engine_volumes = [round(i * 0.1, 1) for i in range(5, 251)]

#Покоління авто (Більше 12-13 покищо немає)
car_generations = list(range(1, 16))

#Більше 3-4 редизайнів також не було
car_facelifts = list(range(0, 6))

#Тип двигуна
engine_types = ['ДВЗ (Бензин)', 'ДВЗ (Дизель)', 'Електричний', 'Гібрид (HEV)', 'Гібрид (PHEV)', 'Гібрид (MHEV)']

#Тип трансмісії
transimiton_list = ['Автоматична (АКПП)', 'Механічна (КПП)', 'Секвентальна (ККПП)', 'Варіатор (CVT)', 'З подвійним зчепленням (DCT)', 'Робот (РКП)']