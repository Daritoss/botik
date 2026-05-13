# Конфигурация подключения к MS SQL Server

DB_CONFIG = {
    'server': 'localhost',  # или IP-адрес сервера
    'database': 'VKBotDatabase',
    'username': 'your_username',  # замените на ваш логин
    'password': 'your_password',  # замените на ваш пароль
    'driver': '{ODBC Driver 17 for SQL Server}'  # или другая версия драйвера
}

# Альтернативный вариант для Windows Authentication
DB_CONFIG_WINDOWS_AUTH = {
    'server': 'localhost',
    'database': 'VKBotDatabase',
    'trusted_connection': 'yes',
    'driver': '{ODBC Driver 17 for SQL Server}'
}
