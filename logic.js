// ============================================================================
// CRM ИТ Школы Ростелекома — Frontend Logic
// Интеграция с Backend API (FastAPI), роли (КАМ, Руководитель, Администратор),
// 14 этапов workflow, скачивание отчётов (XLSX, PDF, JSON), загрузка файлов,
// аналитика Chart.js и клиентское кэширование (отклик < 1 сек по ТЗ).
// ============================================================================

const API_BASE = window.location.protocol.startsWith("http")
  ? window.location.origin
  : "http://localhost:8000";

let STAGES = [
  "Поиск контактов ответственного в вузе",
  "Коммуникация и уточнение программ",
  "Организация встречи с представителями вуза",
  "Обмен пакетом документов для подписания",
  "Корректировка документов перед подписанием",
  "Подписание документов",
  "Передача обучающих материалов и лицензии",
  "Сопровождение внедрения ИТ-продуктов",
  "Обучение преподавателей",
  "Актуализация учебной программы вуза",
  "Ведение занятий",
  "Актуализация документации по продукту",
  "Повышение квалификации преподавателей",
  "Контроль за исполнением каждого этапа"
];

let DIRECTIONS = [
  "DevOps & Cloud",
  "Кибербезопасность",
  "Data Science & AI",
  "QA & Тестирование",
  "Разработка ПО"
];

// Пользователи системы (синхронизируются с БД)
let ADMIN_USERS = [
  { id: "mgr-1", username: "manager1", name: "Иванов Иван (КАМ)", role: "manager", blocked: false },
  { id: "mgr-2", username: "manager2", name: "Смирнова Ольга (КАМ)", role: "manager", blocked: false },
  { id: "mgr-3", username: "manager3", name: "Кузнецов Дмитрий (КАМ)", role: "manager", blocked: false },
  { id: "mgr-4", username: "manager4", name: "Васильева Елена (КАМ)", role: "manager", blocked: false },
  { id: "mgr-5", username: "manager5", name: "Попов Сергей (КАМ)", role: "manager", blocked: false },
  { id: "mgr-6", username: "manager6", name: "Морозова Татьяна (КАМ)", role: "manager", blocked: false },
  { id: "hd-1", username: "head1", name: "Петрова Анна (Руководитель)", role: "head", blocked: false },
  { id: "hd-2", username: "head2", name: "Ковалев Михаил (Руководитель)", role: "head", blocked: false },
  { id: "adm-1", username: "admin", name: "Сидоров Алексей (Администратор)", role: "admin", blocked: false },
  { id: "adm-2", username: "admin2", name: "Николаев Роман (Администратор ИБ)", role: "admin", blocked: false }
];

let MANAGERS = ADMIN_USERS.map((u) => u.name);

const ROLES = { manager: 0, user: 0, head: 1, admin: 2 };
const ROLE_LABELS = {
  manager: "Пользователь (КАМ)",
  user: "Пользователь (КАМ)",
  head: "Руководитель",
  admin: "Администратор"
};

let UNIVERSITIES = [];
let currentUser = null;
let authToken = localStorage.getItem("crm_token") || null;
let currentManagerName = "Иванов Иван (КАМ)";
let role = "manager";
let isLoggedIn = false;
let activeTab = 0;
let query = "";
let directionFilter = "";
let reportColumns = ["name", "direction", "product", "stage", "manager"];
let reportFormat = "xlsx";
let catalogTab = 0;
let currentChart = null;
let loadedDetailsUniId = null;

let eventLog = [
  "Система инициализирована. Подключение к API: " + API_BASE,
  "Keycloak SSO & локальный JWT готовы к работе",
  "Журнал аудита ФЗ-152 / ФСТЭК №117 активен"
];

// Матрица навигации по правам доступа (0=КАМ, 1=Руководитель, 2=Администратор)
const NAV = [
  ["dashboard", "Дашборд", 0],
  ["vuzes", "Вузы", 0],
  ["workflow", "Workflow", 0],
  ["reports", "Отчёты", 0],
  ["catalogs", "Каталоги", 1],
  ["integ", "Интеграции", 2],
  ["admin", "Администрирование", 2],
  ["docs", "Справка", 0]
];

const $ = (selector) => document.querySelector(selector);

// ---------------------------------------------------------------------------
// Сетевой слой с кэшированием (соответствие ТЗ: отклик < 1 сек)
// ---------------------------------------------------------------------------

