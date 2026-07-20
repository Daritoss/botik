"""
Модуль для работы с базой данных SQLite для VK бота
Поддерживает работу с пользователями, заявками на служебки, переговорки и медиапроекты
"""

import os
import sqlite3
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any

# Файл БД рядом с этим модулем (одинаково на Windows, Linux и VPS)
_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQLITE_PATH = os.path.join(_BOT_DIR, 'vk-botik.db')


class SQLiteDatabase:
    """Класс для работы с SQLite базой данных бота"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Инициализация подключения к базе данных
        
        Args:
            db_path: Путь к файлу базы данных SQLite; по умолчанию — vk-botik.db в каталоге проекта
        """
        self.db_path = db_path if db_path is not None else DEFAULT_SQLITE_PATH
        # Соединение на поток: иначе main + поток статистики ломают друг друга
        self._local = threading.local()
        self._write_lock = threading.RLock()
        self.connection = None  # совместимость: последнее соединение текущего потока
        self._ensure_tables()
        self._ensure_innovatika_room_row()

    def _ensure_tables(self):
        """Создаёт недостающие таблицы при инициализации"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Документы (
                id_документа INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER NOT NULL,
                тип_документа TEXT,
                id_заявки INTEGER,
                vk_doc_id INTEGER NOT NULL,
                vk_owner_id INTEGER NOT NULL,
                название_файла TEXT NOT NULL,
                расширение TEXT,
                размер INTEGER,
                url TEXT NOT NULL,
                дата_загрузки TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (vk_id) REFERENCES Пользователь(vk_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Бронирование_PlayStation (
                id_заявки INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER NOT NULL,
                дата TEXT NOT NULL,
                время_начала TEXT NOT NULL,
                время_окончания TEXT NOT NULL,
                количество_часов INTEGER NOT NULL,
                id_диалога INTEGER,
                статус TEXT DEFAULT 'На рассмотрении',
                дата_подачи TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (vk_id) REFERENCES Пользователь(vk_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Занятость_PlayStation (
                id_слота INTEGER PRIMARY KEY AUTOINCREMENT,
                дата TEXT NOT NULL,
                время_начала TEXT NOT NULL,
                время_окончания TEXT NOT NULL,
                vk_id INTEGER NOT NULL,
                id_заявки INTEGER,
                статус TEXT DEFAULT 'Занято',
                дата_обновления TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (vk_id) REFERENCES Пользователь(vk_id)
            )
        ''')
        cursor.execute('DROP INDEX IF EXISTS UX_Занятость_PS_Слот')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS UX_Занятость_PS_Слот
            ON Занятость_PlayStation (дата, время_начала, время_окончания, статус)
        ''')
        conn.commit()
        conn.close()

    def _ensure_innovatika_room_row(self) -> None:
        """Строка справочника «Инноватика» (id=10) для брони в боте; не меняет существующие id 1–9."""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='Переговорки'"
            )
            if not cur.fetchone():
                return
            cur.execute(
                """
                INSERT OR IGNORE INTO Переговорки (id_переговорки, название, вместимость)
                VALUES (10, '«Инноватика» – до 20 чел.', 20)
                """
            )
            conn.commit()
        finally:
            conn.close()

    def connect(self) -> sqlite3.Connection:
        """Открыть соединение с БД в текущем потоке (безопасно при параллельных запросах)."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA busy_timeout = 30000')
        self._local.connection = conn
        self.connection = conn
        return conn
    
    def close(self):
        """Закрыть соединение текущего потока"""
        conn = getattr(self._local, 'connection', None)
        if conn is None:
            conn = self.connection
        if conn is not None:
            try:
                conn.commit()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
        if getattr(self._local, 'connection', None) is conn:
            self._local.connection = None
        if self.connection is conn:
            self.connection = None
    
    def __enter__(self):
        """Контекстный менеджер: вход"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: выход"""
        self.close()
    
   
    # РАБОТА С ПОЛЬЗОВАТЕЛЯМИ
   
    
    def add_user(self, vk_id: int, имя: str = None, фамилия: str = None) -> None:
        """
        Добавить или обновить пользователя
        
        Args:
            vk_id: ID пользователя ВКонтакте
            имя: Имя пользователя
            фамилия: Фамилия пользователя
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute('SELECT vk_id FROM Пользователь WHERE vk_id = ?', (vk_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Обновляем активность
            cursor.execute('''
                UPDATE Пользователь 
                SET последняя_активность = ?,
                    имя = COALESCE(?, имя),
                    фамилия = COALESCE(?, фамилия)
                WHERE vk_id = ?
            ''', (datetime.now().isoformat(), имя, фамилия, vk_id))
        else:
            # Создаем нового пользователя
            cursor.execute('''
                INSERT INTO Пользователь (vk_id, имя, фамилия)
                VALUES (?, ?, ?)
            ''', (vk_id, имя, фамилия))
        
        conn.commit()
        self.close()
    
    def get_user(self, vk_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить данные пользователя по ID
        
        Args:
            vk_id: ID пользователя ВКонтакте
            
        Returns:
            Словарь с данными пользователя или None
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Пользователь WHERE vk_id = ?', (vk_id,))
        user = cursor.fetchone()
        
        self.close()
        return dict(user) if user else None
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получить список всех пользователей"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Пользователь ORDER BY последняя_активность DESC')
        users = cursor.fetchall()
        
        self.close()
        return [dict(row) for row in users]
    
   
    # РАБОТА С ДИАЛОГАМИ

    
    def create_dialog(self, vk_id: int, состояние: str = None) -> int:
        """
        Создать новый диалог
        
        Args:
            vk_id: ID пользователя
            состояние: Начальное состояние диалога
            
        Returns:
            ID созданного диалога
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO Диалог (vk_id, состояние_диалога)
            VALUES (?, ?)
        ''', (vk_id, состояние))
        
        dialog_id = cursor.lastrowid
        conn.commit()
        self.close()
        
        return dialog_id
    
    def update_dialog_state(self, id_диалога: int, состояние: str, последнее_сообщение: str = None):
        """Обновить состояние диалога"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE Диалог 
            SET состояние_диалога = ?, 
                последнее_сообщение = ?
            WHERE id_диалога = ?
        ''', (состояние, последнее_сообщение, id_диалога))
        
        conn.commit()
        self.close()
    
    # РАБОТА СО СЛУЖЕБКАМИ

    
    def get_service_types(self) -> List[Dict[str, Any]]:
        """Получить список всех типов служебок"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Служебки ORDER BY id_служебки')
        types = cursor.fetchall()
        
        self.close()
        return [dict(row) for row in types]
    
    def get_service_type(self, id_служебки: int) -> Optional[Dict[str, Any]]:
        """Получить информацию о конкретном типе служебки"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Служебки WHERE id_служебки = ?', (id_служебки,))
        service = cursor.fetchone()
        
        self.close()
        return dict(service) if service else None
    
    def add_service_note(self, vk_id: int, id_служебки: int, дата_мероприятия: str,
                         id_диалога: int = None, комментарии: str = None) -> int:
        """
        Создать заявку на служебку
        
        Args:
            vk_id: ID пользователя
            id_служебки: Тип служебки
            дата_мероприятия: Дата мероприятия (ISO формат)
            id_диалога: ID диалога (опционально)
            комментарии: Комментарии к заявке
            
        Returns:
            ID созданной заявки
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO Заявка_на_служебку 
            (vk_id, id_служебки, дата_мероприятия, id_диалога, комментарии)
            VALUES (?, ?, ?, ?, ?)
        ''', (vk_id, id_служебки, дата_мероприятия, id_диалога, комментарии))
        
        заявка_id = cursor.lastrowid
        conn.commit()
        self.close()
        
        return заявка_id
    
    def get_user_service_notes(self, vk_id: int, статус: str = None) -> List[Dict[str, Any]]:
        """
        Получить заявки на служебки пользователя
        
        Args:
            vk_id: ID пользователя
            статус: Фильтр по статусу (опционально)
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        if статус:
            cursor.execute('''
                SELECT зс.*, с.тип_служебки 
                FROM Заявка_на_служебку зс
                JOIN Служебки с ON зс.id_служебки = с.id_служебки
                WHERE зс.vk_id = ? AND зс.статус = ?
                ORDER BY зс.дата_подачи DESC
            ''', (vk_id, статус))
        else:
            cursor.execute('''
                SELECT зс.*, с.тип_служебки 
                FROM Заявка_на_служебку зс
                JOIN Служебки с ON зс.id_служебки = с.id_служебки
                WHERE зс.vk_id = ?
                ORDER BY зс.дата_подачи DESC
            ''', (vk_id,))
        
        notes = cursor.fetchall()
        self.close()
        return [dict(row) for row in notes]
    
    def update_service_note_status(self, id_заявки: int, статус: str):
        """Обновить статус заявки на служебку"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE Заявка_на_служебку 
            SET статус = ?, дата_обработки = ?
            WHERE id_заявки = ?
        ''', (статус, datetime.now().isoformat(), id_заявки))
        
        conn.commit()
        self.close()
    
    
    # РАБОТА С ПЕРЕГОВОРКАМИ
   
    
    def get_rooms(self) -> List[Dict[str, Any]]:
        """Получить список всех переговорок"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Переговорки ORDER BY название')
        rooms = cursor.fetchall()
        
        self.close()
        return [dict(row) for row in rooms]
    
    def get_room(self, id_переговорки: int) -> Optional[Dict[str, Any]]:
        """Получить информацию о переговорке"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Переговорки WHERE id_переговорки = ?', (id_переговорки,))
        room = cursor.fetchone()
        
        self.close()
        return dict(room) if room else None
    
    def get_room_equipment(self, id_переговорки: int) -> List[Dict[str, Any]]:
        """Получить оборудование в переговорке"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT о.* 
            FROM Оборудование о
            JOIN Оборудование_в_переговорке оп ON о.id_оборудования = оп.id_оборудования
            WHERE оп.id_переговорки = ?
        ''', (id_переговорки,))
        
        equipment = cursor.fetchall()
        self.close()
        return [dict(row) for row in equipment]
    
    def add_room_booking(self, vk_id: int, название_мероприятия: str, дата_и_время: str,
                         id_переговорки: int = None, формат: str = None,
                         количество_человек: int = None, необходимость_оборудования: str = None,
                         id_оборудования: int = None, id_диалога: int = None) -> int:
        """
        Создать бронь переговорки
        
        Args:
            vk_id: ID пользователя
            название_мероприятия: Название мероприятия
            дата_и_время: Дата и время (ISO формат)
            id_переговорки: ID переговорки
            формат: Формат мероприятия
            количество_человек: Количество участников
            необходимость_оборудования: Описание нужного оборудования
            id_оборудования: ID оборудования
            id_диалога: ID диалога
            
        Returns:
            ID созданной брони
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO Заявки_на_переговорки 
            (vk_id, название_мероприятия, дата_и_время, id_переговорки, формат,
             количество_человек, необходимость_оборудования, id_оборудования, id_диалога)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (vk_id, название_мероприятия, дата_и_время, id_переговорки, формат,
              количество_человек, необходимость_оборудования, id_оборудования, id_диалога))
        
        заявка_id = cursor.lastrowid
        conn.commit()
        self.close()
        
        return заявка_id
    
    def get_user_bookings(self, vk_id: int, статус: str = None) -> List[Dict[str, Any]]:
        """
        Получить брони пользователя
        
        Args:
            vk_id: ID пользователя
            статус: Фильтр по статусу (опционально)
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        if статус:
            cursor.execute('''
                SELECT зп.*, п.название AS название_переговорки
                FROM Заявки_на_переговорки зп
                LEFT JOIN Переговорки п ON зп.id_переговорки = п.id_переговорки
                WHERE зп.vk_id = ? AND зп.статус = ?
                ORDER BY зп.дата_и_время DESC
            ''', (vk_id, статус))
        else:
            cursor.execute('''
                SELECT зп.*, п.название AS название_переговорки
                FROM Заявки_на_переговорки зп
                LEFT JOIN Переговорки п ON зп.id_переговорки = п.id_переговорки
                WHERE зп.vk_id = ?
                ORDER BY зп.дата_и_время DESC
            ''', (vk_id,))
        
        bookings = cursor.fetchall()
        self.close()
        return [dict(row) for row in bookings]
    
    def cancel_booking(self, id_заявки: int):
        """Отменить бронь переговорки"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE Заявки_на_переговорки 
            SET статус = 'Отменено'
            WHERE id_заявки = ?
        ''', (id_заявки,))
        
        conn.commit()
        self.close()
    
    
    # РАБОТА С МЕДИАПРОЕКТАМИ
   
    
    def add_media_project(self, vk_id: int, название: str, формат: str, описание: str,
                          необходимая_поддержка: str = None, место_публикации: str = None,
                          id_диалога: int = None) -> int:
        """
        Создать заявку на медиапроект
        
        Args:
            vk_id: ID пользователя
            название: Название проекта
            формат: Формат проекта
            описание: Описание проекта
            необходимая_поддержка: Какая поддержка нужна
            место_публикации: Где будет опубликовано
            id_диалога: ID диалога
            
        Returns:
            ID созданной заявки
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO Заявка_на_медиапроект 
            (vk_id, название, формат, описание, необходимая_поддержка, место_публикации, id_диалога)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (vk_id, название, формат, описание, необходимая_поддержка, место_публикации, id_диалога))
        
        заявка_id = cursor.lastrowid
        conn.commit()
        self.close()
        
        return заявка_id
    
    def get_user_media_projects(self, vk_id: int, статус: str = None) -> List[Dict[str, Any]]:
        """
        Получить медиапроекты пользователя
        
        Args:
            vk_id: ID пользователя
            статус: Фильтр по статусу (опционально)
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        if статус:
            cursor.execute('''
                SELECT * FROM Заявка_на_медиапроект
                WHERE vk_id = ? AND статус = ?
                ORDER BY дата_подачи DESC
            ''', (vk_id, статус))
        else:
            cursor.execute('''
                SELECT * FROM Заявка_на_медиапроект
                WHERE vk_id = ?
                ORDER BY дата_подачи DESC
            ''', (vk_id,))
        
        projects = cursor.fetchall()
        self.close()
        return [dict(row) for row in projects]
    
    def update_media_project_status(self, id_заявки: int, статус: str, комментарии: str = None):
        """Обновить статус медиапроекта"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE Заявка_на_медиапроект 
            SET статус = ?, дата_рассмотрения = ?, комментарии = ?
            WHERE id_заявки = ?
        ''', (статус, datetime.now().isoformat(), комментарии, id_заявки))
        
        conn.commit()
        self.close()
    
   
    # ЛОГИРОВАНИЕ И ИСТОРИЯ
   
    
    def log_message(self, vk_id: int, текст_сообщения: str, 
                    ответ_бота: str = None, состояние: str = None):
        """
        Сохранить сообщение в историю
        
        Args:
            vk_id: ID пользователя
            текст_сообщения: Текст сообщения от пользователя
            ответ_бота: Ответ бота
            состояние: Текущее состояние пользователя
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO История_сообщений 
            (vk_id, текст_сообщения, ответ_бота, состояние_пользователя)
            VALUES (?, ?, ?, ?)
        ''', (vk_id, текст_сообщения, ответ_бота, состояние))
        
        conn.commit()
        self.close()
    
    def get_user_message_history(self, vk_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Получить историю сообщений пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM История_сообщений
            WHERE vk_id = ?
            ORDER BY время DESC
            LIMIT ?
        ''', (vk_id, limit))
        
        history = cursor.fetchall()
        self.close()
        return [dict(row) for row in history]
    

    # СТАТИСТИКА

    
    def update_daily_statistics(self):
        """Обновить ежедневную статистику"""
        conn = self.connect()
        try:
            cursor = conn.cursor()

            today = datetime.now().date().isoformat()

            # Проверяем, есть ли уже запись за сегодня
            cursor.execute('SELECT id_статистики FROM Статистика WHERE дата = ?', (today,))
            exists = cursor.fetchone()

            # Считаем статистику за сегодня
            cursor.execute('SELECT COUNT(*) FROM Заявка_на_служебку WHERE date(дата_подачи) = ?', (today,))
            служебок = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM Заявки_на_переговорки WHERE date(дата_подачи) = ?', (today,))
            броней = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM Заявка_на_медиапроект WHERE date(дата_подачи) = ?', (today,))
            медиапроектов = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(DISTINCT vk_id) FROM Пользователь WHERE date(последняя_активность) = ?', (today,))
            активных = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM История_сообщений WHERE date(время) = ?', (today,))
            сообщений = cursor.fetchone()[0]

            if exists:
                cursor.execute('''
                    UPDATE Статистика 
                    SET количество_служебок = ?,
                        количество_броней = ?,
                        количество_медиапроектов = ?,
                        количество_активных_пользователей = ?,
                        количество_сообщений = ?
                    WHERE дата = ?
                ''', (служебок, броней, медиапроектов, активных, сообщений, today))
            else:
                cursor.execute('''
                    INSERT INTO Статистика 
                    (дата, количество_служебок, количество_броней, количество_медиапроектов,
                     количество_активных_пользователей, количество_сообщений)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (today, служебок, броней, медиапроектов, активных, сообщений))

            conn.commit()
        finally:
            self.close()
    
    def get_statistics(self, дней: int = 7) -> List[Dict[str, Any]]:
        """
        Получить статистику за последние N дней
        
        Args:
            дней: Количество дней для выборки
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM Статистика
            ORDER BY дата DESC
            LIMIT ?
        ''', (дней,))
        
        stats = cursor.fetchall()
        self.close()
        return [dict(row) for row in stats]
    

    # ПРЕДСТАВЛЕНИЯ
    
    def get_user_activity_summary(self, vk_id: int = None) -> List[Dict[str, Any]]:
        """
        Получить сводку активности пользователей
        
        Args:
            vk_id: ID конкретного пользователя (опционально)
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        if vk_id:
            cursor.execute('SELECT * FROM Сводка_активности_пользователей WHERE vk_id = ?', (vk_id,))
        else:
            cursor.execute('SELECT * FROM Сводка_активности_пользователей')
        
        summary = cursor.fetchall()
        self.close()
        return [dict(row) for row in summary]
    
    def get_upcoming_bookings(self) -> List[Dict[str, Any]]:
        """Получить предстоящие брони переговорок"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Предстоящие_брони ORDER BY дата_и_время')
        bookings = cursor.fetchall()
        
        self.close()
        return [dict(row) for row in bookings]
    
    # РАБОТА С ДОКУМЕНТАМИ

    def add_document(self, vk_id: int, vk_doc_id: int, vk_owner_id: int,
                     название_файла: str, расширение: str = None, размер: int = None,
                     url: str = None, тип_документа: str = 'общий',
                     id_заявки: int = None) -> int:
        """
        Сохранить информацию о загруженном документе
        
        Args:
            vk_id: ID пользователя ВКонтакте
            vk_doc_id: ID документа в VK
            vk_owner_id: Owner ID документа в VK
            название_файла: Название файла
            расширение: Расширение файла (например, 'docx', 'pdf')
            размер: Размер файла в байтах
            url: URL документа
            тип_документа: Тип ('служебка', 'переговорка', 'медиапроект', 'общий')
            id_заявки: ID связанной заявки (опционально)
            
        Returns:
            ID созданной записи о документе
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO Документы (
                vk_id, vk_doc_id, vk_owner_id, название_файла, расширение,
                размер, url, тип_документа, id_заявки
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (vk_id, vk_doc_id, vk_owner_id, название_файла, расширение,
              размер, url, тип_документа, id_заявки))
        
        doc_id = cursor.lastrowid
        conn.commit()
        self.close()
        
        return doc_id
    
    def get_document(self, id_документа: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о документе по ID
        
        Args:
            id_документа: ID документа
            
        Returns:
            Словарь с данными документа или None
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Документы WHERE id_документа = ?', (id_документа,))
        document = cursor.fetchone()
        
        self.close()
        return dict(document) if document else None
    
    def get_documents_by_user(self, vk_id: int, тип_документа: str = None) -> List[Dict[str, Any]]:
        """
        Получить все документы пользователя
        
        Args:
            vk_id: ID пользователя
            тип_документа: Фильтр по типу документа (опционально)
            
        Returns:
            Список документов пользователя
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        if тип_документа:
            cursor.execute('''
                SELECT * FROM Документы 
                WHERE vk_id = ? AND тип_документа = ?
                ORDER BY дата_загрузки DESC
            ''', (vk_id, тип_документа))
        else:
            cursor.execute('''
                SELECT * FROM Документы 
                WHERE vk_id = ?
                ORDER BY дата_загрузки DESC
            ''', (vk_id,))
        
        documents = cursor.fetchall()
        self.close()
        
        return [dict(row) for row in documents]
    
    def get_documents_by_request(self, id_заявки: int, тип_документа: str) -> List[Dict[str, Any]]:
        """
        Получить документы, связанные с конкретной заявкой
        
        Args:
            id_заявки: ID заявки
            тип_документа: Тип документа
            
        Returns:
            Список документов заявки
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM Документы 
            WHERE id_заявки = ? AND тип_документа = ?
            ORDER BY дата_загрузки DESC
        ''', (id_заявки, тип_документа))
        
        documents = cursor.fetchall()
        self.close()
        
        return [dict(row) for row in documents]
    
    def update_document_request_link(self, id_документа: int, id_заявки: int):
        """
        Связать документ с заявкой
        
        Args:
            id_документа: ID документа
            id_заявки: ID заявки
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE Документы 
            SET id_заявки = ?
            WHERE id_документа = ?
        ''', (id_заявки, id_документа))
        
        conn.commit()
        self.close()

    def add_ps_booking(self, vk_id: int, дата: str, время_начала: str,
                       время_окончания: str, количество_часов: int,
                       id_диалога: int = None) -> int:
        """Cохранить заявку на PlayStation"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Бронирование_PlayStation
                (vk_id, дата, время_начала, время_окончания, количество_часов, id_диалога)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (vk_id, дата, время_начала, время_окончания, количество_часов, id_диалога))
        заявка_id = cursor.lastrowid
        conn.commit()
        self.close()
        return заявка_id

    def is_ps_slot_available(self, дата: str, время_начала: str, время_окончания: str) -> bool:
        """Проверить доступность слота PlayStation"""
        date_variants = {дата}
        if '-' in дата:
            try:
                date_obj = datetime.strptime(дата, '%Y-%m-%d').date()
                date_variants.add(date_obj.strftime('%d.%m.%Y'))
            except ValueError:
                pass

        conn = self.connect()
        cursor = conn.cursor()
        count = 0
        for date_value in date_variants:
            cursor.execute('''
                SELECT COUNT(*)
                FROM Занятость_PlayStation
                WHERE дата = ? AND время_начала = ? AND время_окончания = ? AND статус = 'Занято'
            ''', (date_value, время_начала, время_окончания))
            count += cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*)
                FROM Бронирование_PlayStation
                WHERE дата = ? AND время_начала = ? AND время_окончания = ? AND статус != 'Отменено'
            ''', (date_value, время_начала, время_окончания))
            count += cursor.fetchone()[0]

        self.close()
        return count == 0

    def add_ps_slot(self, vk_id: int, дата: str, время_начала: str,
                    время_окончания: str, id_заявки: int = None) -> bool:
        """Занять слот PlayStation"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO Занятость_PlayStation
                    (дата, время_начала, время_окончания, vk_id, id_заявки)
                VALUES (?, ?, ?, ?, ?)
            ''', (дата, время_начала, время_окончания, vk_id, id_заявки))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            self.close()

    def get_ps_busy_slots(self, дата: str) -> List[Dict[str, Any]]:
        """Получить занятые слоты PlayStation на дату"""
        date_variants = {дата}
        if '-' in дата:
            try:
                date_obj = datetime.strptime(дата, '%Y-%m-%d').date()
                date_variants.add(date_obj.strftime('%d.%m.%Y'))
            except ValueError:
                pass

        conn = self.connect()
        cursor = conn.cursor()
        busy = set()
        for date_value in date_variants:
            cursor.execute('''
                SELECT время_начала, время_окончания
                FROM Занятость_PlayStation
                WHERE дата = ? AND статус = 'Занято'
                ORDER BY время_начала
            ''', (date_value,))
            rows = cursor.fetchall()
            for row in rows:
                busy.add((row['время_начала'], row['время_окончания']))

            cursor.execute('''
                SELECT время_начала, время_окончания
                FROM Бронирование_PlayStation
                WHERE дата = ? AND статус != 'Отменено'
                ORDER BY время_начала
            ''', (date_value,))
            rows = cursor.fetchall()
            for row in rows:
                busy.add((row['время_начала'], row['время_окончания']))

        self.close()
        return [{'время_начала': start, 'время_окончания': end} for start, end in sorted(busy)]

    def get_ps_week_busy_slots(self, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """Получить занятые слоты PlayStation за период"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT дата, время_начала, время_окончания
            FROM Занятость_PlayStation
            WHERE дата BETWEEN ? AND ? AND статус = 'Занято'
            ORDER BY дата, время_начала
        ''', (date_from, date_to))
        rows = cursor.fetchall()

        cursor.execute('''
            SELECT дата, время_начала, время_окончания
            FROM Бронирование_PlayStation
            WHERE статус != 'Отменено'
        ''')
        booking_rows = cursor.fetchall()
        self.close()
        result = [dict(row) for row in rows]

        try:
            date_start_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_end_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            return result

        for row in booking_rows:
            date_value = row['дата']
            date_obj = None
            if '-' in date_value:
                try:
                    date_obj = datetime.strptime(date_value, '%Y-%m-%d').date()
                except ValueError:
                    date_obj = None
            if date_obj is None:
                try:
                    date_obj = datetime.strptime(date_value, '%d.%m.%Y').date()
                except ValueError:
                    date_obj = None

            if date_obj and date_start_obj <= date_obj <= date_end_obj:
                result.append({
                    'дата': date_obj.isoformat(),
                    'время_начала': row['время_начала'],
                    'время_окончания': row['время_окончания']
                })

        return result

    @staticmethod
    def _ps_date_variants(дата: str) -> List[str]:
        """Строковые варианты одной даты для поиска в БД (ISO и ДД.ММ.ГГГГ)."""
        if not дата or not str(дата).strip():
            return []
        s = str(дата).strip()
        variants = {s}
        if '-' in s:
            try:
                d = datetime.strptime(s, '%Y-%m-%d').date()
                variants.add(d.strftime('%d.%m.%Y'))
            except ValueError:
                pass
        if '.' in s:
            try:
                d = datetime.strptime(s, '%d.%m.%Y').date()
                variants.add(d.isoformat())
            except ValueError:
                pass
        return list(variants)

    def get_ps_active_owner_for_slot(self, дата: str, время_начала: str) -> Optional[int]:
        """vk_id владельца активной записи на слот (сначала заявка, иначе занятость), или None."""
        variants = self._ps_date_variants(дата) if дата else []
        if not variants:
            variants = [str(дата).strip()] if дата else []
        if not variants:
            return None
        ph = ','.join('?' * len(variants))
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            f'''
            SELECT vk_id FROM Бронирование_PlayStation
            WHERE время_начала = ? AND IFNULL(статус, '') != 'Отменено' AND дата IN ({ph})
            LIMIT 1
            ''',
            (время_начала, *variants),
        )
        row = cursor.fetchone()
        if row:
            oid = int(row['vk_id'])
            self.close()
            return oid
        cursor.execute(
            f'''
            SELECT vk_id FROM Занятость_PlayStation
            WHERE время_начала = ? AND статус = 'Занято' AND дата IN ({ph})
            LIMIT 1
            ''',
            (время_начала, *variants),
        )
        row = cursor.fetchone()
        self.close()
        return int(row['vk_id']) if row else None

    def cancel_ps_booking(self, vk_id: int, дата: str, время_начала: str) -> bool:
        """Отменить только бронь с данным vk_id (своя заявка); дата сопоставляется во всех форматах хранения."""
        conn = self.connect()
        cursor = conn.cursor()

        date_try = []
        for dv in self._ps_date_variants(дата):
            if dv not in date_try:
                date_try.append(dv)

        row = None
        for dv in date_try:
            cursor.execute('''
                SELECT id_заявки, дата FROM Бронирование_PlayStation
                WHERE vk_id = ? AND дата = ? AND время_начала = ? AND IFNULL(статус, '') != 'Отменено'
            ''', (vk_id, dv, время_начала))
            row = cursor.fetchone()
            if row:
                break

        if not row:
            self.close()
            return False

        booking_id = row['id_заявки']
        matched_date = str(row['дата'])
        slot_variants = self._ps_date_variants(matched_date) or [matched_date]

        cursor.execute('''
            UPDATE Бронирование_PlayStation
            SET статус = 'Отменено', дата_подачи = дата_подачи
            WHERE id_заявки = ? AND vk_id = ?
        ''', (booking_id, vk_id))

        ph = ','.join('?' * len(slot_variants))
        cursor.execute(f'''
            UPDATE Занятость_PlayStation
            SET статус = 'Отменено', дата_обновления = datetime('now', 'localtime')
            WHERE vk_id = ? AND время_начала = ? AND статус = 'Занято'
              AND дата IN ({ph})
        ''', (vk_id, время_начала, *slot_variants))

        conn.commit()
        self.close()
        return True


# Пример использования
if __name__ == '__main__':
    # Инициализация базы данных
    db = SQLiteDatabase()
    
    # Добавить пользователя
    db.add_user(123456789, 'Иван', 'Иванов')
    print("✅ Пользователь добавлен")
    
    # Получить список типов служебок
    служебки = db.get_service_types()
    print(f"📋 Типы служебок: {len(служебки)}")
    for с in служебки:
        print(f"  - {с['тип_служебки']}")
    
    # Создать заявку на служебку
    заявка_id = db.add_service_note(
        vk_id=123456789,
        id_служебки=1,
        дата_мероприятия='2025-12-20',
        комментарии='Нужна аудитория на 50 человек'
    )
    print(f"✅ Создана заявка #{заявка_id}")
    
    # Получить список переговорок
    переговорки = db.get_rooms()
    print(f"🏢 Переговорки: {len(переговорки)}")
    for п in переговорки:
        print(f"  - {п['название']} (вместимость: {п['вместимость']})")
    
    # Использование с контекстным менеджером
    print("\n📊 Статистика пользователя:")
    with SQLiteDatabase() as db:
        пользователь = db.get_user(123456789)
        if пользователь:
            print(f"  Имя: {пользователь['имя']} {пользователь['фамилия']}")
            print(f"  Последняя активность: {пользователь['последняя_активность']}")
