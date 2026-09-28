"""
seed.py — начальные данные для разработки.

Запуск:
  python backend/seed.py

Создаёт:
  • 3 пользователя (manager / head / admin)
  • 5 направлений
  • 6 продуктов
"""
import asyncio
import os
import sys

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app.database import engine, Base, AsyncSessionLocal
from app.models import Direction, Product, University, User, UserRole
from app.security import hash_password
from sqlalchemy import select


DIRECTIONS = [
    ("Облачные решения", "Инфраструктура и платформы в облаке"),
    ("Кибербезопасность", "Защита данных и систем"),
    ("Связь и коммуникации", "Телефония, видеоконференции, мессенджеры"),
    ("Образовательные платформы", "LMS, e-learning, дистанционное обучение"),
    ("Корпоративное ПО", "ERP, CRM, HRM-системы"),
]

PRODUCTS = [
    # (name, vendor, direction_index)
    ("RT.Cloud Edu", "Ростелеком", 0),
    ("Solar JSOC", "Ростелеком-Солар", 1),
    ("Страж-3", "Ростелеком-Солар", 1),
    ("SberJazz", "Сбер", 2),
    ("РТ.Академия", "Ростелеком", 3),
    ("1С:Университет ПРОФ", "1С", 4),
]

USERS = [
    ("manager1", "Иванов Иван Иванович", "manager1@crmrt.ru", UserRole.manager, "Manager1pass!"),
    ("head1", "Петрова Анна Сергеевна", "head1@crmrt.ru", UserRole.head, "Head1pass!"),
    ("admin", "Сидоров Алексей Викторович", "admin@crmrt.ru", UserRole.admin, "Admin1pass!"),
]

UNIVERSITIES = [
    ("Московский государственный университет им. М.В. Ломоносова", "МГУ", "Москва", "7729082090", 2027, 0, 0, "manager1"),
    ("Санкт-Петербургский государственный университет", "СПбГУ", "Санкт-Петербург", "7801002274", 2028, 1, 1, "head1"),
    ("МГТУ им. Н.Э. Баумана", "МГТУ", "Москва", "7701002520", 2029, 1, 2, "manager1"),
    ("НИУ Высшая школа экономики", "НИУ ВШЭ", "Москва", "7714030726", 2027, 2, 3, "admin"),
    ("Новосибирский государственный университет", "НГУ", "Новосибирск", "5408106985", 2028, 3, 4, "manager1"),
    ("Казанский федеральный университет", "КФУ", "Казань", "1655018018", 2029, 4, 5, "head1"),
    ("Уральский федеральный университет", "УрФУ", "Екатеринбург", "6660003190", 2027, 1, 1, "manager1"),
    ("Университет ИТМО", "ИТМО", "Санкт-Петербург", "7813045591", 2028, 2, 3, "head1"),
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Directions
        direction_ids = []
        for name, desc in DIRECTIONS:
            existing = await db.scalar(select(Direction).where(Direction.name == name))
            if not existing:
                d = Direction(name=name, description=desc)
                db.add(d)
                await db.flush()
                direction_ids.append(d.id)
                print(f"  [+] Direction: {name}")
            else:
                direction_ids.append(existing.id)
                print(f"  [*] Direction already exists: {name}")

        # Products
        product_ids = []
        for prod_name, vendor, dir_idx in PRODUCTS:
            existing = await db.scalar(select(Product).where(Product.name == prod_name))
            if not existing:
                p = Product(name=prod_name, vendor=vendor, direction_id=direction_ids[dir_idx])
                db.add(p)
                await db.flush()
                product_ids.append(p.id)
                print(f"  [+] Product: {prod_name}")
            else:
                product_ids.append(existing.id)
                print(f"  [*] Product already exists: {prod_name}")

        # Users
        user_map = {}
        for username, full_name, email, role, password in USERS:
            existing = await db.scalar(select(User).where(User.username == username))
            if not existing:
                u = User(
                    username=username,
                    full_name=full_name,
                    email=email,
                    role=role,
                    hashed_password=hash_password(password),
                )
                db.add(u)
                await db.flush()
                user_map[username] = u.id
                print(f"  [+] User: {username} ({role.value})")
            else:
                user_map[username] = existing.id
                print(f"  [*] User already exists: {username}")

        # Universities
        for name, short_name, city, inn, lic_year, dir_idx, prod_idx, mgr_username in UNIVERSITIES:
            existing = await db.scalar(select(University).where(University.name == name))
            if not existing:
                u = University(
                    name=name,
                    short_name=short_name,
                    city=city,
                    inn=inn,
                    licence_year=lic_year,
                    direction_id=direction_ids[dir_idx] if dir_idx < len(direction_ids) else None,
                    product_id=product_ids[prod_idx] if prod_idx < len(product_ids) else None,
                    manager_id=user_map.get(mgr_username),
                )
                db.add(u)
                print(f"  [+] University: {short_name or name}")
            else:
                print(f"  [*] University already exists: {short_name or name}")

        await db.commit()
    print("\n[OK] Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
