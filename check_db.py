"""
Скрипт для проверки данных в базе данных
"""
from database_sqlite import SQLiteDatabase

db = SQLiteDatabase()

print("\n" + "="*60)
print("📊 ПРОВЕРКА ДАННЫХ В БАЗЕ ДАННЫХ")
print("="*60)

# 1. Проверка пользователей
print("\n👥 ПОЛЬЗОВАТЕЛИ:")
users = db.get_all_users()
print(f"Всего пользователей: {len(users)}")
for user in users:
    print(f"  • VK ID: {user['vk_id']}")
    print(f"    Имя: {user.get('имя', 'Не указано')} {user.get('фамилия', '')}")
    print(f"    Активность: {user.get('последняя_активность', 'Нет данных')}")
    print()

# 2. Проверка истории сообщений
print("\n💬 ИСТОРИЯ СООБЩЕНИЙ:")
conn = db.connect()
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM История_сообщений')
msg_count = cursor.fetchone()[0]
print(f"Всего сообщений: {msg_count}")

if msg_count > 0:
    cursor.execute('SELECT * FROM История_сообщений ORDER BY время DESC LIMIT 10')
    messages = cursor.fetchall()
    print("\nПоследние 10 сообщений:")
    for msg in messages:
        print(f"  • {msg['время']}")
        print(f"    От пользователя: {msg['vk_id']}")
        print(f"    Сообщение: {msg['текст_сообщения']}")
        print(f"    Ответ бота: {msg['ответ_бота'][:50]}..." if msg['ответ_бота'] and len(msg['ответ_бота']) > 50 else f"    Ответ бота: {msg['ответ_бота']}")
        print()

# 3. Проверка заявок на служебки
print("\n📋 ЗАЯВКИ НА СЛУЖЕБКИ:")
cursor.execute('SELECT COUNT(*) FROM Заявка_на_служебку')
notes_count = cursor.fetchone()[0]
print(f"Всего заявок: {notes_count}")

# 4. Проверка броней переговорок
print("\n🏢 БРОНИ ПЕРЕГОВОРОК:")
cursor.execute('SELECT COUNT(*) FROM Заявки_на_переговорки')
bookings_count = cursor.fetchone()[0]
print(f"Всего броней: {bookings_count}")

if bookings_count > 0:
    cursor.execute('SELECT * FROM Заявки_на_переговорки ORDER BY дата_подачи DESC LIMIT 5')
    bookings = cursor.fetchall()
    print("\nПоследние брони:")
    for booking in bookings:
        print(f"  • Мероприятие: {booking['название_мероприятия']}")
        print(f"    Дата: {booking['дата_и_время']}")
        print(f"    Статус: {booking['статус']}")
        print()

# 5. Проверка медиапроектов
print("\n🎬 МЕДИАПРОЕКТЫ:")
cursor.execute('SELECT COUNT(*) FROM Заявка_на_медиапроект')
projects_count = cursor.fetchone()[0]
print(f"Всего проектов: {projects_count}")

db.close()

print("\n" + "="*60)
print("✅ Проверка завершена")
print("="*60 + "\n")
