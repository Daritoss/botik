# Инструкция по подключению базы данных MS SQL Server к боту

## 1. Установка необходимых компонентов

### 1.1 Установка Python библиотеки pyodbc
```bash
pip install pyodbc
```

### 1.2 Установка ODBC Driver для SQL Server

**Windows:**
Скачайте и установите [Microsoft ODBC Driver for SQL Server](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

Рекомендуется: ODBC Driver 17 или 18 for SQL Server

**Проверка установленных драйверов:**
```python
import pyodbc
print(pyodbc.drivers())
```

## 2. Создание базы данных

### 2.1 Открыть SQL Server Management Studio (SSMS)

### 2.2 Выполнить скрипт database_setup.sql
1. Откройте файл `database_setup.sql` в SSMS
2. Нажмите F5 или кнопку "Execute"
3. Убедитесь, что база данных `VKBotDatabase` создана

### 2.3 Проверка создания
Выполните запрос:
```sql
USE VKBotDatabase;
GO

SELECT TABLE_NAME 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_TYPE = 'BASE TABLE';
```

Должны быть созданы таблицы:
- Users
- ServiceNotes
- RoomBookings
- MediaProjects
- MessageHistory
- Statistics

## 3. Настройка подключения

### 3.1 Отредактировать файл db_config.py

**Вариант 1: SQL Server Authentication**
```python
DB_CONFIG = {
    'server': 'localhost',  # или имя вашего сервера
    'database': 'VKBotDatabase',
    'username': 'your_username',  # ваш логин
    'password': 'your_password',  # ваш пароль
    'driver': '{ODBC Driver 17 for SQL Server}'
}
```

**Вариант 2: Windows Authentication (рекомендуется для локальной разработки)**
```python
DB_CONFIG = {
    'server': 'localhost',
    'database': 'VKBotDatabase',
    'trusted_connection': 'yes',
    'driver': '{ODBC Driver 17 for SQL Server}'
}
```

Для Windows Authentication измените в `database.py`:
```python
conn_string = (
    f"DRIVER={DB_CONFIG['driver']};"
    f"SERVER={DB_CONFIG['server']};"
    f"DATABASE={DB_CONFIG['database']};"
    f"Trusted_Connection=yes;"
)
```

## 4. Тестирование подключения

Запустите тестовый скрипт:
```bash
python database.py
```

Ожидаемый результат:
```
✅ Подключение к базе данных установлено
✅ Тестовый пользователь добавлен
✅ Пользователь найден: (123456789, 'Иван', 'Иванов', ...)
Соединение с БД закрыто
✅ Тест подключения завершен успешно
```

## 5. Структура базы данных

### Основные таблицы:

**Users** - пользователи бота
- UserID (BIGINT, PK) - ID пользователя VK
- FirstName, LastName - имя и фамилия
- RegistrationDate - дата регистрации
- LastActivity - последняя активность
- IsActive - активен ли пользователь

**ServiceNotes** - служебные записки
- NoteID (INT, PK, IDENTITY)
- UserID - ID пользователя
- NoteType - тип записки (аудитория/освобождение/пропуск)
- RequestDate - дата запроса
- TargetDate - целевая дата
- Status - статус (В обработке/Одобрено/Отклонено)

**RoomBookings** - бронирование переговорок
- BookingID (INT, PK, IDENTITY)
- UserID - ID пользователя
- EventName - название мероприятия
- BookingDateTime - дата и время брони
- RoomName - название переговорки
- Status - статус (Подтверждено/Отменено)

**MediaProjects** - медиапроекты
- ProjectID (INT, PK, IDENTITY)
- UserID - ID пользователя
- ProjectName - название проекта
- Status - статус (На рассмотрении/Одобрено/Отклонено)
- RequestDate - дата подачи заявки

**MessageHistory** - история сообщений
- MessageID (INT, PK, IDENTITY)
- UserID - ID пользователя
- MessageText - текст сообщения
- BotResponse - ответ бота
- Timestamp - время сообщения

**Statistics** - статистика использования
- StatDate - дата
- ServiceNotesCount - количество служебных записок
- BookingsCount - количество броней
- MediaProjectsCount - количество медиапроектов

## 6. Использование в боте

Добавьте в начало файла bot.py:
```python
from database import DatabaseManager

# Инициализация БД
db = DatabaseManager()
```

Примеры использования:

### Регистрация пользователя:
```python
db.upsert_user(user_id, first_name="Иван", last_name="Иванов")
```

### Добавление служебной записки:
```python
note_id = db.add_service_note(
    user_id=user_id,
    note_type='аудитория',
    target_date='2025-12-20',
    comments='Для проведения лекции'
)
```

### Бронирование переговорки:
```python
booking_id = db.add_room_booking(
    user_id=user_id,
    event_name='Встреча с клиентом',
    event_format='Презентация',
    participants_count=10,
    booking_datetime='2025-12-20 14:30',
    room_name='Переговорка 1',
    equipment='Проектор, доска'
)
```

### Добавление медиапроекта:
```python
project_id = db.add_media_project(
    user_id=user_id,
    project_name='Видео о событии',
    project_format='Видео',
    support_needed='Монтаж',
    publication_place='YouTube',
    description='Репортаж о мероприятии'
)
```

### Логирование сообщений:
```python
db.log_message(
    user_id=user_id,
    message_text=text,
    bot_response=response,
    user_state=state['step']
)
```

## 7. Полезные SQL запросы

### Просмотр всех пользователей:
```sql
SELECT * FROM Users;
```

### Статистика по служебным запискам:
```sql
SELECT NoteType, Status, COUNT(*) as Count
FROM ServiceNotes
GROUP BY NoteType, Status;
```

### Предстоящие бронирования:
```sql
SELECT * FROM UpcomingBookings;
```

### Активность пользователей:
```sql
SELECT * FROM UserActivitySummary;
```

### Статистика за последнюю неделю:
```sql
SELECT * FROM Statistics
WHERE StatDate >= DATEADD(day, -7, GETDATE())
ORDER BY StatDate DESC;
```

## 8. Troubleshooting

### Ошибка: "Driver not found"
Установите ODBC Driver для SQL Server (см. п. 1.2)

### Ошибка: "Login failed"
Проверьте credentials в db_config.py или используйте Windows Authentication

### Ошибка: "Database does not exist"
Выполните скрипт database_setup.sql (см. п. 2)

### Ошибка: "Unable to connect"
- Проверьте, что SQL Server запущен
- Проверьте имя сервера в db_config.py
- Проверьте настройки файрвола
- Убедитесь, что SQL Server принимает TCP/IP соединения

## 9. Рекомендации

1. **Backup**: Регулярно создавайте резервные копии БД
2. **Индексы**: Уже созданы для основных запросов
3. **Логирование**: Используйте MessageHistory для аналитики
4. **Статистика**: Обновляйте ежедневно через `db.update_daily_statistics()`
5. **Очистка**: Периодически архивируйте старые записи

## 10. Безопасность

⚠️ **ВАЖНО:**
- Не храните db_config.py в git репозитории
- Добавьте db_config.py в .gitignore
- Используйте переменные окружения для продакшн-среды
- Ограничьте права доступа пользователя БД

Пример .gitignore:
```
db_config.py
*.pyc
__pycache__/
```