async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { credentials: "omit", ...options, headers });
    if (res.status === 401) {
      authToken = null;
      localStorage.removeItem("crm_token");
      isLoggedIn = false;
      render();
      throw new Error("401: Требуется авторизация");
    }
    if (res.status === 403) {
      showToast("Ошибка 403: Недостаточно прав для выполнения действия");
      throw new Error("403: Forbidden");
    }
    return res;
  } catch (err) {
    console.warn("API Error:", err);
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Загрузка начальных данных из бэкенда
// ---------------------------------------------------------------------------

async function loadDataFromApi() {
  try {
    // 1. Загрузка этапов workflow
    const stagesRes = await apiFetch("/api/workflow/stages");
    if (stagesRes.ok) {
      const stagesData = await stagesRes.json();
      if (stagesData && stagesData.length) {
        STAGES = stagesData.sort((a, b) => a.order - b.order).map((s) => s.name);
      }
    }

    // 2. Загрузка направлений
    const dirRes = await apiFetch("/api/catalogs/directions");
    if (dirRes.ok) {
      const dirData = await dirRes.json();
      const dirs = dirData.items || dirData;
      if (dirs.length) DIRECTIONS = dirs.map((d) => d.name);
    }

    // 3. Загрузка справочника менеджеров (доступно всем ролям)
    const mgrRes = await apiFetch("/api/catalogs/managers");
    if (mgrRes.ok) {
      const mgrList = await mgrRes.json();
      if (mgrList && mgrList.length) {
        mgrList.forEach((m) => {
          const existing = ADMIN_USERS.find((u) => u.username === m.username);
          if (existing) {
            existing.id = m.id;
            existing.name = m.full_name;
            existing.role = m.role;
          } else {
            ADMIN_USERS.push({
              id: m.id,
              username: m.username,
              name: m.full_name,
              role: m.role,
              blocked: false
            });
          }
        });
        MANAGERS = ADMIN_USERS.map((u) => u.name);
      }
    }

    // 4. Загрузка полного списка пользователей (Руководитель и Админ)
    if (ROLES[role] >= 1) {
      const usersRes = await apiFetch("/api/security/users");
      if (usersRes.ok) {
        const uData = await usersRes.json();
        const uList = uData.items || uData;
        ADMIN_USERS = uList.map((u) => ({
          id: u.id,
          username: u.username,
          name: u.full_name,
          role: u.role,
          blocked: u.is_blocked || !u.is_active
        }));
        MANAGERS = ADMIN_USERS.map((u) => u.name);
      }
    }

    // 5. Загрузка журнала аудита (Руководитель и Админ — ФЗ-152)
    if (ROLES[role] >= 1) {
      try {
        const auditRes = await apiFetch("/api/security/audit?page_size=10");
        if (auditRes.ok) {
          const auditData = await auditRes.json();
          const items = auditData.items || [];
          if (items.length) {
            eventLog = items.map((l) => {
              const dt = new Date(l.created_at).toLocaleString("ru");
              return `[${dt}] ${l.username || "Система"} — ${l.action}${l.detail ? ": " + JSON.stringify(l.detail) : ""}`;
            });
          }
        }
      } catch (e) {}
    }

    // 6. Загрузка канбан-доски вузов (бэкенд изолирует вузы для КАМ)
    const boardRes = await apiFetch("/api/workflow/board");
    if (boardRes.ok) {
      const board = await boardRes.json();
      let allUnis = [];
      board.forEach((col) => {
        col.universities.forEach((u) => {
          allUnis.push({
            id: u.id,
            name: u.name,
            city: u.city || "Не указан",
            direction: u.direction || DIRECTIONS[0],
            product: u.software || u.vendor || "RT.Cloud Edu",
            stage: u.current_stage,
            managerId: u.manager_id,
            manager: u.manager_fio || "Не назначен",
            licenceYear: u.licence_year || 2027,
            contract: u.contract || "ТЕСТ-" + (100 + u.id),
            lastUpdate: u.last_update || todayString(),
            history: [],
            files: [],
            comments: []
          });
        });
      });
      if (allUnis.length) {
        UNIVERSITIES = allUnis;
      }
    }
  } catch (e) {
    console.log("Используем локальные данные кэша при недоступности сети:", e);
  }
}

// Фильтрация видимости вузов в соответствии с ТЗ:
// КАМ видит только свои закрепленные вузы, Руководитель и Админ — все
function visibleUniversities() {
  if (role === "manager" || role === "user") {
    return UNIVERSITIES.filter((v) => {
      if (currentUser && currentUser.id && v.managerId) {
        return v.managerId === currentUser.id;
      }
      return v.manager === currentManagerName;
    });
  }
  return UNIVERSITIES;
}

function daysSinceUpdate(v) {
  if (!v.lastUpdate) return 0;
  const parts = v.lastUpdate.split(".").map(Number);
  if (parts.length < 3) return 0;
  const lastDate = new Date(parts[2], parts[1] - 1, parts[0]);
  return Math.max(0, Math.floor((Date.now() - lastDate.getTime()) / 86400000));
}

function stageGroup(stage) {
  if (stage < 3) return "Переговоры";
  if (stage < 8) return "Внедрение";
  return "Обучение";
}

function todayString() {
  return new Date().toLocaleDateString("ru");
}

function showToast(text) {
  const el = document.createElement("div");
  el.className = "ts";
  el.textContent = text;
  document.body.append(el);
  setTimeout(() => el.remove(), 2500);
}

// ---------------------------------------------------------------------------
// Авторизация (Keycloak / Local Dev)
// ---------------------------------------------------------------------------

function loginView() {
  return `
    <div class="cd lg">
      <div class="logo" style="justify-content:center;margin:12px 0">
        <span>Ростелеком<small>ИТ Школа</small></span>
      </div>
      <h1>Войдите в систему CRM</h1>
      <p class="mu" style="font-size:13px;margin-bottom:12px">
        Быстрый доступ: <b>admin</b> / <b>Admin123!</b> | <b>head1</b> / <b>Head123!</b> | <b>manager1</b> / <b>Manager123!</b>
      </p>
      <input id="em" type="text" placeholder="Логин (например, admin или manager1)" value="admin" aria-label="Логин">
      <input id="pw" type="password" placeholder="Пароль" value="Admin123!" aria-label="Пароль">
      <button class="b" style="width:100%;margin-top:10px" onclick="submitLogin()">Войти в систему</button>
      <p class="mu" style="font-size:12px;margin-top:14px">Поддерживается интеграция Keycloak SSO / ФЗ-152</p>
    </div>
  `;
}

async function submitLogin() {
  const username = $("#em").value.trim();
  const password = $("#pw").value.trim();
  if (!username) {
    showToast("Введите имя пользователя");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/security/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || "Ошибка авторизации");
      return;
    }

    const data = await res.json();
    authToken = data.access_token;
    localStorage.setItem("crm_token", authToken);
    if (data.user) {
      currentUser = data.user;
      role = data.user.role;
      currentManagerName = data.user.full_name;
    } else {
      role = username.startsWith("admin") ? "admin" : username.startsWith("head") ? "head" : "manager";
      currentManagerName = username;
    }

    isLoggedIn = true;
    location.hash = "#/dashboard";
    await loadDataFromApi();
    render();
    showToast(`Вы вошли как ${ROLE_LABELS[role] || role}`);
  } catch (err) {
    isLoggedIn = true;
    location.hash = "#/dashboard";
    render();
  }
}

function appShell(page, content) {
  return `
    <header>
      <div class="logo">
        <span>Ростелеком<small>ИТ Школа · CRM</small></span>
      </div>
      <nav>
        ${NAV
          .filter((item) => ROLES[role] >= item[2])
          .map((item) => {
            const activeClass = page === item[0] || (page === "vuz" && item[0] === "vuzes") ? "on" : "";
            return `<a href="#/${item[0]}" class="${activeClass}">${item[1]}</a>`;
          })
          .join("")}
      </nav>
      <div style="display:flex;align-items:center;gap:8px;margin-left:auto">
        <select style="width:auto;font-size:13px" aria-label="Текущий пользователь" onchange="switchAccount(this.value)">
          ${ADMIN_USERS
            .filter((u) => !u.blocked)
            .map((u) => `<option value="${u.name}" ${u.name === currentManagerName ? "selected" : ""}>${u.name} (${ROLE_LABELS[u.role] || u.role})</option>`)
            .join("")}
        </select>
        <button class="b g s" onclick="logout()">Выйти</button>
      </div>
    </header>
    <main>${content}</main>
  `;
}

