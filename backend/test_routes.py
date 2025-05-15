import os
import sys

# Вставляем папку "backend" в sys.path, чтобы Python увидел подпакеты api/ и database/
HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import unittest
import datetime

# Импортируем нашу логику создания БД
from database import create_tables, DB_PATH
# Импортируем Flask-приложение из api.routes
import api.routes as routes

# Заменяем реальные Google API на заглушки
routes.sync_group_to_calendar = lambda group: None
routes.sync_events_in_date_range = lambda start, end: None

app = routes.app
app.config['TESTING'] = True

# Перед каждым запуском тестов удаляем старую БД, чтобы всё было с нуля
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
create_tables()


class RoutesTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def register(self, email, pwd, role=None):
        data = {'email': email, 'password': pwd}
        if role:
            data['role'] = role
        return self.client.post('/register', json=data)

    def login(self, email, pwd):
        resp = self.client.post('/login', json={'email': email, 'password': pwd})
        if resp.status_code == 200:
            return resp.get_json().get('access_token')
        return None

    def test_groups_empty(self):
        r = self.client.get('/groups')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), [])

    def test_schedule_get(self):
        # без параметров — 400
        r0 = self.client.get('/schedule')
        self.assertEqual(r0.status_code, 400)
        # с правильными, но пустыми — []
        r1 = self.client.get('/schedule?group=FOO&week=1')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.get_json(), [])

    def test_rooms_endpoints(self):
        r1 = self.client.get('/occupied_rooms')
        r2 = self.client.get('/free_rooms')
        self.assertEqual(r1.status_code, 200)
        self.assertIsInstance(r1.get_json(), list)
        self.assertEqual(r2.status_code, 200)
        self.assertIsInstance(r2.get_json(), list)

    def test_schedule_post_auth(self):
        # без токена — 401
        r0 = self.client.post('/schedule', json={})
        self.assertEqual(r0.status_code, 401)

        # студент — 403
        self.register('stu@x.com', 'pw')
        tok = self.login('stu@x.com', 'pw')
        r1 = self.client.post(
            '/schedule',
            headers={'Authorization': f'Bearer {tok}'},
            json={
                'group_name':'G','week':1,'day':'Пн',
                'start_time':'09:00','end_time':'10:30',
                'subject':'S','teacher':'T','room':'R',
                'event_type':'разовое','recurrence_pattern':''
            }
        )
        self.assertEqual(r1.status_code, 403)

        # преподаватель — 201
        self.register('t@x.com','pw','teacher')
        tok = self.login('t@x.com','pw')
        r2 = self.client.post(
            '/schedule',
            headers={'Authorization': f'Bearer {tok}'},
            json={
                'group_name':'G1','week':2,'day':'Вт, 10.06.2025',
                'start_time':'10:00','end_time':'11:30',
                'subject':'Math','teacher':'Dr','room':'R2',
                'event_type':'разовое','recurrence_pattern':''
            }
        )
        self.assertEqual(r2.status_code, 201)

    def test_calendar_sync(self):
        # /calendar/sync_group без токена — 401
        r0 = self.client.post('/calendar/sync_group', json={'group':'G1'})
        self.assertEqual(r0.status_code, 401)

        # преподаватель может синхронизировать
        self.register('c@x.com','pw','teacher')
        tok = self.login('c@x.com','pw')
        r1 = self.client.post(
            '/calendar/sync_group',
            headers={'Authorization': f'Bearer {tok}'},
            json={'group':'G1'}
        )
        self.assertEqual(r1.status_code, 200)

        # /calendar/sync_range без дат — 400
        r2 = self.client.post(
            '/calendar/sync_range',
            headers={'Authorization': f'Bearer {tok}'},
            json={}
        )
        self.assertEqual(r2.status_code, 400)

        # с валидными датами — 200
        today = datetime.date.today().strftime('%d.%m.%Y')
        r3 = self.client.post(
            '/calendar/sync_range',
            headers={'Authorization': f'Bearer {tok}'},
            json={'start_date': today, 'end_date': today}
        )
        self.assertEqual(r3.status_code, 200)


if __name__ == '__main__':
    unittest.main(verbosity=2)
