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
from app.models import Direction, Product, User, UserRole
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
                print(f"  ✓ Direction: {name}")
            else:
                direction_ids.append(existing.id)
                print(f"  · Direction already exists: {name}")

        # Products
        for prod_name, vendor, dir_idx in PRODUCTS:
            existing = await db.scalar(select(Product).where(Product.name == prod_name))
            if not existing:
                p = Product(name=prod_name, vendor=vendor, direction_id=direction_ids[dir_idx])
                db.add(p)
                print(f"  ✓ Product: {prod_name}")
            else:
                print(f"  · Product already exists: {prod_name}")

        # Users
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
                print(f"  ✓ User: {username} ({role.value})")
            else:
                print(f"  · User already exists: {username}")

        await db.commit()
    print("\n✅ Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