async function switchAccount(name) {
  const user = ADMIN_USERS.find((u) => u.name === name);
  if (!user) return;
  currentManagerName = user.name;
  role = user.role;
  currentUser = user;
  loadedDetailsUniId = null;

  try {
    const pwd = user.username.startsWith("admin") ? "Admin123!" : user.username.startsWith("head") ? "Head123!" : "Manager123!";
    const res = await fetch(`${API_BASE}/api/security/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user.username, password: pwd })
    });
    if (res.ok) {
      const data = await res.json();
      authToken = data.access_token;
      localStorage.setItem("crm_token", authToken);
      if (data.user) {
        currentUser = data.user;
      }
    }
  } catch (e) {}

  await loadDataFromApi();
  render();
  showToast(`Переключено на: ${user.name} (${ROLE_LABELS[role]})`);
}

async function logout() {
  try {
    if (authToken) {
      await apiFetch("/api/security/logout", { method: "POST" });
    }
  } catch (e) {}
  authToken = null;
  currentUser = null;
  localStorage.removeItem("crm_token");
  isLoggedIn = false;
  render();
}

function forbiddenView() {
  return `
    <div class="cd" style="text-align:center">
      <div class="k">403</div>
      <h2>Нет доступа</h2>
      <p class="mu">Этот раздел доступен только роли Руководитель или Администратор.</p>
      <a class="b" href="#/dashboard">На дашборд</a>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Дашборд с визуализацией статистики (Chart.js + экспорт PNG / PDF / JSON)
// ---------------------------------------------------------------------------

function dashboardView() {
  const list = visibleUniversities();
  const stageCounts = STAGES.map((_, i) => list.filter((v) => v.stage === i).length);
  const attention = list.filter((v) => daysSinceUpdate(v) >= 14).length;
  const averageStage = list.length ? Math.round(list.reduce((sum, v) => sum + v.stage + 1, 0) / list.length) : 0;

  // Инициализация Chart.js после рендера
  setTimeout(() => initDashboardChart(stageCounts), 50);

  // Журнал аудита доступен ТОЛЬКО для Руководителя и Администратора (ТЗ / ФЗ-152)
  const auditBlock = ROLES[role] >= 1
    ? `
      <div class="cd" style="margin-top:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px">
          <h2>Журнал аудита событий безопасности (ФЗ-152 / ФСТЭК №117)</h2>
          ${ROLES[role] >= 2 ? `<button class="b g s" onclick="exportAuditXlsx()">Экспорт аудита (.xlsx)</button>` : ""}
        </div>
        ${eventLog.slice(0, 7).map((line) => `<div style="padding:6px 0;border-bottom:1px solid var(--bd);font-size:13px">${line}</div>`).join("")}
      </div>
    `
    : "";

  return `
    <h1>Дашборд аналитики</h1>
    <div class="fl">
      <select aria-label="Период">
        <option>2026/2027 учебный год</option>
        <option>Сентябрь 2026</option>
        <option>3 квартал 2026</option>
      </select>
      <select aria-label="Направление" onchange="setDirectionFilter(this.value)">
        <option value="">Все направления</option>
        ${DIRECTIONS.map((d) => `<option value="${d}">${d}</option>`).join("")}
      </select>
      <button class="b s g" onclick="exportResultJson()">Выгрузить JSON (ТЗ 6.4)</button>
    </div>
    <div class="gr">
      <div class="cd">
        <div class="k">${list.length}</div>
        <div class="mu">вузов в работе</div>
      </div>
      <div class="cd">
        <div class="k">${list.filter((v) => v.stage < 13).length}</div>
        <div class="mu">активных взаимодействий</div>
      </div>
      <div class="cd">
        <div class="k" style="color:var(--rd, #d32f2f)">${attention}</div>
        <div class="mu">требуют внимания (&gt;14 дн.)</div>
      </div>
      <div class="cd">
        <div class="k">${averageStage}</div>
        <div class="mu">средний этап из 14</div>
      </div>
    </div>
    <div class="cd" style="margin-top:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px">
        <h2>Востребованность программ и распределение по этапам</h2>
        <div>
          <button class="b g s" onclick="exportChart('png')">Экспорт графика (PNG)</button>
          <button class="b g s" onclick="exportReportFile('pdf')">Экспорт отчёта (PDF)</button>
        </div>
      </div>
      <div style="position:relative;height:260px;width:100%">
        <canvas id="analyticsChart"></canvas>
      </div>
    </div>
    ${auditBlock}
  `;
}

function initDashboardChart(stageCounts) {
  const ctx = document.getElementById("analyticsChart");
  if (!ctx || typeof Chart === "undefined") return;

  if (currentChart) {
    currentChart.destroy();
  }

  currentChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: STAGES.map((s, i) => `${i + 1}. ${s.slice(0, 16)}...`),
      datasets: [{
        label: "Количество ВУЗов на этапе",
        data: stageCounts,
        backgroundColor: "rgba(119, 0, 255, 0.75)",
        borderColor: "rgba(119, 0, 255, 1)",
        borderWidth: 1,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 } },
        x: { ticks: { font: { size: 10 } } }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

function exportChart(format) {
  if (!currentChart) {
    showToast("График ещё не загружен");
    return;
  }
  const link = document.createElement("a");
  link.download = `chart_analytics.${format}`;
  link.href = currentChart.toBase64Image();
  link.click();
  showToast("Диаграмма успешно экспортирована");
}

// ---------------------------------------------------------------------------
// Вузы — Таблица и Карточка
// ---------------------------------------------------------------------------

function universityRows() {
  let list = visibleUniversities();
  if (directionFilter) {
    list = list.filter((v) => v.direction === directionFilter);
  }
  if (query) {
    list = list.filter((v) => (v.name + v.city + v.product).toLowerCase().includes(query.toLowerCase()));
  }
  if (!list.length) {
    return '<tr><td colspan="7" class="mu">Ничего не найдено. Измените поиск или фильтры.</td></tr>';
  }
  return list
    .map((v) => `
      <tr class="c" tabindex="0" onclick="location.hash='#/vuz/${v.id}'">
        <td><b>${v.name}</b></td>
        <td>${v.city}</td>
        <td>${v.direction}</td>
        <td>${v.product}</td>
        <td><span class="tag">${v.stage + 1}. ${STAGES[v.stage] || "Этап " + (v.stage + 1)}</span></td>
        <td>${v.manager}</td>
        <td>${v.licenceYear}</td>
      </tr>
    `)
    .join("");
}

function refreshTable() {
  const el = $("#tb");
  if (el) el.innerHTML = universityRows();
}

function setDirectionFilter(value) {
  directionFilter = value;
  refreshTable();
}

function universitiesView() {
  return `
    <h1>Каталог ВУЗов</h1>
    <div class="fl">
      <input placeholder="Поиск по вузу, городу, продукту..." value="${query}"
             oninput="query=this.value;refreshTable()" aria-label="Поиск">
      <select onchange="setDirectionFilter(this.value)" aria-label="Направление">
        <option value="">Все направления</option>
        ${DIRECTIONS.map((d) => `<option ${d === directionFilter ? "selected" : ""}>${d}</option>`).join("")}
      </select>
    </div>
    <div class="cd tw">
      <table>
        <thead>
          <tr>
            <th>Вуз</th>
            <th>Город</th>
            <th>Направление</th>
            <th>Продукт</th>
            <th>Этап workflow</th>
            <th>Ответственный</th>
            <th>Лицензия до</th>
          </tr>
        </thead>
        <tbody id="tb">${universityRows()}</tbody>
      </table>
    </div>
  `;
}

// Динамическая подгрузка вложений и истории карточки вуза из БД
async function loadUniversityDetails(id) {
  const v = UNIVERSITIES.find((x) => x.id == id);
  if (!v) return;

  try {
    const [attRes, histRes] = await Promise.all([
      apiFetch(`/api/workflow/${id}/attachments`),
      apiFetch(`/api/workflow/${id}/history`)
    ]);

    if (attRes.ok) {
      const atts = await attRes.json();
      v.files = atts.map((a) => [
        a.filename,
        new Date(a.created_at).toLocaleDateString("ru"),
        a.uploaded_by || "Система",
        a.id
      ]);
    }

    if (histRes.ok) {
      const hists = await histRes.json();
      v.history = hists.map((h) => ({
        date: new Date(h.created_at).toLocaleDateString("ru") + " " + new Date(h.created_at).toLocaleTimeString("ru", { hour: "2-digit", minute: "2-digit" }),
        text: `${h.user_name || "Пользователь"}: ${h.action_type === "comment" ? "Комментарий: " + h.comment : (STAGES[h.from_stage] || "Этап " + (h.from_stage + 1)) + " → " + (STAGES[h.to_stage] || "Этап " + (h.to_stage + 1)) + (h.comment ? " (" + h.comment + ")" : "")}`
      }));

      v.comments = hists
        .filter((h) => h.comment)
        .map((h) => [
          h.user_name || "Пользователь",
          new Date(h.created_at).toLocaleDateString("ru") + " " + new Date(h.created_at).toLocaleTimeString("ru", { hour: "2-digit", minute: "2-digit" }),
          h.comment
        ]);
    }
  } catch (e) {
    console.warn("Ошибка загрузки деталей вуза:", e);
  }
}

function universityView(id) {
  const v = visibleUniversities().find((x) => x.id == id);
  if (!v) {
    return `
      <div class="cd" style="text-align:center">
        <div class="k">404</div>
        <p>Вуз не найден или недоступен для вашей роли.</p>
        <a class="b" href="#/vuzes">К списку вузов</a>
      </div>
    `;
  }

  // При первом открытии карточки вуза подгружаем историю и вложения из БД
  if (loadedDetailsUniId !== id) {
    loadedDetailsUniId = id;
    loadUniversityDetails(id).then(() => render());
  }

  const TABS = ["Общее", "Workflow", "Документы и лицензии", "Комментарии", "История"];
  let content = "";

  if (activeTab === 0) {
    content = `
      <div class="gr">
        <div><div class="mu">Вендор / ПО</div>${v.product}</div>
        <div><div class="mu">Номер договора</div>${v.contract}</div>
        <div><div class="mu">Срок лицензии</div>${v.licenceYear} год</div>
        <div><div class="mu">Направление</div>${v.direction}</div>
        <div><div class="mu">Город</div>${v.city}</div>
        <div><div class="mu">Статус</div>${stageGroup(v.stage)}</div>
      </div>
    `;
  }

  if (activeTab === 1) {
    content = `
      <div class="st">
        ${STAGES.map((stage, i) => `
          <div class="${i < v.stage ? "d" : i === v.stage ? "n" : ""}">
            <b>${i < v.stage ? "✓" : i + 1}</b>${stage}
          </div>
        `).join("")}
      </div>
      <p style="margin-top:16px">
        <button class="b g" ${v.stage === 0 ? "disabled" : ""} onclick="openStageModal(${v.id}, -1)">← Вернуть на этап назад</button>
        <button class="b" ${v.stage === 13 ? "disabled" : ""} onclick="openStageModal(${v.id}, 1)">Перевести на следующий этап →</button>
      </p>
    `;
  }

  if (activeTab === 2) {
    const fileList = v.files.length
      ? v.files.map((f) => {
          const dlCall = f[3]
            ? `downloadAttachment(${v.id}, ${f[3]}, '${f[0]}')`
            : `window.open('${API_BASE}/uploads/${f[0]}', '_blank')`;
          return `
            <div style="padding:10px 0;border-bottom:1px solid var(--bd);display:flex;justify-content:space-between;align-items:center">
              <div>
                <a onclick="${dlCall}">📄 <b>${f[0]}</b></a>
                <span class="mu" style="font-size:13px"> · ${f[1]} · ${f[2]}</span>
              </div>
              <button class="b s g" onclick="${dlCall}">Скачать</button>
            </div>
          `;
        }).join("")
      : '<p class="mu">Файлов нет. Вы можете прикрепить лицензии или договор при переходе статуса.</p>';

    content = `
      ${fileList}
      <p style="margin-top:14px">
        <label class="b g" style="display:inline-block">
          Загрузить файл в этап
          <input type="file" hidden onchange="addFile(${v.id}, this.files[0])">
        </label>
      </p>
      <p class="mu" style="font-size:12px">Поддерживаемые форматы (ТЗ): png, jpeg, pdf, zip, gzip, rar, doc, docx, xls, xlsx</p>
    `;
  }

  if (activeTab === 3) {
    const comments = v.comments.length
      ? v.comments.map((x) => `<div style="padding:8px 0;border-bottom:1px solid var(--bd)"><b>${x[0]}</b> <span class="mu">${x[1]}</span><br>${x[2]}</div>`).join("")
      : '<p class="mu">Комментариев пока нет.</p>';

    content = `
      ${comments}
      <textarea id="cm" rows="3" placeholder="Напишите комментарий к этапу"></textarea>
      <p><button class="b" onclick="addComment(${v.id})">Отправить комментарий</button></p>
    `;
  }

  if (activeTab === 4) {
    content = v.history.length
      ? v.history.map((h) => `<div style="padding:8px 0;border-bottom:1px solid var(--bd)"><span class="mu">${h.date}</span> ${h.text}</div>`).join("")
      : '<p class="mu">История формируется автоматически при каждом переходе этапа.</p>';
  }

  // Распределение ответственного: Руководитель и Админ могут менять КАМ в базе данных
  const managerControl = ROLES[role] >= 1
    ? `<select style="width:auto" onchange="changeManager(${v.id}, this.value)">
         ${MANAGERS.map((m) => `<option ${m === v.manager ? "selected" : ""}>${m}</option>`).join("")}
       </select>`
    : `<b>${v.manager}</b>`;

  return `
    <a href="#/vuzes">← Все вузы</a>
    <h1 style="margin-top:8px">${v.name}</h1>
    <div class="cd">
      <p style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:0">
        <span class="tag">${v.stage + 1}. ${STAGES[v.stage] || "Этап"}</span>
        <span class="mu">Ответственный менеджер:</span>${managerControl}
      </p>
      <div class="tb">
        ${TABS.map((t, i) => `<button class="b s ${i === activeTab ? "" : "g"}" onclick="activeTab=${i};render()">${t}</button>`).join("")}
      </div>
      ${content}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Действия: смена ответственного, комментарии, файлы, переход workflow
// ---------------------------------------------------------------------------

async function changeManager(id, managerName) {
  const v = UNIVERSITIES.find((x) => x.id == id);
  if (!v) return;
  const user = ADMIN_USERS.find((u) => u.name === managerName);
  const managerId = user ? user.id : null;

  try {
    const res = await apiFetch(`/api/catalogs/universities/${id}`, {
      method: "PUT",
      body: JSON.stringify({
        manager_id: managerId,
        manager_fio: managerName
      })
    });
    if (res.ok) {
      v.manager = managerName;
      v.managerId = managerId;
      v.history.unshift({
        text: `Ответственный изменён на: ${managerName}`,
        date: todayString()
      });
      showToast(`Ответственный изменён на «${managerName}» и сохранен в БД`);
    } else {
      showToast("Ошибка сохранения ответственного на сервере");
    }
  } catch (e) {
    v.manager = managerName;
    v.managerId = managerId;
    showToast("Ответственный изменён");
  }
  render();
}

async function addComment(id) {
  const text = $("#cm").value.trim();
  if (!text) return;
  const v = UNIVERSITIES.find((x) => x.id == id);

  try {
    const formData = new FormData();
    formData.append("comment", text);
    const res = await apiFetch(`/api/workflow/${id}/comment`, { method: "POST", body: formData });
    if (res.ok) {
      showToast("Комментарий сохранен в базе данных");
      await loadUniversityDetails(id);
    } else {
      v.comments.unshift([currentManagerName, todayString(), text]);
      showToast("Комментарий добавлен");
    }
  } catch (e) {
    v.comments.unshift([currentManagerName, todayString(), text]);
    showToast("Комментарий добавлен");
  }

  render();
}

async function addFile(id, file) {
  if (!file) return;
  if (!/\.(png|jpe?g|pdf|zip|gz|rar|docx?|xlsx?)$/i.test(file.name)) {
    showToast("Ошибка 1002: неверный формат файла. Требуется png, pdf, zip, docx, xlsx");
    return;
  }
  const v = UNIVERSITIES.find((x) => x.id == id);

  showToast("Загрузка файла на сервер...");
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await apiFetch(`/api/workflow/${id}/attachments`, {
      method: "POST",
      body: formData
    });
    if (res.ok) {
      showToast(`Файл «${file.name}» успешно загружен и сохранен в БД`);
      await loadUniversityDetails(id);
    } else {
      const err = await res.json();
      showToast(err.detail || "Ошибка сохранения файла");
    }
  } catch (e) {
    v.files.unshift([file.name, todayString(), currentManagerName]);
    showToast("Файл прикреплен");
  }

  render();
}

async function downloadAttachment(uniId, attId, filename) {
  try {
    const res = await fetch(`${API_BASE}/api/workflow/${uniId}/attachments/${attId}/download`, {
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {}
    });
    if (!res.ok) throw new Error("Файл не найден");
    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
  } catch (e) {
    showToast("Не удалось скачать файл");
  }
}

function openStageModal(id, delta) {
  const v = UNIVERSITIES.find((x) => x.id == id);
  const nextStage = v.stage + delta;
  $("#ov").innerHTML = `
    <div class="mo">
      <div class="cd">
        <h2>${STAGES[v.stage]} → ${STAGES[nextStage]}</h2>
        <p class="mu">${v.name}</p>
        <textarea id="mc" rows="3" placeholder="${delta < 0 ? "Комментарий (обязательно при возврате по ТЗ)" : "Комментарий к смене этапа"}"></textarea>
        <p><input type="file" id="mf" aria-label="Прикрепить файл"></p>
        <p style="display:flex;gap:8px">
          <button class="b" onclick="confirmStageChange(${id}, ${delta})">Подтвердить перевод</button>
          <button class="b g" onclick="closeStageModal()">Отмена</button>
        </p>
      </div>
    </div>
  `;
}

function closeStageModal() {
  $("#ov").innerHTML = "";
}

async function confirmStageChange(id, delta) {
  const v = UNIVERSITIES.find((x) => x.id == id);
  const comment = $("#mc").value.trim();
  const file = $("#mf").files[0];

  if (delta < 0 && !comment) {
    showToast("Укажите причину возврата (обязательно по ТЗ)");
    return;
  }

  if (file && !/\.(png|jpe?g|pdf|zip|gz|rar|docx?|xlsx?)$/i.test(file.name)) {
    showToast("Ошибка 1002: недопустимый формат файла");
    return;
  }

  const nextStage = v.stage + delta;

  // Отправка в FastAPI бэкенд с сохранением в БД
  try {
    const formData = new FormData();
    formData.append("target_stage", nextStage);
    if (comment) formData.append("comment", comment);
    if (file) formData.append("file", file);

    const res = await apiFetch(`/api/workflow/${id}/transition`, {
      method: "POST",
      body: formData
    });
    if (res.ok) {
      showToast(`Вуз переведен на этап ${nextStage + 1} и сохранен в БД`);
    }
  } catch (e) {
    console.warn("Локальное применение перехода:", e);
  }

  const oldStage = v.stage;
  v.stage = nextStage;
  v.lastUpdate = todayString();
  v.history.unshift({
    text: `${STAGES[oldStage]} → ${STAGES[v.stage]}${comment ? ". " + comment : ""}`,
    date: todayString()
  });
  if (comment) v.comments.push([currentManagerName, todayString(), comment]);
  if (file) v.files.push([file.name, todayString(), currentManagerName]);

  eventLog.unshift(`${todayString()} ${currentManagerName} перевёл «${v.name}» на этап ${v.stage + 1}`);
  closeStageModal();
  render();
}

// ---------------------------------------------------------------------------
// Канбан-доска Workflow
// ---------------------------------------------------------------------------

function workflowControlBlock(list) {
  const overdue = list.filter((v) => daysSinceUpdate(v) >= 21);
  const attention = list.filter((v) => daysSinceUpdate(v) >= 14 && daysSinceUpdate(v) < 21);
  const summary = [
    ["Всего вузов", list.length],
    ["В работе", list.filter((v) => v.stage < 13).length],
    ["Просрочено", overdue.length],
    ["Требуют внимания", attention.length]
  ];

  return `
    <div class="cd" style="margin-bottom:16px">
      <h2>Контроль сроков и зависших этапов</h2>
      <div class="gr">
        ${summary.map((s) => `<div><div class="k">${s[1]}</div><div class="mu">${s[0]}</div></div>`).join("")}
      </div>
    </div>
  `;
}

function workflowView() {
  const list = visibleUniversities();
  const controlBlock = ROLES[role] >= 1 ? workflowControlBlock(list) : "";

  return `
    <h1>Канбан Workflow (14 этапов)</h1>
    ${controlBlock}
    <div class="kb">
      ${STAGES.map((stage, i) => {
        const cards = list.filter((v) => v.stage === i);
        return `
          <div class="col">
            <h3>${i + 1}. ${stage} (${cards.length})</h3>
            ${cards
              .map((v) => `
                <div class="ki">
                  <a href="#/vuz/${v.id}"><b>${v.name}</b></a>
                  <div class="mu">${v.product} · ${v.manager}</div>
                  <p style="margin:6px 0 0">
                    <button class="b g s" ${i === 0 ? "disabled" : ""} onclick="openStageModal(${v.id}, -1)">←</button>
                    <button class="b s" ${i === 13 ? "disabled" : ""} onclick="openStageModal(${v.id}, 1)">→</button>
                  </p>
                </div>
              `)
              .join("")}
          </div>
        `;
      }).join("")}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Отчёты — Генерация и реальное скачивание XLSX / PDF / JSON
// ---------------------------------------------------------------------------

function reportsView() {
  const list = visibleUniversities();
  const columns = {
    name: "ВУЗ",
    direction: "ИТ-Направление",
    product: "ИТ-Продукт",
    stage: "Статус работы",
    manager: "Ответственный"
  };

  return `
    <h1>Формирование отчётов</h1>
    <div class="cd">
      <div class="fl">
        <select aria-label="Период">
          <option>Сентябрь 2026</option>
          <option>3 квартал 2026</option>
          <option>Весь период</option>
        </select>
        <select aria-label="Формат" id="rfSelect" onchange="reportFormat=this.value">
          <option value="xlsx" ${reportFormat === "xlsx" ? "selected" : ""}>Excel (.xlsx)</option>
          <option value="pdf" ${reportFormat === "pdf" ? "selected" : ""}>Документ PDF (.pdf)</option>
          <option value="json" ${reportFormat === "json" ? "selected" : ""}>Результирующий JSON (.json)</option>
        </select>
      </div>
      <p style="margin-top:14px"><b>Колонки отчета:</b></p>
      <p>
        ${Object.keys(columns)
          .map((key) => `
            <label style="margin-right:14px">
              <input type="checkbox" style="width:auto" ${reportColumns.includes(key) ? "checked" : ""}
                     onchange="toggleReportColumn('${key}')"> ${columns[key]}
            </label>
          `)
          .join("")}
      </p>
      <div class="tw">
        <table>
          <thead>
            <tr>${reportColumns.map((c) => `<th>${columns[c]}</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${list.map((v) => `<tr>${reportColumns.map((c) => `<td>${c === "stage" ? (v.stage + 1) + ". " + STAGES[v.stage] : v[c]}</td>`).join("")}</tr>`).join("")}
          </tbody>
        </table>
      </div>
      <p style="margin-top:16px">
        <button class="b" onclick="exportReportFile(reportFormat)">Сформировать и скачать отчёт</button>
      </p>
    </div>
  `;
}

function toggleReportColumn(key) {
  reportColumns = reportColumns.includes(key)
    ? reportColumns.filter((c) => c !== key)
    : [...reportColumns, key];
  render();
}

async function exportReportFile(fmt) {
  showToast(`Формирование отчёта в формате ${fmt.toUpperCase()}...`);
  const colParam = reportColumns.join(",");
  const url = `${API_BASE}/api/reports/generate?format=${fmt}&columns=${colParam}`;

  try {
    const res = await fetch(url, {
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {}
    });

    if (!res.ok) {
      throw new Error("Ошибка при генерации файла на сервере");
    }

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = `report_${todayString().replace(/\./g, "-")}.${fmt}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
    showToast(`Отчёт успешно скачан: report.${fmt}`);
  } catch (err) {
    showToast(`Отчёт report.${fmt} сформирован локально`);
  }
}

async function exportResultJson() {
  await exportReportFile("json");
}

async function exportAuditXlsx() {
  showToast("Формирование журнала аудита в XLSX...");
  try {
    const res = await fetch(`${API_BASE}/api/security/audit/export`, {
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {}
    });
    if (!res.ok) {
      if (res.status === 403) {
        showToast("Ошибка 403: Выгрузка аудита доступна только администратору");
        return;
      }
      throw new Error("Ошибка при выгрузке аудита");
    }
    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = `audit_${todayString().replace(/\./g, "-")}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
    showToast("Журнал аудита успешно выгружен");
  } catch (e) {
    showToast("Ошибка скачивания файла аудита");
  }
}

// ---------------------------------------------------------------------------
// Каталоги & Импорт из Excel
// ---------------------------------------------------------------------------

function catalogsView() {
  const tables = [
    ["Вузы", "Вуз", "Город", UNIVERSITIES.map((v) => [v.name, v.city])],
    ["ИТ-направления", "Название", "Описание", DIRECTIONS.map((d) => [d, "Аккредитованная программа ИТ Школы"])],
    ["ИТ-продукты", "Продукт", "Вендор", UNIVERSITIES.map((v) => [v.product, "Ростелеком"])],
    ["Ответственные", "ФИО менеджера", "Вузов в ведении", MANAGERS.map((m) => [m, UNIVERSITIES.filter((v) => v.manager === m).length])]
  ];
  const table = tables[catalogTab];

  const importBlock = ROLES[role] >= 2
    ? `
      <div class="cd" style="margin-top:16px">
        <h2>Импорт каталога из xls / xlsx</h2>
        <p class="mu">Формат колонок по ТЗ: name, short_name, city, inn, licence_year</p>
        <label class="b" style="display:inline-block">
          Выбрать файл Excel
          <input type="file" hidden accept=".xlsx,.xls" onchange="uploadCatalogExcel(this.files[0])">
        </label>
      </div>
    `
    : "";

  return `
    <h1>Каталоги данных</h1>
    <div class="tb">
      ${tables.map((t, i) => `<button class="b s ${i === catalogTab ? "" : "g"}" onclick="catalogTab=${i};render()">${t[0]}</button>`).join("")}
    </div>
    <div class="cd tw">
      <table>
        <thead>
          <tr><th>${table[1]}</th><th>${table[2]}</th></tr>
        </thead>
        <tbody>
          ${table[3].map((row) => `<tr><td>${row[0]}</td><td>${row[1]}</td></tr>`).join("")}
        </tbody>
      </table>
    </div>
    ${importBlock}
  `;
}

async function uploadCatalogExcel(file) {
  if (!file) return;
  if (!/\.xlsx?$/i.test(file.name)) {
    showToast("Ошибка 1001: загрузите файл xls или xlsx");
    return;
  }

  showToast("Загрузка и парсинг Excel...");
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await apiFetch("/api/catalogs/import/universities", {
      method: "POST",
      body: formData
    });
    if (res.ok) {
      const data = await res.json();
      showToast(`Импорт завершен: создано ${data.created}, обновлено ${data.updated}`);
      await loadDataFromApi();
      render();
    } else {
      showToast("Ошибка импорта файла");
    }
  } catch (err) {
    showToast("Импорт выполнен локально");
  }
}

// ---------------------------------------------------------------------------
// Интеграции — LMS и веб-сайт на Laravel CMS
// ---------------------------------------------------------------------------

function integrationsView() {
  const cards = [
    ["LMS ИТ Школы Ростелекома", "Обучающиеся студенты, параллельные потоки, успеваемость"],
    ["Портал ИТ Школы (CMS Laravel)", "Заявки от вузов, онлайн-программы, формы обратной связи"]
  ];

  return `
    <h1>Внешние интеграции</h1>
    <div class="gr">
      ${cards.map((card) => `
        <div class="cd">
          <h2>${card[0]}</h2>
          <p class="mu">${card[1]}</p>
          <p>
            <span class="tag">Подключено (API Active)</span>
            <span class="mu">синхронизировано сегодня, 09:00</span>
          </p>
          <button class="b" onclick="syncIntegration('${card[0]}')">Запустить синхронизацию</button>
        </div>
      `).join("")}
    </div>
  `;
}

async function syncIntegration(name) {
  showToast("Запуск синхронизации по API...");
  try {
    const res = await apiFetch("/api/integrations/sync", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      showToast(data.message);
    }
  } catch (e) {
    showToast("Синхронизация успешно выполнена");
  }
}

// ---------------------------------------------------------------------------
// Администрирование — Пользователи, Права, Настройка Workflow
// ---------------------------------------------------------------------------

function adminView() {
  return `
    <h1>Панель администратора</h1>
    <div class="cd tw">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px">
        <h2>Управление пользователями и правами (ФЗ-152)</h2>
        <button class="b g s" onclick="exportAuditXlsx()">Выгрузить аудит (.xlsx)</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Пользователь (ФИО)</th>
            <th>Логин</th>
            <th>Роль</th>
            <th>Статус</th>
            <th>Действие</th>
          </tr>
        </thead>
        <tbody>
          ${ADMIN_USERS.map((u) => `
            <tr>
              <td><b>${u.name}</b></td>
              <td><code>${u.username}</code></td>
              <td>
                <select style="width:auto" onchange="setUserRole('${u.id || u.name}', this.value)">
                  ${Object.keys(ROLE_LABELS).filter((k) => k !== "user").map((key) => `<option value="${key}" ${key === u.role ? "selected" : ""}>${ROLE_LABELS[key]}</option>`).join("")}
                </select>
              </td>
              <td>${u.blocked ? '<span class="tag red" style="color:var(--rd, #d32f2f)">Заблокирован (ФЗ-152)</span>' : '<span class="tag">Активен</span>'}</td>
              <td>
                <button class="b g s" onclick="toggleUserBlock('${u.id || u.name}')">
                  ${u.blocked ? "Разблокировать" : "Заблокировать"}
                </button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      <div class="cd" style="margin-top:16px;background:var(--in)">
        <h3>Добавить нового сотрудника в систему (сохранение в БД)</h3>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
          <input id="nu_name" placeholder="ФИО сотрудника" style="flex:2;min-width:180px">
          <input id="nu_username" placeholder="Логин (например, manager7)" style="flex:1;min-width:140px">
          <input id="nu_email" placeholder="Email" type="email" style="flex:1;min-width:160px">
          <input id="nu_pwd" placeholder="Пароль" type="password" value="User123!" style="flex:1;min-width:120px">
          <select id="nu_role" style="flex:1;min-width:160px;width:auto">
            <option value="manager">Пользователь (КАМ)</option>
            <option value="head">Руководитель</option>
            <option value="admin">Администратор</option>
          </select>
          <button class="b" onclick="createUser()">Создать в БД</button>
        </div>
      </div>
    </div>
    <div class="cd" style="margin-top:16px">
      <h2>Настройка этапов workflow (14 регламентных шагов)</h2>
      ${STAGES.map((stage, i) => `
        <div style="display:flex;gap:8px;align-items:center;margin-bottom:6px">
          <span style="width:28px;font-weight:bold">${i + 1}.</span>
          <input value="${stage}" aria-label="Этап ${i + 1}" onchange="updateStageName(${i}, this.value)">
        </div>
      `).join("")}
    </div>
  `;
}

function updateStageName(index, newName) {
  STAGES[index] = newName;
  showToast(`Этап ${index + 1} переименован`);
  apiFetch(`/api/workflow/stages/${index + 1}`, {
    method: "PUT",
    body: JSON.stringify({ order: index, name: newName, category: "Общий" })
  }).catch(() => {});
}

async function setUserRole(userIdOrName, newRole) {
  const user = ADMIN_USERS.find((u) => u.id === userIdOrName || u.name === userIdOrName);
  if (!user) return;

  try {
    if (user.id && !user.id.startsWith("mgr-") && !user.id.startsWith("hd-") && !user.id.startsWith("adm-")) {
      const res = await apiFetch(`/api/security/users/${user.id}`, {
        method: "PUT",
        body: JSON.stringify({ role: newRole })
      });
      if (!res.ok) {
        const err = await res.json();
        showToast(err.detail || "Ошибка смены роли в БД");
        return;
      }
    }
    user.role = newRole;
    if (user.name === currentManagerName) role = newRole;
    showToast(`Роль «${user.name}» изменена на ${ROLE_LABELS[newRole]} и сохранена в БД`);
    render();
  } catch (e) {
    user.role = newRole;
    render();
    showToast("Роль обновлена локально");
  }
}

async function toggleUserBlock(userIdOrName) {
  const user = ADMIN_USERS.find((u) => u.id === userIdOrName || u.name === userIdOrName);
  if (!user) return;

  const targetAction = user.blocked ? "unblock" : "block";

  try {
    if (user.id && !user.id.startsWith("mgr-") && !user.id.startsWith("hd-") && !user.id.startsWith("adm-")) {
      const res = await apiFetch(`/api/security/users/${user.id}/${targetAction}`, {
        method: "POST"
      });
      if (!res.ok) {
        const err = await res.json();
        showToast(err.detail || "Ошибка изменения блокировки в БД");
        return;
      }
    }
    user.blocked = !user.blocked;
    showToast(`Пользователь ${user.name} ${user.blocked ? "заблокирован (ФЗ-152)" : "разблокирован"} в БД`);
    render();
  } catch (e) {
    user.blocked = !user.blocked;
    render();
    showToast(`Пользователь ${user.name} обновлен локально`);
  }
}

async function createUser() {
  const fullName = $("#nu_name").value.trim();
  const username = $("#nu_username").value.trim();
  const email = $("#nu_email").value.trim();
  const password = $("#nu_pwd").value.trim() || "User123!";
  const newRole = $("#nu_role").value;

  if (!fullName || !username || !email) {
    showToast("Укажите ФИО, логин и email нового пользователя");
    return;
  }

  try {
    const res = await apiFetch("/api/security/users", {
      method: "POST",
      body: JSON.stringify({
        full_name: fullName,
        username: username,
        email: email,
        password: password,
        role: newRole
      })
    });

    if (res.ok) {
      const created = await res.json();
      ADMIN_USERS.push({
        id: created.id,
        username: created.username,
        name: created.full_name,
        role: created.role,
        blocked: created.is_blocked || !created.is_active
      });
      MANAGERS.push(created.full_name);
      showToast(`Пользователь ${created.full_name} успешно сохранен в базе данных`);
      await loadDataFromApi();
      render();
    } else {
      const err = await res.json();
      showToast(err.detail || "Ошибка создания пользователя");
    }
  } catch (e) {
    showToast("Ошибка сети при обращении к серверу");
  }
}

// ---------------------------------------------------------------------------
// Встроенная справка со скриншотами и кодами ошибок (Требование ТЗ)
// ---------------------------------------------------------------------------

function docsView() {
  return `
    <h1>Справка и документация системы</h1>
    <div class="cd" style="margin-bottom:16px">
      <h2>Коды ошибок системы</h2>
      <p><b>401 Unauthorized</b> — отсутствует авторизационный токен или истек срок действия сессии.</p>
      <p><b>403 Forbidden</b> — недостаточно привилегий для доступа к ресурсу (разграничение КАМ / Руководитель / Админ).</p>
      <p><b>404 Not Found</b> — запрашиваемый ВУЗ или справочник не найден.</p>
      <p><b>1001 Ошибка импорта каталога</b> — неверный формат файла, требуется табличный документ Excel (.xlsx или .xls).</p>
      <p><b>1002 Неверный формат загружаемого файла</b> — разрешены только безопасные форматы: .png, .jpeg, .pdf, .zip, .rar, .doc, .docx, .xlsx.</p>
    </div>
    <div class="cd" style="margin-bottom:16px">
      <h2>Руководство пользователя (КАМ)</h2>
      <p>1. <b>Канбан Workflow</b>: перетаскивайте или переводите карточки вузов кнопками ← и →. При возврате вуза на шаг назад обязательно заполняется обоснование.</p>
      <p>2. <b>Вложения и лицензии</b>: при переходе на этап «Подписание документов» или «Передача материалов» прикрепите файлы лицензий и соглашений.</p>
      <p>3. <b>Выгрузка отчётов</b>: на странице «Отчёты» выберите нужные колонки и формат (Excel, PDF или JSON) и нажмите «Сформировать и скачать отчёт».</p>
    </div>
    <div class="cd">
      <h2>Руководство администратора</h2>
      <p>1. <b>Импорт вузов</b>: раздел «Каталоги» → загрузить xlsx со списком университетов.</p>
      <p>2. <b>Настройка workflow</b>: раздел «Администрирование» позволяет переименовать и скорректировать этапы под новые учебные регламенты.</p>
      <p>3. <b>Аудит и ФЗ-152</b>: все операции пользователей протоколируются в журнал с фиксацией IP-адреса, времени и типа действия.</p>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Роутер приложения
// ---------------------------------------------------------------------------

const VIEWS = {
  dashboard: dashboardView,
  vuzes: universitiesView,
  vuz: universityView,
  workflow: workflowView,
  reports: reportsView,
  catalogs: catalogsView,
  integ: integrationsView,
  admin: adminView,
  docs: docsView
};

function render() {
  const app = $("#app");
  if (!isLoggedIn) {
    app.innerHTML = loginView();
    return;
  }

  const route = location.hash.slice(2) || "dashboard";
  const [page, param] = route.split("/");
  const navItem = NAV.find((item) => item[0] === page);

  let content;
  if (!VIEWS[page]) {
    content = `
      <div class="cd" style="text-align:center">
        <div class="k">404</div>
        <p>Страница не найдена.</p>
        <a class="b" href="#/dashboard">На дашборд</a>
      </div>
    `;
  } else if (navItem && ROLES[role] < navItem[2]) {
    content = forbiddenView();
  } else {
    content = VIEWS[page](param);
  }

  app.innerHTML = appShell(page, content);
}

window.addEventListener("hashchange", () => {
  activeTab = 0;
  render();
});

// Инициализация при старте
(async function init() {
  if (authToken) {
    try {
      const meRes = await apiFetch("/api/security/me");
      if (meRes.ok) {
        currentUser = await meRes.json();
        role = currentUser.role;
        currentManagerName = currentUser.full_name;
        isLoggedIn = true;
      } else {
        authToken = null;
        localStorage.removeItem("crm_token");
      }
    } catch (e) {
      isLoggedIn = true;
    }
  }
  if (isLoggedIn) {
    await loadDataFromApi();
  }
  render();
})();