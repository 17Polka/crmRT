"""
seed.py — Инициализация начальных данных CRM Ростелекома:
• 14 базовых этапов workflow по ТЗ
• 3 пользователя (менеджер/КАМ, руководитель, администратор)
• Направления обучения и продукты
• Вузы-партнеры
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app.database import engine, Base, AsyncSessionLocal
from app.models import Direction, Product, University, WorkflowStage, User, UserRole
from app.security import hash_password
from sqlalchemy import select


STAGES = [
    (0, "Поиск контактов ответственного в вузе", "Переговоры"),
    (1, "Коммуникация и уточнение программ", "Переговоры"),
    (2, "Организация встречи с представителями вуза", "Переговоры"),
    (3, "Обмен пакетом документов для подписания", "Документы"),
    (4, "Корректировка документов перед подписанием", "Документы"),
    (5, "Подписание документов", "Документы"),
    (6, "Передача обучающих материалов и лицензии", "Внедрение"),
    (7, "Сопровождение внедрения ИТ-продуктов", "Внедрение"),
    (8, "Обучение преподавателей", "Обучение"),
    (9, "Актуализация учебной программы вуза", "Обучение"),
    (10, "Ведение занятий", "Обучение"),
    (11, "Актуализация документации по продукту", "Сопровождение"),
    (12, "Повышение квалификации преподавателей", "Обучение"),
    (13, "Контроль за исполнением каждого этапа", "Контроль"),
]

DIRECTIONS = [
    ("DevOps & Cloud", "Инфраструктура, CI/CD, облачные сервисы"),
    ("Кибербезопасность", "Информационная безопасность, SOC, криптография"),
    ("Data Science & AI", "Анализ данных, машинное обучение и ИИ"),
    ("QA & Тестирование", "Автоматизированное и ручное тестирование ПО"),
    ("Разработка ПО", "Backend, Frontend, мобильная разработка"),
]

PRODUCTS = [
    ("RT.Cloud Edu", "Ростелеком", 0),
    ("Solar JSOC", "Ростелеком-Солар", 1),
    ("Страж-3", "Ростелеком-Солар", 1),
    ("РТ.Аналитика", "Ростелеком", 2),
    ("QA Automation Studio", "Ростелеком", 3),
    ("РТ.Платформа", "Ростелеком", 4),
]

USERS = [
    ("manager1", "Иванов Иван (КАМ)", "manager1@crmrt.ru", UserRole.manager, "Manager123!"),
    ("manager2", "Смирнова Ольга (КАМ)", "manager2@crmrt.ru", UserRole.manager, "Manager123!"),
    ("manager3", "Кузнецов Дмитрий (КАМ)", "manager3@crmrt.ru", UserRole.manager, "Manager123!"),
    ("manager4", "Васильева Елена (КАМ)", "manager4@crmrt.ru", UserRole.manager, "Manager123!"),
    ("manager5", "Попов Сергей (КАМ)", "manager5@crmrt.ru", UserRole.manager, "Manager123!"),
    ("manager6", "Морозова Татьяна (КАМ)", "manager6@crmrt.ru", UserRole.manager, "Manager123!"),
    ("head1", "Петрова Анна (Руководитель)", "head1@crmrt.ru", UserRole.head, "Head123!"),
    ("head2", "Ковалев Михаил (Руководитель)", "head2@crmrt.ru", UserRole.head, "Head123!"),
    ("admin", "Сидоров Алексей (Администратор)", "admin@crmrt.ru", UserRole.admin, "Admin123!"),
    ("admin2", "Николаев Роман (Администратор ИБ)", "admin2@crmrt.ru", UserRole.admin, "Admin123!"),
]

INITIAL_UNIVERSITIES = [
    ("МГТУ им. Н.Э. Баумана", "Москва", "7701002520", 0, 0, 6, "ТЕСТ-101", 2027, "Передано"),
    ("СПбПУ Петра Великого", "Санкт-Петербург", "7804040077", 1, 1, 3, "ТЕСТ-102", 2028, "В процессе"),
    ("ННГУ им. Н.И. Лобачевского", "Нижний Новгород", "5262006698", 2, 3, 10, "ТЕСТ-103", 2026, "Передано"),
    ("ИТМО", "Санкт-Петербург", "7813045580", 0, 0, 8, "ТЕСТ-104", 2027, "Передано"),
    ("УрФУ", "Екатеринбург", "6660003190", 3, 4, 1, "ТЕСТ-105", 2026, "Не передано"),
    ("КФУ", "Казань", "1655018018", 4, 5, 12, "ТЕСТ-106", 2029, "Передано"),
    ("НГУ", "Новосибирск", "5408100229", 1, 2, 5, "ТЕСТ-107", 2027, "В процессе"),
    ("МИФИ", "Москва", "7724068140", 2, 3, 13, "ТЕСТ-108", 2028, "Передано"),
    ("МФТИ (Физтех)", "Долгопрудный", "5008006211", 0, 0, 4, "ТЕСТ-109", 2027, "В процессе"),
    ("ТПУ", "Томск", "7021000350", 1, 1, 7, "ТЕСТ-110", 2028, "Передано"),
    ("ЮФУ", "Ростов-на-Дону", "6165036136", 3, 4, 2, "ТЕСТ-111", 2026, "Не передано"),
    ("ДВФУ", "Владивосток", "2536014538", 4, 5, 9, "ТЕСТ-112", 2029, "Передано"),
    ("ВГУ", "Воронеж", "3666029505", 2, 3, 11, "ТЕСТ-113", 2028, "Передано"),
    ("Самарский университет", "Самара", "6316000632", 0, 0, 0, "ТЕСТ-114", 2026, "Не передано"),
    ("СПбГУ", "Санкт-Петербург", "7801002274", 1, 2, 5, "ТЕСТ-115", 2027, "В процессе"),
    ("ПНИПУ", "Пермь", "5902290455", 3, 4, 8, "ТЕСТ-116", 2028, "Передано"),
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        print("[*] Init database...")

        # 1. Этапы workflow
        for order, name, category in STAGES:
            st = await db.scalar(select(WorkflowStage).where(WorkflowStage.order == order))
            if not st:
                db.add(WorkflowStage(order=order, name=name, category=category))
                print(f"  + Stage {order + 1}: {name}")
            else:
                st.name = name
                st.category = category

        # 2. Направления
        dir_ids = []
        for name, desc in DIRECTIONS:
            d = await db.scalar(select(Direction).where(Direction.name == name))
            if not d:
                d = Direction(name=name, description=desc)
                db.add(d)
                await db.flush()
                print(f"  + Direction: {name}")
            dir_ids.append(d.id)

        # 3. Продукты
        prod_ids = []
        for name, vendor, dir_idx in PRODUCTS:
            p = await db.scalar(select(Product).where(Product.name == name))
            if not p:
                p = Product(name=name, vendor=vendor, direction_id=dir_ids[dir_idx])
                db.add(p)
                await db.flush()
                print(f"  + Product: {name} ({vendor})")
            prod_ids.append(p.id)

        # 4. Пользователи
        user_ids = []
        for username, full_name, email, role, pwd in USERS:
            u = await db.scalar(select(User).where(User.username == username))
            if not u:
                u = User(
                    username=username,
                    full_name=full_name,
                    email=email,
                    role=role,
                    hashed_password=hash_password(pwd),
                )
                db.add(u)
                await db.flush()
                print(f"  + User: {username} [{role.value}]")
            user_ids.append(u.id)

        # Менеджеры для распределения вузов
        managers_only = [u for u in (await db.scalars(select(User).where(User.role == UserRole.manager))).all()]

        # 5. Вузы
        for idx, (name, city, inn, d_idx, p_idx, stage, contract, lic_year, status) in enumerate(INITIAL_UNIVERSITIES):
            uni = await db.scalar(select(University).where(University.name == name))
            assigned_manager = managers_only[idx % len(managers_only)]
            if not uni:
                uni = University(
                    name=name,
                    city=city,
                    inn=inn,
                    direction_id=dir_ids[d_idx % len(dir_ids)],
                    product_id=prod_ids[p_idx % len(prod_ids)],
                    manager_id=assigned_manager.id,
                    manager_fio=assigned_manager.full_name,
                    current_stage_order=stage,
                    contract_number=contract,
                    licence_year=lic_year,
                    transfer_status=status,
                    vendor=PRODUCTS[p_idx % len(PRODUCTS)][1],
                    software=PRODUCTS[p_idx % len(PRODUCTS)][0],
                    comment="Базовое взаимодействие по соглашению"
                )
                db.add(uni)
                print(f"  + University: {name} (Stage {stage + 1}, КАМ: {assigned_manager.full_name})")

        await db.commit()
    print("[OK] Database seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
