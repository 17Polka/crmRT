    // примеры

    const STAGES = [
      "Поиск контактов",
      "Уточнение программ",
      "Встреча",
      "Обмен документами",
      "Корректировка документов",
      "Подписание",
      "Передача материалов и лицензий",
      "Внедрение продукта",
      "Обучение преподавателей",
      "Актуализация программы",
      "Ведение занятий",
      "Актуализация документации",
      "Повышение квалификации",
      "Контроль исполнения"
    ];

    const DIRECTIONS = [
      "Тест направление 1",
      "Тест направление 2",
      "Тест направление 3",
      "Тест направление 4",
      "Тест направление 5"
    ];

    const MANAGERS = ["Тест 1", "Тест 2", "Тест 3"];

    const ADMIN_USERS = [
      { name: "Тест 1", role: "user", blocked: false },
      { name: "Тест 2", role: "head", blocked: false },
      { name: "Тест 3", role: "admin", blocked: false }
    ];

    const ROLES = { user: 0, head: 1, admin: 2 };
    const ROLE_LABELS = {
      user: "Пользователь",
      head: "Руководитель",
      admin: "Администратор"
    };

    const CREATED_DATE = "01.09.2026";

    const UNIVERSITIES_BASE = [
      ["Тест вуз 1", "Тест город", 0, "Тест продукт", 6, "14.09.2026"],
      ["Тест вуз 2", "Тест город", 1, "Тест продукт", 3, "23.09.2026"],
      ["Тест вуз 3", "Тест город", 2, "Тест продукт", 10, "01.09.2026"],
      ["Тест вуз 4", "Тест город", 0, "Тест продукт", 8, "05.09.2026"],
      ["Тест вуз 5", "Тест город", 3, "Тест продукт", 1, "01.09.2026"],
      ["Тест вуз 6", "Тест город", 4, "Тест продукт", 12, "20.09.2026"],
      ["Тест вуз 7", "Тест город", 1, "Тест продукт", 5, "12.09.2026"],
      ["Тест вуз 8", "Тест город", 2, "Тест продукт", 13, "01.09.2026"]
    ];

    const UNIVERSITIES = UNIVERSITIES_BASE.map((row, index) => {
      const lastUpdate = row[5];
      const history = lastUpdate === CREATED_DATE
        ? [{ text: "Карточка создана", date: CREATED_DATE }]
        : [
            { text: "Смена этапа", date: lastUpdate },
            { text: "Карточка создана", date: CREATED_DATE }
          ];

      return {
        id: index + 1,
        name: row[0],
        city: row[1],
        direction: DIRECTIONS[row[2]],
        product: row[3],
        stage: row[4],
        manager: MANAGERS[index % 3],
        licenceYear: 2027 + index % 3,
        contract: "ТЕСТ-" + (101 + index),
        lastUpdate: lastUpdate,
        history: history,
        files: [],
        comments: []
      };
    });

    let currentManagerName = MANAGERS[0];
    let role = "user";
    let isLoggedIn = false;
    let activeTab = 0;
    let query = "";
    let directionFilter = "";
    let inviteMode = 0;
    let reportColumns = ["Вуз", "Направление", "Продукт", "Статус", "Ответственный"];
    let reportFormat = "xlsx";
    let catalogTab = 0;

    let eventLog = [
      "23.09 10:02 Тест 1 перевёл «Тест вуз 1» на этап 7",
      "22.09 16:40 Импорт каталога: тест",
      "22.09 09:15 Тест 2 вошёл в систему"
    ];

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

    // настройка и вспомогательные программы

    const $ = (selector) => document.querySelector(selector);

    function visibleUniversities() {
      return role === "user"
        ? UNIVERSITIES.filter((v) => v.manager === currentManagerName)
        : UNIVERSITIES;
    }

    function daysSinceUpdate(v) {
      const [day, month, year] = v.lastUpdate.split(".").map(Number);
      const lastDate = new Date(year, month - 1, day);
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

    // общие

    function loginView() {
      return `
        <div class="cd lg">
          <a onclick="location.hash='';">← Назад</a>
          <div class="logo" style="justify-content:center;margin:12px 0">
            <span>Тест<small>ИТ Школа</small></span>
          </div>
          <h1>Войдите, чтобы продолжить работу</h1>
          <input id="em" type="email" placeholder="Электронная почта" aria-label="Электронная почта">
          <input id="pw" type="password" placeholder="Пароль" aria-label="Пароль">
          ${inviteMode ? '<input placeholder="Код приглашения" aria-label="Код приглашения">' : ''}
          <p style="text-align:right;margin:-4px 0 12px"><a>Забыли пароль?</a></p>
          <button class="b" style="width:100%" onclick="submitLogin()">Войти</button>
          <p><a onclick="inviteMode=1;render()">Ввести код приглашения</a></p>
          <p><a class="mu">Сообщить об ошибке</a></p>
          <p class="mu" style="font-size:12px">Вход выполняется через Keycloak (SSO)</p>
        </div>
      `;
    }

    function submitLogin() {
      if (!$("#em").value) {
        showToast("Введите электронную почту");
        return;
      }
      isLoggedIn = true;
      location.hash = "#/dashboard";
      render();
    }

    function appShell(page, content) {
      return `
        <header>
          <div class="logo">
            <span>Тест<small>ИТ Школа · CRM</small></span>
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
          <select style="width:auto" aria-label="Текущий пользователь" onchange="switchAccount(this.value)">
            ${ADMIN_USERS
              .filter((u) => !u.blocked)
              .map((u) => `<option value="${u.name}" ${u.name === currentManagerName ? "selected" : ""}>${u.name} (${ROLE_LABELS[u.role]})</option>`)
              .join("")}
          </select>
          <button class="b g s" onclick="logout()">Выйти</button>
        </header>
        <main>${content}</main>
      `;
    }

    function switchAccount(name) {
      const user = ADMIN_USERS.find((u) => u.name === name);
      if (!user) return;
      currentManagerName = user.name;
      role = user.role;
      render();
    }

    function logout() {
      isLoggedIn = false;
      render();
    }

    function forbiddenView() {
      return `
        <div class="cd" style="text-align:center">
          <div class="k">403</div>
          <h2>Нет доступа</h2>
          <p class="mu">Этот раздел доступен другой роли. Обратитесь к администратору.</p>
          <a class="b" href="#/dashboard">На дашборд</a>
        </div>
      `;
    }

    //дашборд

    function dashboardView() {
      const list = visibleUniversities();
      const stageCounts = STAGES.map((_, i) => list.filter((v) => v.stage === i).length);
      const maxCount = Math.max(...stageCounts, 1);
      const attention = list.filter((v) => v.stage < 3 || v.stage === 13).length;
      const averageStage = list.length ? Math.round(list.reduce((sum, v) => sum + v.stage + 1, 0) / list.length) : 0;

      return `
        <h1>Дашборд</h1>
        <div class="fl">
          <select aria-label="Период">
            <option>Сентябрь 2026</option>
            <option>3 квартал 2026</option>
            <option>2026 год</option>
          </select>
          <select aria-label="Направление">
            <option>Все направления</option>
            ${DIRECTIONS.map((d) => `<option>${d}</option>`).join("")}
          </select>
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
            <div class="k">${attention}</div>
            <div class="mu">требуют внимания</div>
          </div>
          <div class="cd">
            <div class="k">${averageStage}</div>
            <div class="mu">средний этап из 14</div>
          </div>
        </div>
        <div class="cd" style="margin-top:16px">
          <h2>Вузы по этапам workflow</h2>
          <div class="bar" role="img" aria-label="Диаграмма вузов по этапам">
            ${stageCounts
              .map((c, i) => `<div title="${STAGES[i]}"><i style="height:${c / maxCount * 130}px"></i>${i + 1}</div>`)
              .join("")}
          </div>
          <p style="margin:12px 0 0">
            <button class="b g s" onclick="showToast('Диаграмма сохранена в png')">Экспорт png</button>
            <button class="b g s" onclick="showToast('Диаграмма сохранена в pdf')">Экспорт pdf</button>
          </p>
        </div>
        <div class="cd" style="margin-top:16px">
          <h2>Последние события</h2>
          ${eventLog
            .map((line) => `<div style="padding:6px 0;border-bottom:1px solid var(--bd)">${line}</div>`)
            .join("")}
        </div>
      `;
    }

    // вузы

    function universityRows() {
      let list = visibleUniversities();

      if (directionFilter) {
        list = list.filter((v) => v.direction === directionFilter);
      }
      if (query) {
        list = list.filter((v) =>
          (v.name + v.city + v.product).toLowerCase().includes(query.toLowerCase())
        );
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
            <td><span class="tag">${v.stage + 1}. ${STAGES[v.stage]}</span></td>
            <td>${v.manager}</td>
            <td>${v.licenceYear}</td>
          </tr>
        `)
        .join("");
    }

    function refreshTable() {
      $("#tb").innerHTML = universityRows();
    }

    function setDirectionFilter(value) {
      directionFilter = value;
      refreshTable();
    }

    function universitiesView() {
      return `
        <h1>Вузы</h1>
        <div class="fl">
          <input placeholder="Поиск по вузу, городу, продукту" value="${query}"
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
                <th>Этап</th>
                <th>Ответственный</th>
                <th>Лицензия до</th>
              </tr>
            </thead>
            <tbody id="tb">${universityRows()}</tbody>
          </table>
        </div>
      `;
    }

    // карточки вузы

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

      const TABS = ["Общее", "Workflow", "Документы", "Комментарии", "История"];
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
          <p>
            <button class="b g" ${v.stage === 0 ? "disabled" : ""} onclick="openStageModal(${v.id}, -1)">Назад по этапу</button>
            <button class="b" ${v.stage === 13 ? "disabled" : ""} onclick="openStageModal(${v.id}, 1)">Следующий этап</button>
          </p>
        `;
      }

      if (activeTab === 2) {
        const fileList = v.files.length
          ? v.files
              .map((f) => `
                <div style="padding:8px 0;border-bottom:1px solid var(--bd)">
                  ${f[0]} <span class="mu">· ${f[1]} · ${f[2]}</span>
                </div>
              `)
              .join("")
          : '<p class="mu">Файлов нет. Приложите документ при переходе на следующий этап.</p>';

        content = `
          ${fileList}
          <p>
            <label class="b g" style="display:inline-block">
              Загрузить файл
              <input type="file" hidden onchange="addFile(${v.id}, this.files[0])">
            </label>
          </p>
          <p class="mu" style="font-size:13px">png, jpeg, pdf, zip, gzip, rar, doc, docx, xls, xlsx</p>
        `;
      }

      if (activeTab === 3) {
        const comments = v.comments.length
          ? v.comments
              .map((x) => `
                <div style="padding:8px 0;border-bottom:1px solid var(--bd)">
                  <b>${x[0]}</b> <span class="mu">${x[1]}</span><br>${x[2]}
                </div>
              `)
              .join("")
          : '<p class="mu">Комментариев пока нет.</p>';

        content = `
          ${comments}
          <textarea id="cm" rows="3" placeholder="Напишите комментарий"></textarea>
          <p><button class="b" onclick="addComment(${v.id})">Отправить</button></p>
        `;
      }

      if (activeTab === 4) {
        content = v.history
          .map((h) => `
            <div style="padding:8px 0;border-bottom:1px solid var(--bd)">
              <span class="mu">${h.date}</span> ${h.text}
            </div>
          `)
          .join("");
      }

      const managerControl = ROLES[role] >= 1
        ? `<select style="width:auto" onchange="changeManager(${v.id}, this.value)">
             ${MANAGERS.map((m) => `<option ${m === v.manager ? "selected" : ""}>${m}</option>`).join("")}
           </select>`
        : v.manager;

      return `
        <a href="#/vuzes">← Все вузы</a>
        <h1 style="margin-top:8px">${v.name}</h1>
        <div class="cd">
          <p style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:0">
            <span class="tag">${v.stage + 1}. ${STAGES[v.stage]}</span>
            <span class="mu">Ответственный:</span>${managerControl}
          </p>
          <div class="tb">
            ${TABS.map((t, i) => `
              <button class="b s ${i === activeTab ? "" : "g"}" onclick="activeTab=${i};render()">${t}</button>
            `).join("")}
          </div>
          ${content}
        </div>
      `;
    }

    // действия

    function changeManager(id, manager) {
      const v = UNIVERSITIES.find((x) => x.id == id);
      v.history.unshift({ text: `Ответственный: ${v.manager} → ${manager}`, date: todayString() });
      v.manager = manager;
      showToast("Ответственный изменён");
    }

    function addComment(id) {
      const text = $("#cm").value.trim();
      if (!text) return;
      UNIVERSITIES.find((x) => x.id == id).comments.push([
        role === "user" ? currentManagerName : ROLE_LABELS[role],
        todayString(),
        text
      ]);
      render();
    }

    function addFile(id, file) {
      if (!file) return;
      if (!/\.(png|jpe?g|pdf|zip|gz|rar|docx?|xlsx?)$/i.test(file.name)) {
        showToast("Ошибка 1002: неверный формат файла");
        return;
      }
      UNIVERSITIES.find((x) => x.id == id).files.push([file.name, todayString(), currentManagerName]);
      render();
    }

    function openStageModal(id, delta) {
      const v = UNIVERSITIES.find((x) => x.id == id);
      const nextStage = v.stage + delta;
      $("#ov").innerHTML = `
        <div class="mo">
          <div class="cd">
            <h2>${STAGES[v.stage]} → ${STAGES[nextStage]}</h2>
            <p class="mu">${v.name}</p>
            <textarea id="mc" rows="3"
                      placeholder="${delta < 0 ? "Комментарий (обязательно при возврате)" : "Комментарий"}"></textarea>
            <p><input type="file" id="mf"></p>
            <p style="display:flex;gap:8px">
              <button class="b" onclick="confirmStageChange(${id}, ${delta})">Подтвердить</button>
              <button class="b g" onclick="closeStageModal()">Отмена</button>
            </p>
          </div>
        </div>
      `;
    }

    function closeStageModal() {
      $("#ov").innerHTML = "";
    }

    function confirmStageChange(id, delta) {
      const v = UNIVERSITIES.find((x) => x.id == id);
      const comment = $("#mc").value.trim();
      const file = $("#mf").files[0];

      if (delta < 0 && !comment) {
        showToast("Укажите комментарий при возврате");
        return;
      }
      if (file) {
        if (!/\.(png|jpe?g|pdf|zip|gz|rar|docx?|xlsx?)$/i.test(file.name)) {
          showToast("Ошибка 1002: неверный формат файла");
          return;
        }
        v.files.push([file.name, todayString(), currentManagerName]);
      }

      const oldStage = v.stage;
      v.stage += delta;
      v.lastUpdate = todayString();
      v.history.unshift({
        text: `${STAGES[oldStage]} → ${STAGES[v.stage]}${comment ? ". " + comment : ""}`,
        date: todayString()
      });
      if (comment) {
        v.comments.push([currentManagerName, todayString(), comment]);
      }
      eventLog.unshift(`${todayString()} ${currentManagerName} перевёл «${v.name}» на этап ${v.stage + 1}`);

      closeStageModal();
      showToast("Этап обновлён");
      render();
    }

    // канбан

    function workflowControlBlock(list) {
      const overdue = list.filter((v) => daysSinceUpdate(v) >= 21);
      const attention = list.filter((v) => daysSinceUpdate(v) >= 14 && daysSinceUpdate(v) < 21);
      const stuck = overdue.filter((v) => v.stage <= 2);

      const summary = [
        ["Всего вузов", list.length],
        ["В работе", list.filter((v) => v.stage < 13).length],
        ["Просрочено", overdue.length],
        ["Зависло", stuck.length],
        ["Требуют внимания", attention.length]
      ];

      const problems = list
        .filter((v) => daysSinceUpdate(v) >= 14)
        .sort((a, b) => daysSinceUpdate(b) - daysSinceUpdate(a))
        .map((v) => {
          const days = daysSinceUpdate(v);
          const badge = days >= 21 ? (v.stage <= 2 ? "зависло" : "просрочено") : "требует внимания";
          const red = days >= 21 ? ' class="tag red"' : ' class="tag"';
          return `
            <div class="ki" style="display:flex;justify-content:space-between;gap:10px;align-items:center">
              <div>
                <a href="#/vuz/${v.id}"><b>${v.name}</b></a>
                <div class="mu">${STAGES[v.stage]} · ${v.manager}</div>
              </div>
              <span${red}>${badge}, ${days} дн.</span>
            </div>
          `;
        })
        .join("");

      const byManager = MANAGERS.map((m) => {
        const own = list.filter((v) => v.manager === m);
        const bad = own.filter((v) => daysSinceUpdate(v) >= 14).length;
        return `${m}: ${own.length} вузов, проблемных ${bad}`;
      });

      return `
        <div class="cd" style="margin-bottom:16px">
          <h2>Контроль workflow</h2>
          <div class="gr">
            ${summary.map((s) => `<div><div class="k">${s[1]}</div><div class="mu">${s[0]}</div></div>`).join("")}
          </div>
          <p class="mu" style="margin:14px 0 4px">${byManager.join(" · ")}</p>
          <h2 style="margin-top:14px">Просрочки и зависшие</h2>
          ${problems
            ? `<div class="kb" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr))">${problems}</div>`
            : '<p class="mu">Просрочек нет, всё в работе.</p>'}
        </div>
      `;
    }

    function workflowView() {
      const list = visibleUniversities();
      const controlBlock = ROLES[role] >= 1 ? workflowControlBlock(list) : "";

      return `
        <h1>Workflow взаимодействия</h1>
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
                        <button class="b g s" ${i === 0 ? "disabled" : ""}
                                onclick="openStageModal(${v.id}, -1)" aria-label="Назад">←</button>
                        <button class="b s" ${i === 13 ? "disabled" : ""}
                                onclick="openStageModal(${v.id}, 1)" aria-label="Вперёд">→</button>
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

    // отчеты

    function reportsView() {
      const list = visibleUniversities();
      const columns = {
        "Вуз": (v) => v.name,
        "Направление": (v) => v.direction,
        "Продукт": (v) => v.product,
        "Статус": (v) => STAGES[v.stage],
        "Ответственный": (v) => v.manager
      };

      return `
        <h1>Отчёты</h1>
        <div class="cd">
          <div class="fl">
            <select aria-label="Период">
              <option>Сентябрь 2026</option>
              <option>3 квартал 2026</option>
            </select>
            <select aria-label="Направление">
              <option>Все направления</option>
              ${DIRECTIONS.map((d) => `<option>${d}</option>`).join("")}
            </select>
            <select aria-label="Формат" onchange="setReportFormat(this.value)">
              <option ${reportFormat === "xls" ? "selected" : ""}>xls</option>
              <option ${reportFormat === "xlsx" ? "selected" : ""}>xlsx</option>
              <option ${reportFormat === "pdf" ? "selected" : ""}>pdf</option>
            </select>
          </div>
          <p>
            ${Object.keys(columns)
              .map((key) => `
                <label style="margin-right:14px">
                  <input type="checkbox" style="width:auto" ${reportColumns.includes(key) ? "checked" : ""}
                         onchange="toggleReportColumn('${key}')"> ${key}
                </label>
              `)
              .join("")}
          </p>
          <div class="tw">
            <table>
              <thead>
                <tr>${reportColumns.map((c) => `<th>${c}</th>`).join("")}</tr>
              </thead>
              <tbody>
                ${list
                  .map((v) => `<tr>${reportColumns.map((c) => `<td>${columns[c](v)}</td>`).join("")}</tr>`)
                  .join("")}
              </tbody>
            </table>
          </div>
          <p>
            <button class="b" onclick="showToast('Отчёт report.' + reportFormat + ' сформирован')">Выгрузить отчёт</button>
          </p>
        </div>
      `;
    }

    function setReportFormat(value) {
      reportFormat = value;
    }

    function toggleReportColumn(name) {
      reportColumns = reportColumns.includes(name)
        ? reportColumns.filter((c) => c !== name)
        : [...reportColumns, name];
      render();
    }

    // каталог

    function catalogsView() {
      const tables = [
        ["Вузы", "Вуз", "Город", UNIVERSITIES.map((v) => [v.name, v.city])],
        ["ИТ-направления", "Название", "Вузов", DIRECTIONS.map((d) => [d, UNIVERSITIES.filter((v) => v.direction === d).length])],
        ["ИТ-продукты", "Продукт", "Направление", UNIVERSITIES.map((v) => [v.product, v.direction])],
        ["Ответственные", "ФИО", "Вузов", MANAGERS.map((m) => [m, UNIVERSITIES.filter((v) => v.manager === m).length])]
      ];
      const table = tables[catalogTab];

      const importBlock = ROLES[role] >= 2
        ? `
          <div class="cd" style="margin-top:16px">
            <h2>Импорт из xls / xlsx</h2>
            <p class="mu">Поля: Название ВУЗа, Вендор, ПО, Номер договора, Подписание лицензии,
              Срок действия лицензии, Статус по передаче, ФИО менеджера, Ответственные от ВУЗа, Комментарий</p>
            <label class="b" style="display:inline-block">
              Выбрать файл
              <input type="file" hidden onchange="importCatalogFile(this.files[0])">
            </label>
          </div>
        `
        : "";

      return `
        <h1>Каталоги</h1>
        <div class="tb">
          ${tables
            .map((t, i) => `<button class="b s ${i === catalogTab ? "" : "g"}" onclick="catalogTab=${i};render()">${t[0]}</button>`)
            .join("")}
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

    function importCatalogFile(file) {
      if (!file) return;
      if (!/\.xlsx?$/i.test(file.name)) {
        showToast("Ошибка 1001: загрузите файл xls или xlsx");
        return;
      }
      eventLog.unshift(`${todayString()} Импорт каталога: ${file.name}`);
      showToast("Импорт выполнен: файл принят");
    }

    // интегрвция

    function integrationsView() {
      const cards = [
        ["LMS тест", "Обучающиеся, потоки, заявки"],
        ["Сайт (Laravel CMS)", "Вузы, программы, заявки"]
      ];

      return `
        <h1>Интеграции</h1>
        <div class="gr">
          ${cards
            .map((card) => `
              <div class="cd">
                <h2>${card[0]}</h2>
                <p class="mu">${card[1]}</p>
                <p>
                  <span class="tag">Подключено</span>
                  <span class="mu">синхронизация сегодня, 09:00</span>
                </p>
                <button class="b" onclick="syncIntegration('${card[0]}')">Синхронизировать</button>
              </div>
            `)
            .join("")}
        </div>
      `;
    }

    function syncIntegration(name) {
      showToast("Синхронизация запущена");
      eventLog.unshift(todayString() + " Синхронизация: " + name);
    }

    // администрорование

    function adminView() {
      return `
        <h1>Администрирование</h1>
        <div class="cd tw">
          <h2>Пользователи</h2>
          <table>
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Роль</th>
                <th>Статус</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${ADMIN_USERS
                .map((u) => `
                  <tr>
                    <td>${u.name}</td>
                    <td>
                      <select style="width:auto" onchange="setUserRole('${u.name}', this.value)">
                        ${Object.keys(ROLE_LABELS)
                          .map((key) => `<option value="${key}" ${key === u.role ? "selected" : ""}>${ROLE_LABELS[key]}</option>`)
                          .join("")}
                      </select>
                    </td>
                    <td>${u.blocked ? '<span class="tag red">Заблокирован</span>' : '<span class="tag">Активен</span>'}</td>
                    <td>
                      <button class="b g s" onclick="toggleUserBlock('${u.name}')">
                        ${u.blocked ? "Разблокировать" : "Заблокировать"}
                      </button>
                    </td>
                  </tr>
                `)
                .join("")}
            </tbody>
          </table>
          <p style="margin-top:14px">
            <input id="nu" placeholder="Имя нового пользователя" aria-label="Имя нового пользователя" style="max-width:280px">
            <select id="nr" style="width:auto">
              ${Object.keys(ROLE_LABELS)
                .map((key) => `<option value="${key}">${ROLE_LABELS[key]}</option>`)
                .join("")}
            </select>
            <button class="b" onclick="createUser()">Добавить пользователя</button>
          </p>
        </div>
        <div class="cd" style="margin-top:16px">
          <h2>Этапы workflow</h2>
          ${STAGES
            .map((stage, i) => `
              <input value="${stage}" style="margin-bottom:6px" aria-label="Этап ${i + 1}"
                     onchange="STAGES[${i}]=this.value;showToast('Этап переименован')">
            `)
            .join("")}
        </div>
        <div class="cd" style="margin-top:16px">
          <h2>Журнал аудита</h2>
          ${eventLog
            .map((line) => `<div style="padding:6px 0;border-bottom:1px solid var(--bd)">${line}</div>`)
            .join("")}
        </div>
      `;
    }

    function setUserRole(name, newRole) {
      const user = ADMIN_USERS.find((u) => u.name === name);
      if (!user) return;
      user.role = newRole;
      if (name === currentManagerName) {
        role = newRole;
      }
      eventLog.unshift(`${todayString()} ${currentManagerName}: изменена роль ${name} → ${ROLE_LABELS[newRole]}`);
      render();
    }

    function toggleUserBlock(name) {
      const user = ADMIN_USERS.find((u) => u.name === name);
      if (!user) return;
      user.blocked = !user.blocked;

      if (user.blocked && name === currentManagerName) {
        const next = ADMIN_USERS.find((u) => !u.blocked);
        if (next) {
          currentManagerName = next.name;
          role = next.role;
        }
      }

      eventLog.unshift(`${todayString()} ${currentManagerName}: пользователь ${name} ${user.blocked ? "заблокирован" : "разблокирован"}`);
      render();
    }

    function createUser() {
      const name = $("#nu").value.trim();
      if (!name) {
        showToast("Укажите имя пользователя");
        return;
      }
      if (ADMIN_USERS.some((u) => u.name === name)) {
        showToast("Такой пользователь уже есть");
        return;
      }

      const newRole = $("#nr").value;
      ADMIN_USERS.push({ name: name, role: newRole, blocked: false });
      MANAGERS.push(name);
      eventLog.unshift(`${todayString()} ${currentManagerName}: создан пользователь ${name} (${ROLE_LABELS[newRole]})`);
      render();
    }

    // справка

    function docsView() {
      const sections = [
        ["Руководство пользователя", "Как найти вуз, сменить этап, добавить файл и выгрузить отчёт."],
        ["Руководство администратора", "Как загрузить каталог, настроить workflow, права и интеграции."],
        ["Коды ошибок", "401 нет входа · 403 нет доступа · 404 не найдено · 1001 ошибка импорта · 1002 неверный формат файла"]
      ];

      return `
        <h1>Справка</h1>
        <div class="gr">
          ${sections
            .map((s) => `
              <div class="cd">
                <h2>${s[0]}</h2>
                <p class="mu">${s[1]}</p>
              </div>
            `)
            .join("")}
        </div>
      `;
    }

    // роутер

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

    render();
  