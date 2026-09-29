"""
stress_test.py — Нагрузочное тестирование CRM ИТ Школы Ростелекома.
Требования ТЗ:
- Проверка производительности при 50 параллельных пользователях (авторизация, канбан-доска, каталоги)
- Проверка генерации 10 параллельных отчётов (XLSX, PDF, JSON)
- Замер метрик: RPS, среднее время отклика (Latency ms), p95, процент успешных запросов
"""
import asyncio
import time
import json
import statistics
import sys

# Настройка кодировки вывода для Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from httpx import AsyncClient, ASGITransport

from app.main import app


async def run_stress_test():
    print("=" * 70)
    print("[STRESS TEST] CRM IT SCHOOL ROSTELECOM BENCHMARK")
    print("=" * 70)

    transport = ASGITransport(app=app)
    results = {
        "concurrent_users": 50,
        "concurrent_reports": 10,
        "tasks": [],
    }

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Авторизация под демо-пользователем
        login_res = await client.post(
            "/api/security/login",
            json={"username": "admin", "password": "Admin123!"}
        )
        if login_res.status_code != 200:
            print(f"[FAIL] Ошибка входа администратора: {login_res.text}")
            return
        token = login_res.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        print("[OK] Авторизация успешна. Токен получен.")

        # -------------------------------------------------------------------
        # ТЕСТ 1: 50 параллельных пользователей (Канбан + Каталоги + Аудит)
        # -------------------------------------------------------------------
        print("\n[ТЕСТ 1] Запуск 50 параллельных пользователей...")
        endpoints = [
            ("/api/workflow/board", "GET"),
            ("/api/catalogs/universities", "GET"),
            ("/api/catalogs/directions", "GET"),
            ("/api/catalogs/products", "GET"),
            ("/api/security/users", "GET"),
            ("/api/workflow/stages", "GET"),
        ]

        latencies_users = []
        errors_users = 0

        async def simulate_user(user_idx: int):
            nonlocal errors_users
            for path, method in endpoints:
                start = time.perf_counter()
                try:
                    res = await client.get(path, headers=headers)
                    dur = (time.perf_counter() - start) * 1000
                    latencies_users.append(dur)
                    if res.status_code != 200:
                        errors_users += 1
                except Exception:
                    errors_users += 1

        t0 = time.perf_counter()
        await asyncio.gather(*(simulate_user(i) for i in range(50)))
        total_time_users = time.perf_counter() - t0

        avg_lat_users = statistics.mean(latencies_users) if latencies_users else 0
        p95_lat_users = statistics.quantiles(latencies_users, n=20)[18] if len(latencies_users) >= 20 else avg_lat_users
        rps_users = len(latencies_users) / total_time_users if total_time_users > 0 else 0

        print(f"  • Всего запросов: {len(latencies_users)}")
        print(f"  • Успешность: {((len(latencies_users) - errors_users) / len(latencies_users) * 100):.1f}%")
        print(f"  • Общее время: {total_time_users:.2f} сек")
        print(f"  • Средний отклик (Latency): {avg_lat_users:.2f} мс")
        print(f"  • 95-й процентиль (p95): {p95_lat_users:.2f} мс")
        print(f"  • Производительность (RPS): {rps_users:.1f} req/sec")

        # -------------------------------------------------------------------
        # ТЕСТ 2: 10 параллельных тяжелых отчетов (XLSX, PDF, JSON)
        # -------------------------------------------------------------------
        print("\n[ТЕСТ 2] Запуск 10 параллельных отчётов (XLSX / PDF / JSON)...")
        report_formats = ["xlsx", "pdf", "json", "xlsx", "pdf", "json", "xlsx", "pdf", "xlsx", "json"]
        latencies_reports = []
        errors_reports = 0

        async def generate_report_task(idx: int, fmt: str):
            nonlocal errors_reports
            start = time.perf_counter()
            try:
                res = await client.get(
                    f"/api/reports/generate?format={fmt}&columns=name,direction,product,stage,manager",
                    headers=headers
                )
                dur = (time.perf_counter() - start) * 1000
                latencies_reports.append(dur)
                if res.status_code != 200 or len(res.content) < 50:
                    errors_reports += 1
            except Exception:
                errors_reports += 1

        t0_rep = time.perf_counter()
        await asyncio.gather(*(generate_report_task(i, fmt) for i, fmt in enumerate(report_formats)))
        total_time_rep = time.perf_counter() - t0_rep

        avg_lat_rep = statistics.mean(latencies_reports) if latencies_reports else 0
        p95_lat_rep = statistics.quantiles(latencies_reports, n=20)[18] if len(latencies_reports) >= 20 else avg_lat_rep
        rps_rep = len(latencies_reports) / total_time_rep if total_time_rep > 0 else 0

        print(f"  • Сформировано отчётов: {len(latencies_reports)}")
        print(f"  • Успешность: {((len(latencies_reports) - errors_reports) / len(latencies_reports) * 100):.1f}%")
        print(f"  • Время генерации 10 отчётов: {total_time_rep:.2f} сек")
        print(f"  • Среднее время на отчёт: {avg_lat_rep:.2f} мс")
        print(f"  • 95-й процентиль: {p95_lat_rep:.2f} мс")
        print(f"  • RPS отчётов: {rps_rep:.1f} reports/sec")

        # -------------------------------------------------------------------
        # ИТОГОВЫЙ ВЕРДИКТ
        # -------------------------------------------------------------------
        passed = (errors_users == 0 and errors_reports == 0 and avg_lat_users < 200 and avg_lat_rep < 1000)
        print("\n" + "=" * 70)
        if passed:
            print("[PASS] НАГРУЗОЧНОЕ ТЕСТИРОВАНИЕ ПРОЙДЕНО УСПЕШНО!")
            print("       Система полностью удовлетворяет требованиям ТЗ к масштабируемости.")
        else:
            print("[WARN] Тестирование завершено с предупреждениями.")
        print("=" * 70)

        # Сохранение результатов
        report_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "PASSED" if passed else "WARNINGS",
            "test_users": {
                "concurrency": 50,
                "total_requests": len(latencies_users),
                "errors": errors_users,
                "avg_latency_ms": round(avg_lat_users, 2),
                "p95_latency_ms": round(p95_lat_users, 2),
                "rps": round(rps_users, 2),
            },
            "test_reports": {
                "concurrency": 10,
                "total_reports": len(latencies_reports),
                "errors": errors_reports,
                "avg_latency_ms": round(avg_lat_rep, 2),
                "p95_latency_ms": round(p95_lat_rep, 2),
                "rps": round(rps_rep, 2),
            }
        }
        with open("stress_test_report.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        print("[SAVED] Результаты сохранены в backend/stress_test_report.json")


if __name__ == "__main__":
    asyncio.run(run_stress_test())
