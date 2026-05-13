-- Создание базы данных для VK бота (SQLite версия)
-- Этот скрипт совместим с SQLite Studio

-- Удаление таблиц если существуют (для повторного запуска)
DROP TABLE IF EXISTS MessageHistory;
DROP TABLE IF EXISTS MediaProjects;
DROP TABLE IF EXISTS RoomBookings;
DROP TABLE IF EXISTS ServiceNotes;
DROP TABLE IF EXISTS Statistics;
DROP TABLE IF EXISTS Users;
DROP VIEW IF EXISTS UserActivitySummary;
DROP VIEW IF EXISTS UpcomingBookings;

-- Таблица пользователей
CREATE TABLE Users (
    UserID INTEGER PRIMARY KEY,
    FirstName TEXT,
    LastName TEXT,
    RegistrationDate TEXT DEFAULT (datetime('now', 'localtime')),
    LastActivity TEXT DEFAULT (datetime('now', 'localtime')),
    IsActive INTEGER DEFAULT 1
);

-- Таблица служебных записок
CREATE TABLE ServiceNotes (
    NoteID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL,
    NoteType TEXT NOT NULL, -- 'аудитория', 'освобождение', 'пропуск'
    RequestDate TEXT DEFAULT (datetime('now', 'localtime')),
    TargetDate TEXT,
    Status TEXT DEFAULT 'В обработке', -- 'В обработке', 'Одобрено', 'Отклонено'
    FileAttached INTEGER DEFAULT 0,
    Comments TEXT,
    ProcessedDate TEXT,
    FOREIGN KEY (UserID) REFERENCES Users(UserID)
);

-- Таблица броней переговорок
CREATE TABLE RoomBookings (
    BookingID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL,
    EventName TEXT NOT NULL,
    EventFormat TEXT,
    ParticipantsCount INTEGER,
    BookingDateTime TEXT NOT NULL,
    RoomName TEXT NOT NULL,
    Equipment TEXT,
    RequestDate TEXT DEFAULT (datetime('now', 'localtime')),
    Status TEXT DEFAULT 'Подтверждено', -- 'Подтверждено', 'Отменено'
    FOREIGN KEY (UserID) REFERENCES Users(UserID)
);

-- Таблица медиапроектов
CREATE TABLE MediaProjects (
    ProjectID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL,
    ProjectName TEXT NOT NULL,
    ProjectFormat TEXT,
    SupportNeeded TEXT,
    PublicationPlace TEXT,
    Description TEXT,
    RequestDate TEXT DEFAULT (datetime('now', 'localtime')),
    Status TEXT DEFAULT 'На рассмотрении', -- 'На рассмотрении', 'Одобрено', 'Отклонено'
    ReviewDate TEXT,
    CuratorID INTEGER,
    Comments TEXT,
    FOREIGN KEY (UserID) REFERENCES Users(UserID)
);

-- Таблица истории сообщений (для аналитики)
CREATE TABLE MessageHistory (
    MessageID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserID INTEGER NOT NULL,
    MessageText TEXT,
    BotResponse TEXT,
    Timestamp TEXT DEFAULT (datetime('now', 'localtime')),
    UserState TEXT,
    FOREIGN KEY (UserID) REFERENCES Users(UserID)
);

-- Таблица для хранения статистики
CREATE TABLE Statistics (
    StatID INTEGER PRIMARY KEY AUTOINCREMENT,
    StatDate TEXT DEFAULT (date('now', 'localtime')),
    ServiceNotesCount INTEGER DEFAULT 0,
    BookingsCount INTEGER DEFAULT 0,
    MediaProjectsCount INTEGER DEFAULT 0,
    ActiveUsersCount INTEGER DEFAULT 0,
    MessagesCount INTEGER DEFAULT 0
);

-- Создание индексов для оптимизации запросов
CREATE INDEX IX_ServiceNotes_UserID ON ServiceNotes(UserID);
CREATE INDEX IX_ServiceNotes_Status ON ServiceNotes(Status);
CREATE INDEX IX_ServiceNotes_RequestDate ON ServiceNotes(RequestDate);

CREATE INDEX IX_RoomBookings_UserID ON RoomBookings(UserID);
CREATE INDEX IX_RoomBookings_BookingDateTime ON RoomBookings(BookingDateTime);
CREATE INDEX IX_RoomBookings_Status ON RoomBookings(Status);

CREATE INDEX IX_MediaProjects_UserID ON MediaProjects(UserID);
CREATE INDEX IX_MediaProjects_Status ON MediaProjects(Status);
CREATE INDEX IX_MediaProjects_RequestDate ON MediaProjects(RequestDate);

CREATE INDEX IX_MessageHistory_UserID ON MessageHistory(UserID);
CREATE INDEX IX_MessageHistory_Timestamp ON MessageHistory(Timestamp);

-- Представление для получения статистики по пользователям
CREATE VIEW UserActivitySummary AS
SELECT 
    u.UserID,
    u.FirstName,
    u.LastName,
    u.RegistrationDate,
    u.LastActivity,
    COUNT(DISTINCT sn.NoteID) AS ServiceNotesCount,
    COUNT(DISTINCT rb.BookingID) AS BookingsCount,
    COUNT(DISTINCT mp.ProjectID) AS MediaProjectsCount,
    COUNT(DISTINCT mh.MessageID) AS MessagesCount
FROM Users u
LEFT JOIN ServiceNotes sn ON u.UserID = sn.UserID
LEFT JOIN RoomBookings rb ON u.UserID = rb.UserID
LEFT JOIN MediaProjects mp ON u.UserID = mp.UserID
LEFT JOIN MessageHistory mh ON u.UserID = mh.UserID
GROUP BY u.UserID, u.FirstName, u.LastName, u.RegistrationDate, u.LastActivity;

-- Представление для актуальных броней
CREATE VIEW UpcomingBookings AS
SELECT 
    rb.BookingID,
    u.UserID,
    u.FirstName,
    u.LastName,
    rb.EventName,
    rb.BookingDateTime,
    rb.RoomName,
    rb.ParticipantsCount,
    rb.Equipment
FROM RoomBookings rb
INNER JOIN Users u ON rb.UserID = u.UserID
WHERE rb.BookingDateTime > datetime('now', 'localtime')
  AND rb.Status = 'Подтверждено';

-- Вставка тестовых данных (опционально)
-- INSERT INTO Users (UserID, FirstName, LastName) VALUES (123456789, 'Тест', 'Пользователь');

-- Сообщение о завершении
SELECT 'База данных успешно создана!' AS Message;
SELECT 'Создано таблиц: 6' AS Info;
SELECT 'Создано представлений: 2' AS Info;
SELECT 'Создано индексов: 11' AS Info;

