import pyodbc
from datetime import datetime
from db_config import DB_CONFIG

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.connect()
    
    def connect(self):
        """Подключение к базе данных"""
        try:
            conn_string = (
                f"DRIVER={DB_CONFIG['driver']};"
                f"SERVER={DB_CONFIG['server']};"
                f"DATABASE={DB_CONFIG['database']};"
                f"UID={DB_CONFIG['username']};"
                f"PWD={DB_CONFIG['password']}"
            )
            self.connection = pyodbc.connect(conn_string)
            print("✅ Подключение к базе данных установлено")
        except Exception as e:
            print(f"❌ Ошибка подключения к БД: {e}")
            raise
    
    def close(self):
        """Закрытие соединения"""
        if self.connection:
            self.connection.close()
            print("Соединение с БД закрыто")
    
    def execute_query(self, query, params=None):
        """Выполнение SQL запроса"""
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
            return cursor
        except Exception as e:
            print(f"Ошибка выполнения запроса: {e}")
            self.connection.rollback()
            return None
    
    def fetch_one(self, query, params=None):
        """Получение одной записи"""
        cursor = self.execute_query(query, params)
        if cursor:
            return cursor.fetchone()
        return None
    
    def fetch_all(self, query, params=None):
        """Получение всех записей"""
        cursor = self.execute_query(query, params)
        if cursor:
            return cursor.fetchall()
        return []
    
    # ========== ПОЛЬЗОВАТЕЛИ ==========
    
    def upsert_user(self, user_id, first_name=None, last_name=None):
        """Добавление или обновление пользователя"""
        query = "EXEC usp_UpsertUser @UserID=?, @FirstName=?, @LastName=?"
        self.execute_query(query, (user_id, first_name, last_name))
    
    def get_user(self, user_id):
        """Получение информации о пользователе"""
        query = "SELECT * FROM Users WHERE UserID = ?"
        return self.fetch_one(query, (user_id,))
    
    def get_all_users(self):
        """Получение всех пользователей"""
        query = "SELECT * FROM Users WHERE IsActive = 1"
        return self.fetch_all(query)
    
    # СЛУЖЕБНЫЕ ЗАПИСКИ 
    
    def add_service_note(self, user_id, note_type, target_date, comments=None):
        """Добавление служебной записки"""
        query = "EXEC usp_AddServiceNote @UserID=?, @NoteType=?, @TargetDate=?, @Comments=?"
        cursor = self.execute_query(query, (user_id, note_type, target_date, comments))
        if cursor:
            result = cursor.fetchone()
            return result[0] if result else None
        return None
    
    def update_service_note_status(self, note_id, status):
        """Обновление статуса служебной записки"""
        query = """
            UPDATE ServiceNotes 
            SET Status = ?, ProcessedDate = GETDATE() 
            WHERE NoteID = ?
        """
        self.execute_query(query, (status, note_id))
    
    def get_user_service_notes(self, user_id):
        """Получение всех служебных записок пользователя"""
        query = """
            SELECT NoteID, NoteType, TargetDate, Status, RequestDate 
            FROM ServiceNotes 
            WHERE UserID = ? 
            ORDER BY RequestDate DESC
        """
        return self.fetch_all(query, (user_id,))
    
    def get_pending_service_notes(self):
        """Получение всех служебных записок в обработке"""
        query = """
            SELECT sn.*, u.FirstName, u.LastName 
            FROM ServiceNotes sn
            INNER JOIN Users u ON sn.UserID = u.UserID
            WHERE sn.Status = 'В обработке'
            ORDER BY sn.RequestDate
        """
        return self.fetch_all(query)
    
    # БРОНЬ ПЕРЕГОВОРОК
    
    def add_room_booking(self, user_id, event_name, event_format, participants_count, 
                        booking_datetime, room_name, equipment=None):
        """Добавление брони переговорки"""
        query = """
            EXEC usp_AddRoomBooking 
            @UserID=?, @EventName=?, @EventFormat=?, @ParticipantsCount=?, 
            @BookingDateTime=?, @RoomName=?, @Equipment=?
        """
        cursor = self.execute_query(query, (user_id, event_name, event_format, 
                                           participants_count, booking_datetime, 
                                           room_name, equipment))
        if cursor:
            result = cursor.fetchone()
            return result[0] if result else None
        return None
    
    def cancel_booking(self, booking_id):
        """Отмена брони"""
        query = "UPDATE RoomBookings SET Status = 'Отменено' WHERE BookingID = ?"
        self.execute_query(query, (booking_id,))
    
    def get_user_bookings(self, user_id):
        """Получение всех броней пользователя"""
        query = """
            SELECT BookingID, EventName, BookingDateTime, RoomName, Status 
            FROM RoomBookings 
            WHERE UserID = ? 
            ORDER BY BookingDateTime DESC
        """
        return self.fetch_all(query, (user_id,))
    
    def get_upcoming_bookings(self):
        """Получение предстоящих броней"""
        query = "SELECT * FROM UpcomingBookings"
        return self.fetch_all(query)
    
    def check_room_availability(self, room_name, booking_datetime):
        """Проверка доступности переговорки"""
        query = """
            SELECT COUNT(*) as BookingCount
            FROM RoomBookings
            WHERE RoomName = ? 
              AND BookingDateTime = ?
              AND Status = 'Подтверждено'
        """
        result = self.fetch_one(query, (room_name, booking_datetime))
        return result[0] == 0 if result else False
    
    #  МЕДИАПРОЕКТЫ 
    
    def add_media_project(self, user_id, project_name, project_format, 
                         support_needed, publication_place, description):
        """Добавление медиапроекта"""
        query = """
            EXEC usp_AddMediaProject 
            @UserID=?, @ProjectName=?, @ProjectFormat=?, @SupportNeeded=?, 
            @PublicationPlace=?, @Description=?
        """
        cursor = self.execute_query(query, (user_id, project_name, project_format, 
                                           support_needed, publication_place, description))
        if cursor:
            result = cursor.fetchone()
            return result[0] if result else None
        return None
    
    def update_media_project_status(self, project_id, status, comments=None):
        """Обновление статуса медиапроекта"""
        query = """
            UPDATE MediaProjects 
            SET Status = ?, ReviewDate = GETDATE(), Comments = ?
            WHERE ProjectID = ?
        """
        self.execute_query(query, (status, comments, project_id))
    
    def get_user_media_projects(self, user_id):
        """Получение всех медиапроектов пользователя"""
        query = """
            SELECT ProjectID, ProjectName, Status, RequestDate 
            FROM MediaProjects 
            WHERE UserID = ? 
            ORDER BY RequestDate DESC
        """
        return self.fetch_all(query, (user_id,))
    
    def get_pending_media_projects(self):
        """Получение медиапроектов на рассмотрении"""
        query = """
            SELECT mp.*, u.FirstName, u.LastName 
            FROM MediaProjects mp
            INNER JOIN Users u ON mp.UserID = u.UserID
            WHERE mp.Status = 'На рассмотрении'
            ORDER BY mp.RequestDate
        """
        return self.fetch_all(query)
    
    #ИСТОРИЯ СООБЩЕНИЙ 
    
    def log_message(self, user_id, message_text, bot_response=None, user_state=None):
        """Логирование сообщения"""
        query = "EXEC usp_LogMessage @UserID=?, @MessageText=?, @BotResponse=?, @UserState=?"
        self.execute_query(query, (user_id, message_text, bot_response, user_state))
    
    def get_user_message_history(self, user_id, limit=50):
        """Получение истории сообщений пользователя"""
        query = """
            SELECT TOP (?) MessageText, BotResponse, Timestamp 
            FROM MessageHistory 
            WHERE UserID = ? 
            ORDER BY Timestamp DESC
        """
        return self.fetch_all(query, (limit, user_id))
    
    # СТАТИСТИКА
    
    def update_daily_statistics(self):
        """Обновление ежедневной статистики"""
        query = "EXEC usp_UpdateDailyStatistics"
        self.execute_query(query)
    
    def get_statistics(self, days=7):
        """Получение статистики за последние N дней"""
        query = """
            SELECT TOP (?) * 
            FROM Statistics 
            ORDER BY StatDate DESC
        """
        return self.fetch_all(query, (days,))
    
    def get_user_activity_summary(self, user_id):
        """Получение сводки активности пользователя"""
        query = "SELECT * FROM UserActivitySummary WHERE UserID = ?"
        return self.fetch_one(query, (user_id,))


# Пример использования
if __name__ == "__main__":
    # Тестирование подключения
    try:
        db = DatabaseManager()
        
        # Добавление тестового пользователя
        db.upsert_user(123456789, "Иван", "Иванов")
        print("✅ Тестовый пользователь добавлен")
        
        # Получение информации о пользователе
        user = db.get_user(123456789)
        if user:
            print(f"✅ Пользователь найден: {user}")
        
        db.close()
        print("✅ Тест подключения завершен успешно")
        
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
