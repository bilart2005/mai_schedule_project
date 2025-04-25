let token = "";
let allGroups = [];

// Авторизация
function login() {
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;
  axios.post('/login', { email, password })
    .then(res => {
      token = res.data.access_token;
      document.getElementById('loginStatus').innerText = 'Успешный вход';
    })
    .catch(() => alert('Ошибка входа'));
}

// Загрузка расписания
function loadSchedule() {
  const group = document.getElementById('groupInput').value;
  const week = document.getElementById('weekInput').value;
  if (!group || !week) return alert('Укажите группу и неделю');

  axios.get(`/schedule?group=${group}&week=${week}`)
    .then(res => {
      const tbody = document.getElementById('scheduleBody');
      tbody.innerHTML = '';
      res.data.forEach(item => {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td>${item.day}</td>
          <td>${item.start_time} - ${item.end_time}</td>
          <td>✈️ ${item.subject}</td>
          <td>${item.teacher}</td>
          <td>${item.room}</td>
          <td><button class='btn btn-sm btn-danger' onclick='deleteSchedule(${item.id})'>Удалить</button></td>
        `;
        tbody.appendChild(row);
      });
    });
}

// Удаление занятия
function deleteSchedule(id) {
  axios.delete(`/schedule/${id}`, {
    headers: { Authorization: `Bearer ${token}` }
  }).then(() => loadSchedule());
}

// Показать/скрыть форму добавления
function showAddForm() {
  document.getElementById('formBlock').classList.remove('d-none');
}
function hideForm() {
  document.getElementById('formBlock').classList.add('d-none');
}

// Добавление занятия
function submitForm() {
  const payload = {
    group_name: document.getElementById('formGroup').value,
    week: +document.getElementById('formWeek').value,
    day: document.getElementById('formDay').value,
    start_time: document.getElementById('formStart').value,
    end_time: document.getElementById('formEnd').value,
    subject: document.getElementById('formSubject').value,
    teacher: document.getElementById('formTeacher').value,
    room: document.getElementById('formRoom').value,
    event_type: document.getElementById('formType').value || 'разовое',
    recurrence_pattern: document.getElementById('formPattern').value || ''
  };
  axios.post('/schedule', payload, {
    headers: { Authorization: `Bearer ${token}` }
  }).then(() => {
    hideForm();
    loadSchedule();
  });
}

// Синхронизация с Google Calendar
function syncCalendar() {
  const group = document.getElementById('groupInput').value;
  if (!group) return alert('Укажите группу');
  axios.post('/calendar/sync_group', { group }, {
    headers: { Authorization: `Bearer ${token}` }
  }).then(() => alert('Синхронизация завершена'));
}

// При загрузке страницы: автозаполнение групп и генерация недель
window.addEventListener('DOMContentLoaded', () => {
  axios.get('/groups').then(res => {
    allGroups = res.data;
    $("#groupInput").autocomplete({ source: allGroups });
  });
  const weekSelect = document.getElementById("weekInput");
  for (let i = 1; i <= 19; i++) {
    const opt = document.createElement("option");
    opt.value = i;
    opt.text = i;
    weekSelect.appendChild(opt);
  }
});
