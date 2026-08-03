import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import datetime
import os
import random
import re
import threading
import time
import json
import traceback

import requests
import urllib3.exceptions
from database_sqlite import SQLiteDatabase
from config import TOKEN, GROUP_ID

try:
    print("🔄 Инициализация VK API...")
    vk_session = vk_api.VkApi(token=TOKEN)
    # Таймауты HTTP: без них загрузка документов/фото может «висеть» при сетевых сбоях
    for _attr in ('http', 'session'):
        _http = getattr(vk_session, _attr, None)
        if _http is not None and hasattr(_http, 'timeout'):
            try:
                _http.timeout = (15, 120)
            except Exception:
                pass
    vk = vk_session.get_api()
    print("✅ VK сессия создана")
    
    # Пробуем получить информацию о группе
    try:
        group_info = vk.groups.getById(group_id=GROUP_ID)
        print(f"✅ Группа найдена: {group_info[0]['name']}")
    except Exception as e:
        print(f"⚠️  Предупреждение: не удалось получить информацию о группе ({e})")
        print("Продолжаем работу...")
    
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    print("✅ Long Poll инициализирован успешно")
    
except vk_api.exceptions.ApiError as e:
    print(f"❌ Ошибка API VK: {e}")
    print("\n💡 Проверьте:")
    print("1. Токен группы VK актуален")
    print("2. GROUP_ID правильный")
    print("3. У токена есть права доступа")
    exit(1)
except Exception as e:
    print(f"❌ Неожиданная ошибка при инициализации VK: {e}")
    exit(1)

# Инициализация базы данных
db = SQLiteDatabase()
print("✅ База данных подключена")

# Состояния пользователей
user_states = {}

# Маппинг названий переговорок на их ID в БД
room_name_to_id = {
    '«Код» – до 7 чел.': 1,
    '«Экология» – до 7 чел.': 2,
    '«Сети» – до 7 чел.': 3,
    '«Индустрия» – до 20 чел.': 5,
    '«Энергия» – до 20 чел.': 6,
    '«Инноватика» – до 20 чел.': 10,
    '«Эврика» – до 20 чел.': 7,
    '«Открытие» – 20–60 чел.': 8,
    '«Лекторий» – 50–100 чел.': 9
}

# Получаем абсолютный путь к директории скрипта
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Шаблоны служебок (пути к файлам)
templates = {
    'аудитория': os.path.join(SCRIPT_DIR, 'templates', 'Шаблон_СЗ_аудитория (2).docx'),
    'освобождение': os.path.join(SCRIPT_DIR, 'templates', 'Шаблон_СЗ_освобождение (2).docx'),
    'пропуск': os.path.join(SCRIPT_DIR, 'templates', 'Шаблон_СЗ_пропуск (2).docx'),
    'поездка': os.path.join(SCRIPT_DIR, 'templates', 'Шаблон_СЗ_освобождение (2).docx'),
    'письмо поддержки': os.path.join(SCRIPT_DIR, 'templates', 'Шаблон_письма_поддержки (2).docx')
}

PROJECT_START_BUTTON = '📋 Проектная среда'
PROJECT_START_INTRO = '''📋 Проектная среда

Регулярные встречи, где команда Башни и приглашённые гости смотрят на ваш проект и подсказывают, как его развивать.

Нажмите «Да», чтобы получить инструкцию по участию.'''
PROJECT_START_FILE = os.path.join(
    SCRIPT_DIR, 'templates', 'КАК НАЧАТЬ РАБОТУ НАД ПРОЕКТОМ В БАШНЕ.docx'
)

OTHER_QUESTION_BUTTON = '❓ Иной вопрос'

# Маппинг типов служебок на ID в БД
service_type_ids = {
    'аудитория': 1,
    'освобождение': 2,
    'пропуск': 3,
    'поездка': 4,
    'письмо поддержки': 5
}

# Инструкции для каждого типа служебки
instructions = {
    'аудитория': '''📋 Пошаговая инструкция для брони аудитории:
1. Укажите дату брони.
2. Заполните шаблон служебной записки.
3. Отправьте заполненную записку на согласование.
4. После согласования аудитория будет забронирована.''',
    'освобождение': '''📋 Пошаговая инструкция для официального освобождения:
1. Укажите дату освобождения.
2. Заполните шаблон служебной записки.''',
    'пропуск': '''📋 Пошаговая инструкция для пропуска посторонних лиц:

1. Укажите дату пропуска.
2. Соберите у участников Согласие на обработку Персональных данных
3. Заполните необходимые Шаблоны
4. Принесите на стойку администратора в коворкинг Башни Согласия в течении 3-х дней после проведения мероприятия''',
    'поездка': '''📋 Заявки на направление в поездку:

Заявки на направление в поездку обучающегося для участия во внешнем мероприятии подаются через корпоративную информационную систему СПбПУ (КИС, https://my.spbstu.ru/) в разделе «Административная деятельность - Стол заявок - Заявка на направление в поездку» не позднее, чем за 10 рабочих дней до начала мероприятия.

Порядок направления обучающихся в поездку на внешние мероприятия определен отдельным нормативным актом - Положением о порядке направления в поездки обучающихся СПбПУ, который размещен в Административном каталоге на сайте СПбПУ (www.spbstu.ru) в подразделе «Управление бухгалтерского учета».''',
    'письмо поддержки': '''📋 Письмо поддержки:

Для получения письма поддержки пожалуйста, оформите письмо строго в соответствии с утвержденным шаблоном (файл «Шаблон_письма_поддержки (2).docx» прикреплен к письму).

Готовые письма необходимо направить специалисту (https://vk.com/nataleeeeeeeeshka) не позднее чем за 5(пять) рабочих дней до окончания срока подачи заявки.

Просим ответственно отнестись к сроку, так как более позднее предоставление документов может поставить под угрозу всю заявку.

Ознакомились с инструкцией?'''
}

# Список переговорок
rooms = [
    '«Код» – до 7 чел.',
    '«Экология» – до 7 чел.',
    '«Сети» – до 7 чел.',
    '«Индустрия» – до 20 чел.',
    '«Энергия» – до 20 чел.',
    '«Инноватика» – до 20 чел.',
    '«Эврика» – до 20 чел.',
    '«Открытие» – 20–60 чел.',
    '«Лекторий» – 50–100 чел.'
]

# --- Медиапроект (отключено, кнопка скрыта) ---
# criteria_file = os.path.join(SCRIPT_DIR, 'criteria.pdf')

PS_OPEN_TIME = datetime.time(9, 30)
PS_CLOSE_TIME = datetime.time(20, 30)
PS_SLOT_HOURS = 1
PS_BOOKING_DAYS = 7

# Бронь переговорок: максимум на сколько дней вперёд от момента ввода даты пользователем
BOOKING_ROOM_MAX_AHEAD_DAYS = 30
# Минимальный срок: не раньше чем через столько календарных дней (1 = только со следующего дня)
BOOKING_MIN_ADVANCE_DAYS = 1
BOOKING_ADMIN_CONFIRM_LINE = 'Ждите ответа администратора о подтверждении брони.'
BOOKING_NAME_PROMPT = (
    '💬 Вы находитесь в разделе Бронирование переговорных. Прежде чем приступить, ознакомьтесь с правилами. '
    'Учтите, что бронировать наши помещения могут Институты и подразделения СПбПУ, студенты и студенческие '
    'объединения, а также партнёры нашего Университета, которые имеют заверенный статус и ответственное лицо '
    'из числа работников. В других случаях — по согласованию с администрацией.\n\n'
    '🏢 Введите название мероприятия:'
)

# Пауза между превью залов (ВК режет частые сообщения одному peer — без паузы long poll «замирает»)
MEETING_ROOM_PREVIEW_DELAY_SEC = 0.4

# Long Poll: пауза при сбоях (экспоненциальный рост до максимума)
LONGPOLL_RETRY_INITIAL_SEC = 5
LONGPOLL_RETRY_MAX_SEC = 120

# Функции для создания клавиатур
def get_start_keyboard():
    """Стартовая клавиатура при входе"""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('🚀 Начать', VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('📝 Служебная записка', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('🏢 Бронь переговорки', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('🎮 Плейстейшен', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button(PROJECT_START_BUTTON, VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button(OTHER_QUESTION_BUTTON, VkKeyboardColor.SECONDARY)
    # keyboard.add_line()
    # keyboard.add_button('🎬 Медиапроект', VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()

def get_ps_hours_keyboard():
    """Клавиатура для выбора количества часов PlayStation"""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('1 час', VkKeyboardColor.PRIMARY)
    keyboard.add_button('2 часа', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('3 часа', VkKeyboardColor.PRIMARY)
    keyboard.add_button('4 часа', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('5 часов', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_ps_menu_keyboard():
    """Клавиатура меню PlayStation"""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('✅ Забронировать', VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('📅 Занятость на неделю', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('❌ Отменить бронь', VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_ps_time_keyboard(available_times):
    """Клавиатура для выбора времени PlayStation (только свободные слоты)"""
    keyboard = VkKeyboard(one_time=True)
    if not available_times:
        keyboard.add_button('❌ Нет свободных слотов', VkKeyboardColor.NEGATIVE)
        keyboard.add_line()
    else:
        for i, time_str in enumerate(available_times, start=1):
            keyboard.add_button(time_str, VkKeyboardColor.PRIMARY)
            if i % 3 == 0:
                keyboard.add_line()
        if len(available_times) % 3 != 0:
            keyboard.add_line()
    keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_booking_menu_keyboard():
    """Клавиатура меню бронирования"""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('📋 Правила и время работы', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('📅 Забронировать аудиторию', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_service_subtype_keyboard():
    """Клавиатура для выбора подтипа служебной записки"""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('Аудитория', VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('Освобождение', VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('Пропуск', VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_service_type_keyboard():
    """Клавиатура для выбора типа служебки"""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('Аудитория', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('Освобождение', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('Пропуск', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('📨 Письма поддержки', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('🌍 Направление в поездку', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_yes_no_keyboard():
    """Клавиатура Да/Нет"""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('Да', VkKeyboardColor.POSITIVE)
    keyboard.add_button('Нет', VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_equipment_keyboard():
    """Клавиатура для выбора оборудования"""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('Проектор', VkKeyboardColor.PRIMARY)
    keyboard.add_button('Доска', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('Компьютер', VkKeyboardColor.PRIMARY)
    keyboard.add_button('Микрофон', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('Готово', VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_booking_format_keyboard():
    """Клавиатура для выбора формата мероприятия"""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('встреча', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('собрание', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('лекция', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('мероприятие', VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('свой вариант', VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def get_rooms_keyboard():
    """Клавиатура для выбора переговорки"""
    keyboard = VkKeyboard(one_time=True)
    for i, room in enumerate(rooms):
        keyboard.add_button(room, VkKeyboardColor.PRIMARY)
        keyboard.add_line()
    keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

# Допустимое число участников для брони: (мин, макс) включительно
ROOM_PEOPLE_BOUNDS = {
    '«Код» – до 7 чел.': (1, 7),
    '«Экология» – до 7 чел.': (1, 7),
    '«Сети» – до 7 чел.': (1, 7),
    '«Индустрия» – до 20 чел.': (1, 20),
    '«Энергия» – до 20 чел.': (1, 20),
    '«Инноватика» – до 20 чел.': (1, 20),
    '«Эврика» – до 20 чел.': (1, 20),
    '«Открытие» – 20–60 чел.': (20, 60),
    '«Лекторий» – 50–100 чел.': (50, 100),
}


def room_allows_people(room: str, people_count) -> bool:
    try:
        n = int(people_count)
    except (TypeError, ValueError):
        return False
    bounds = ROOM_PEOPLE_BOUNDS.get(room)
    if not bounds:
        return False
    lo, hi = bounds
    return lo <= n <= hi


def room_offered_for_people(room: str, people_count) -> bool:
    """Участвует ли зал в списке выбора при данном числе людей (с учётом «не показывать просторные» для малых групп)."""
    try:
        n = int(people_count)
    except (TypeError, ValueError):
        return False
    if not room_allows_people(room, n):
        return False
    # 1–7 человек: только переговорки до 7 мест, без залов на 20 и больше
    if 1 <= n <= 7:
        _, hi = ROOM_PEOPLE_BOUNDS[room]
        if hi > 7:
            return False
    return True


def offered_meeting_rooms(people_count) -> list:
    """Список залов в порядке `rooms`, строго по тем же правилам, что и клавиатура выбора."""
    try:
        n = int(people_count)
    except (TypeError, ValueError):
        return []
    if n < 1:
        return []
    return [room for room in rooms if room_offered_for_people(room, n)]


def parse_participants_count(text: str) -> int:
    """Число участников из ввода пользователя (пробелы, неразрывный пробел, текст вокруг цифр)."""
    if not text:
        raise ValueError('empty')
    s = str(text).strip().replace('\u00a0', ' ')
    m = re.search(r'\d+', s)
    if not m:
        raise ValueError('no digits')
    return int(m.group(0))


def is_weekday(date_value) -> bool:
    """Понедельник–пятница (date или datetime)."""
    if isinstance(date_value, datetime.datetime):
        date_value = date_value.date()
    return date_value.weekday() < 5


def earliest_booking_date() -> datetime.date:
    """Самая ранняя допустимая дата брони (не раньше чем через BOOKING_MIN_ADVANCE_DAYS)."""
    return datetime.date.today() + datetime.timedelta(days=BOOKING_MIN_ADVANCE_DAYS)


def validate_meeting_booking_range(booking_start: datetime.datetime, booking_end: datetime.datetime) -> str | None:
    """
    Проверка даты/времени брони переговорки.
    Возвращает код ошибки или None, если всё в порядке.
    """
    now = datetime.datetime.now()
    if booking_start < now:
        return 'past'
    if booking_start.date() < earliest_booking_date():
        return 'min_advance'
    if not is_weekday(booking_start):
        return 'weekday'
    max_dt = now + datetime.timedelta(days=BOOKING_ROOM_MAX_AHEAD_DAYS)
    if booking_end > max_dt:
        return 'max_ahead'
    return None


def parse_booking_datetime_range(text: str) -> tuple:
    """Диапазон брони переговорки: ДД.ММ.ГГГГ ЧЧ:ММ-ЧЧ:ММ"""
    s = str(text or '').strip().replace('\u00a0', ' ')
    m = re.match(
        r'(\d{1,2}\.\d{1,2}\.\d{4})\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})',
        s
    )
    if not m:
        raise ValueError('format')
    date_str, start_t, end_t = m.group(1), m.group(2), m.group(3)
    start_dt = datetime.datetime.strptime(f'{date_str} {start_t}', '%d.%m.%Y %H:%M')
    end_dt = datetime.datetime.strptime(f'{date_str} {end_t}', '%d.%m.%Y %H:%M')
    if end_dt <= start_dt:
        raise ValueError('end before start')
    return start_dt, end_dt


def format_booking_equipment(equipment) -> str:
    if isinstance(equipment, list):
        equipment = ', '.join(equipment) if equipment else ''
    equipment = str(equipment or '').strip()
    return equipment if equipment else 'не требуется'


def format_booking_time_range(start: datetime.datetime, end: datetime.datetime) -> str:
    return f"{start.strftime('%d.%m.%Y %H:%M')}-{end.strftime('%H:%M')}"


def build_room_booking_summary(booking: dict) -> str:
    time_range = format_booking_time_range(booking['datetime_start'], booking['datetime_end'])
    equipment = format_booking_equipment(booking.get('equipment'))
    return f'''Заявка на бронь переговорки принята!

{BOOKING_ADMIN_CONFIRM_LINE}

Детали брони:
• Мероприятие: {booking['name']}
• Формат: {booking['format']}
• Участников: {booking['people']}
• Дата и время: {time_range}
• Оборудование: {equipment}
• Переговорка: {booking['room']}

Спасибо за обращение!

Просьба зарегистрировать мероприятия в системе Leader-ID не позднее чем за 24 часа до мероприятия, иначе бронь будет аннулирована.
При создании убедитесь в правильности выбранного места проведения, даты и времени.
https://vk.com/@prostranstvo_vozmozhnostey-kak-provesti-meropriyatie-v-bashne
После того, как заведёте мероприятие, вернитесь в сообщения и напишите, что событие было создано.

Каждый участник должен быть зарегистрирован в системе Leader-ID, а также зарегистрироваться на само мероприятие. У стойки администрации необходимо отсканировать персональный QR-код.

Ждём в Башне!'''


# Тексты и файлы превью залов — ключи должны совпадать с элементами `rooms` (один источник для фильтра и картинок)
ROOM_DESCRIPTIONS = {
    '«Код» – до 7 чел.': '1️⃣ «Код» — до 7 человек включительно\nКомпактная переговорка для небольших встреч',
    '«Экология» – до 7 чел.': '2️⃣ «Экология» — до 7 человек включительно\nУютное пространство для команды',
    '«Сети» – до 7 чел.': '3️⃣ «Сети» — до 7 человек включительно\nИдеально для рабочих групп',
    '«Индустрия» – до 20 чел.': '4️⃣ «Индустрия» — до 20 человек включительно\nПереговорка для команд и презентаций',
    '«Энергия» – до 20 чел.': '5️⃣ «Энергия» — до 20 человек включительно\nКомфортное место для мероприятий',
    '«Инноватика» – до 20 чел.': '6️⃣ «Инноватика» — до 20 человек включительно\nПереговорка для командных встреч и лекций',
    '«Эврика» – до 20 чел.': '7️⃣ «Эврика» — до 20 человек включительно\nБольшая переговорка для лекций',
    '«Открытие» – 20–60 чел.': '8️⃣ «Открытие» — от 20 до 60 человек включительно\nКонференц-зал для крупных событий',
    '«Лекторий» – 50–100 чел.': '9️⃣ «Лекторий» — от 50 до 100 человек включительно\nАудитория для массовых мероприятий',
}

# Имя файла в negotiatias/ или None — только текст (без вложения)
ROOM_PHOTO_FILES = {
    '«Код» – до 7 чел.': 'Код.jpg',
    '«Экология» – до 7 чел.': 'Экология.jpg',
    '«Сети» – до 7 чел.': 'Сети.jpg',
    '«Индустрия» – до 20 чел.': 'Индустрия.jpg',
    '«Энергия» – до 20 чел.': 'Энергия.jpg',
    '«Инноватика» – до 20 чел.': 'Инноватика.jpg',
    '«Эврика» – до 20 чел.': 'Эврика.jpg',
    '«Открытие» – 20–60 чел.': 'Открытие.jpg',
    '«Лекторий» – 50–100 чел.': 'Лекторий (1 этаж).jpg',
}


def send_meeting_room_previews(user_id: int, offered_rooms: list) -> None:
    """Отправить описание и фото только для залов из `offered_rooms` (тот же порядок и состав, что у клавиатуры)."""
    for i, room in enumerate(offered_rooms):
        if i > 0:
            time.sleep(MEETING_ROOM_PREVIEW_DELAY_SEC)
        desc = ROOM_DESCRIPTIONS.get(room)
        if desc is None:
            print(f'⚠️ Нет описания для зала в превью: {room!r}')
            continue
        fname = ROOM_PHOTO_FILES.get(room)
        if fname:
            photo_path = os.path.join(SCRIPT_DIR, 'negotiatias', fname)
            if not send_photo(user_id, photo_path, desc):
                send_message(user_id, desc, log_response=False)
        else:
            send_message(user_id, desc, log_response=False)


def get_filtered_rooms_keyboard(people_count):
    """Переговорки по правилам зала; при 1–7 чел. — только залы до 7 мест."""
    try:
        n = int(people_count)
    except (TypeError, ValueError):
        n = 0
    if n < 1:
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
        keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
        return keyboard.get_keyboard(), []

    suitable_rooms = offered_meeting_rooms(n)

    keyboard = VkKeyboard(one_time=True)

    if suitable_rooms:
        for room in suitable_rooms:
            keyboard.add_button(room, VkKeyboardColor.PRIMARY)
            keyboard.add_line()
    else:
        keyboard.add_button('❌ Нет подходящих переговорок', VkKeyboardColor.NEGATIVE)
        keyboard.add_line()

    keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
    keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard(), suitable_rooms

# --- Медиапроект: клавиатуры (отключено) ---
# def get_media_format_keyboard():
#     """Клавиатура для выбора формата медиапроекта"""
#     keyboard = VkKeyboard(one_time=True)
#     keyboard.add_button('горизонтальный ролик', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('подкаст', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('клип', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('фото', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
#     keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
#     return keyboard.get_keyboard()
#
# def get_media_support_keyboard():
#     """Клавиатура для выбора поддержки медиапроекта"""
#     keyboard = VkKeyboard(one_time=True)
#     keyboard.add_button('сценарий + съёмка + монтаж', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('съёмка', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('фотограф + обработка', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
#     keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
#     return keyboard.get_keyboard()
#
# def get_media_publication_keyboard():
#     """Клавиатура для выбора места публикации медиапроекта"""
#     keyboard = VkKeyboard(one_time=True)
#     keyboard.add_button('ВК своего СО', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('ВК Полимера', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('ВК Башни', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('ВК Политеха', VkKeyboardColor.PRIMARY)
#     keyboard.add_line()
#     keyboard.add_button('свой вариант', VkKeyboardColor.SECONDARY)
#     keyboard.add_line()
#     keyboard.add_button('⬅️ Назад', VkKeyboardColor.SECONDARY)
#     keyboard.add_button('🏠 Главное меню', VkKeyboardColor.SECONDARY)
#     return keyboard.get_keyboard()

def send_message(user_id, message, keyboard=None, log_response=True):
    """Отправка сообщения с клавиатурой. При ошибке 912 — без клавиатуры. Ошибки VK не роняют процесс."""
    rid = random.randint(0, 2**31)
    try:
        vk.messages.send(
            user_id=user_id,
            message=message,
            keyboard=keyboard,
            random_id=rid
        )
    except vk_api.exceptions.ApiError as e:
        # 912 — "This is a chat bot feature": в сообществе не включён режим чат-бота / клавиатуры
        if e.code == 912 and keyboard is not None:
            print(
                '⚠️ VK API 912: клавиатуры недоступны. В Управление → Сообщения → Настройки для бота '
                'включите возможности чат-бота. Пока отправляю сообщение без клавиатуры.'
            )
            try:
                vk.messages.send(
                    user_id=user_id,
                    message=message,
                    random_id=random.randint(0, 2**31)
                )
            except Exception as e2:
                print(f'⚠️ Повторная отправка без клавиатуры не удалась: {e2}')
                return False
        elif e.code == 6:
            time.sleep(0.7)
            try:
                vk.messages.send(
                    user_id=user_id,
                    message=message,
                    keyboard=keyboard,
                    random_id=random.randint(0, 2**31)
                )
            except Exception as e2:
                print(f'⚠️ VK API flood retry failed: {e2}')
                return False
        else:
            print(f'⚠️ VK API {e.code}: {e}')
            return False
    except Exception as e:
        print(f'⚠️ Ошибка отправки сообщения: {e}')
        return False
    if log_response:
        try:
            db.log_message(user_id, "", message, user_states.get(user_id, {}).get('step', 'unknown'))
        except Exception:
            pass
    return True

def mark_conversation_for_admin_review(user_id, reason='бронь'):
    """
    После автоответа бота помечает диалог для администраторов сообщества:
    непрочитанным, «без ответа» и важным (как служебные записки).
    """
    for method_name, kwargs in (
        ('markAsUnreadConversation', {'peer_id': user_id}),
        ('markAsAnsweredConversation', {'peer_id': user_id, 'answered': 0}),
        ('markAsImportantConversation', {'peer_id': user_id, 'important': 1}),
    ):
        try:
            getattr(vk.messages, method_name)(**kwargs)
        except Exception as e:
            print(f'⚠️ {method_name} для {user_id} ({reason}): {e}')
    print(f'📬 Диалог {user_id} передан администратору на проверку ({reason})')

def _attachment_from_docs_save(saved):
    """Строка attachment для messages.send из ответа docs.save / VkUpload.document."""
    if isinstance(saved, list):
        if not saved:
            raise ValueError('Пустой ответ docs.save')
        item = saved[0]
    else:
        item = saved
    if not isinstance(item, dict):
        raise ValueError(f'Неожиданный ответ загрузки документа: {type(saved).__name__}')
    if item.get('type') == 'doc' and isinstance(item.get('doc'), dict):
        d = item['doc']
        return f"doc{d['owner_id']}_{d['id']}"
    if 'owner_id' in item and 'id' in item:
        return f"doc{item['owner_id']}_{item['id']}"
    raise ValueError(f'Не удалось извлечь doc из ответа: {item!r}')

def send_document(user_id, file_path, message='', keyboard=None):
    """Отправка документа пользователю (опционально с текстом и клавиатурой в одном сообщении)."""
    try:
        if not os.path.exists(file_path):
            print(f"Файл не найден по пути: {file_path}")
            return False

        file_name = os.path.basename(file_path)
        upload = vk_api.VkUpload(vk_session)
        saved = None
        last_err = None
        for group_id in (GROUP_ID, None):
            try:
                if group_id is not None:
                    saved = upload.document(
                        file_path,
                        title=file_name,
                        message_peer_id=user_id,
                        group_id=group_id,
                    )
                else:
                    saved = upload.document_message(
                        doc=file_path,
                        peer_id=user_id,
                        title=file_name,
                    )
                break
            except Exception as e:
                last_err = e
                saved = None
        if saved is None:
            raise last_err

        attachment = _attachment_from_docs_save(saved)
        text = message.strip() if message else None
        vk.messages.send(
            user_id=user_id,
            message=text,
            attachment=attachment,
            keyboard=keyboard,
            random_id=random.randint(0, 2**31)
        )
        print(f"✅ Файл успешно отправлен: {file_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки файла: {e}")
        print(f"Тип ошибки: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

def send_photo(user_id, photo_path, message=""):
    """Отправка изображения в диалог: загрузка как документ (jpg), без scope photos для photo_messages."""
    try:
        if not os.path.exists(photo_path):
            print(f"Фото не найдено по пути: {photo_path}")
            return False

        file_name = os.path.basename(photo_path)
        upload = vk_api.VkUpload(vk_session)
        saved = None
        last_err = None
        for group_id in (GROUP_ID, None):
            try:
                if group_id is not None:
                    saved = upload.document(
                        photo_path,
                        title=file_name,
                        message_peer_id=user_id,
                        group_id=group_id,
                    )
                else:
                    saved = upload.document_message(
                        doc=photo_path,
                        peer_id=user_id,
                        title=file_name,
                    )
                break
            except Exception as e:
                last_err = e
                saved = None
        if saved is None:
            raise last_err

        attachment = _attachment_from_docs_save(saved)
        text = message.strip() if message else 'Фото переговорки'
        for attempt in range(4):
            try:
                vk.messages.send(
                    user_id=user_id,
                    message=text,
                    attachment=attachment,
                    random_id=random.randint(0, 2**31),
                )
                return True
            except vk_api.exceptions.ApiError as e:
                if e.code == 6 and attempt < 3:
                    time.sleep(0.6 + attempt * 0.4)
                    continue
                print(f'⚠️ Ошибка VK API при отправке фото ({e.code}): {e}')
                return False
    except Exception as e:
        print(f"❌ Ошибка отправки фото (документом): {e}")
        import traceback
        traceback.print_exc()
        return False

def get_ps_available_times(date_obj):
    """Получить свободные слоты PlayStation на дату"""
    date_iso = date_obj.isoformat()
    busy_slots = db.get_ps_busy_slots(date_iso)
    busy_start_times = {slot['время_начала'] for slot in busy_slots}

    available_times = []
    start_dt = datetime.datetime.combine(date_obj, PS_OPEN_TIME)
    end_dt = datetime.datetime.combine(date_obj, PS_CLOSE_TIME)
    while start_dt + datetime.timedelta(hours=PS_SLOT_HOURS) <= end_dt:
        time_str = start_dt.strftime('%H:%M')
        if time_str not in busy_start_times:
            available_times.append(time_str)
        start_dt += datetime.timedelta(hours=PS_SLOT_HOURS)
    return available_times

def build_ps_week_report(start_date):
    """Сформировать отчет по занятости PlayStation на неделю вперед"""
    end_date = start_date + datetime.timedelta(days=PS_BOOKING_DAYS - 1)
    rows = db.get_ps_week_busy_slots(start_date.isoformat(), end_date.isoformat())

    busy_map = {}
    for row in rows:
        busy_map.setdefault(row['дата'], set()).add(f"{row['время_начала']}-{row['время_окончания']}")

    lines = ['📅 Занятость PlayStation на неделю (только будни):']
    for i in range(PS_BOOKING_DAYS):
        day = start_date + datetime.timedelta(days=i)
        if not is_weekday(day):
            continue
        day_iso = day.isoformat()
        day_label = day.strftime('%d.%m.%Y')
        day_busy = sorted(busy_map.get(day_iso, set()))
        if day_busy:
            lines.append(f"{day_label}: {', '.join(day_busy)}")
        else:
            lines.append(f"{day_label}: свободно")
    return "\n".join(lines)

def process_document(user_id, attachment, тип_документа='общий', id_заявки=None):
    """
    Обработка и сохранение документа в базу данных
    
    Args:
        user_id: ID пользователя
        attachment: Объект вложения документа из VK API
        тип_документа: Тип документа ('служебка', 'переговорка', 'медиапроект', 'общий')
        id_заявки: ID связанной заявки (опционально)
        
    Returns:
        ID сохраненного документа в БД или None при ошибке
    """
    try:
        if attachment['type'] != 'doc':
            print(f"⚠️ Неверный тип вложения: {attachment['type']}")
            return None
        
        doc = attachment['doc']
        
        # Извлекаем информацию о документе
        vk_doc_id = doc.get('id')
        vk_owner_id = doc.get('owner_id')
        название_файла = doc.get('title', 'Без названия')
        расширение = doc.get('ext', '').lower()
        размер = doc.get('size', 0)
        url = doc.get('url', '')
        
        # Сохраняем в БД
        doc_id = db.add_document(
            vk_id=user_id,
            vk_doc_id=vk_doc_id,
            vk_owner_id=vk_owner_id,
            название_файла=название_файла,
            расширение=расширение,
            размер=размер,
            url=url,
            тип_документа=тип_документа,
            id_заявки=id_заявки
        )
        
        print(f"✅ Документ сохранен в БД с ID: {doc_id}")
        print(f"   Название: {название_файла}")
        print(f"   Тип: {тип_документа}")
        print(f"   Размер: {размер} байт")
        print(f"   Расширение: {расширение}")
        
        return doc_id
        
    except Exception as e:
        print(f"❌ Ошибка обработки документа: {e}")
        import traceback
        traceback.print_exc()
        return None

def reset_state(user_id):
    """Сброс состояния пользователя"""
    user_states[user_id] = {'step': 'start'}

def get_navigation_state(current_step, dialog_history=None):
    """Определяет предыдущий шаг для кнопки 'Назад'"""
    navigation_map = {
        'choose_service_type': 'start',
        'service_confirm': 'choose_service_type',
        'service_date': 'service_confirm',
        'support_letter_confirm': 'choose_service_type',
        'trip_questions': 'choose_service_type',
        'project_start_confirm': 'start',
        'ps_menu': 'start',
        'ps_date': 'ps_menu',
        'ps_time': 'ps_date',
        'ps_confirm': 'ps_time',
        'ps_cancel_date': 'ps_menu',
        'ps_cancel_time': 'ps_cancel_date',
        'booking_menu': 'start',
        'booking_name': 'booking_menu',
        'booking_format': 'booking_name',
        'booking_capacity': 'booking_format',
        'booking_datetime': 'booking_capacity',
        'booking_equipment_choice': 'booking_datetime',
        'booking_equipment': 'booking_equipment_choice',
        'booking_room': 'booking_equipment',
        'booking_confirm': 'booking_room',
        # 'media_confirm': 'start',
        # 'media_format': 'media_confirm',
        # 'media_support': 'media_format',
        # 'media_publication': 'media_support',
        # 'media_description': 'media_publication',
        # 'media_release_date': 'media_description'
    }
    return navigation_map.get(current_step, 'start')

def update_statistics_periodically():
    """Периодическое обновление статистики (каждый час)"""
    while True:
        try:
            time.sleep(3600)  # Обновляем каждый час
            db.update_daily_statistics()
            print("📊 Статистика обновлена", flush=True)
        except Exception as e:
            print(f"⚠️ Ошибка обновления статистики: {e}", flush=True)


_stats_thread_started = False
_stats_thread_lock = threading.Lock()


def recreate_longpoll():
    """Пересоздать Long Poll после сетевых/API сбоев."""
    global longpoll
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    print('🔄 Long Poll переподключён', flush=True)


def vk_events():
    """События Long Poll с автоповтором при обрыве сети и ошибках VK API."""
    retry_delay = LONGPOLL_RETRY_INITIAL_SEC
    while True:
        try:
            # for + yield надёжнее, чем yield from: исключения из listen() ловятся здесь
            for event in longpoll.listen():
                retry_delay = LONGPOLL_RETRY_INITIAL_SEC
                yield event
        except requests.exceptions.RequestException as e:
            print(f'⚠️ Long Poll (сеть/HTTP): {e}. Повтор через {retry_delay} с...', flush=True)
        except urllib3.exceptions.ProtocolError as e:
            print(f'⚠️ Long Poll (обрыв соединения): {e}. Повтор через {retry_delay} с...', flush=True)
        except (ConnectionError, OSError) as e:
            print(f'⚠️ Long Poll (сокет): {e}. Повтор через {retry_delay} с...', flush=True)
        except json.JSONDecodeError as e:
            print(f'⚠️ Long Poll: некорректный ответ API ({e}). Повтор через {retry_delay} с...', flush=True)
        except vk_api.exceptions.ApiHttpError as e:
            print(f'⚠️ Long Poll (HTTP API): {e}. Повтор через {retry_delay} с...', flush=True)
        except vk_api.exceptions.ApiError as e:
            print(f'⚠️ Long Poll (VK API {getattr(e, "code", "?")}): {e}. Повтор через {retry_delay} с...', flush=True)
        except vk_api.exceptions.VkApiError as e:
            print(f'⚠️ Long Poll (VkApiError): {e}. Повтор через {retry_delay} с...', flush=True)
        except Exception as e:
            print(f'⚠️ Long Poll (неожиданная ошибка): {e}. Повтор через {retry_delay} с...', flush=True)
            traceback.print_exc()
        time.sleep(retry_delay)
        retry_delay = min(int(retry_delay * 1.5) + 1, LONGPOLL_RETRY_MAX_SEC)
        try:
            recreate_longpoll()
        except Exception as re_err:
            print(f'⚠️ Не удалось переподключить Long Poll: {re_err}', flush=True)


def _message_as_dict(message):
    """Нормализовать объект сообщения VK к обычному dict."""
    if message is None:
        return {}
    if isinstance(message, dict):
        return message
    try:
        return dict(message)
    except Exception:
        out = {}
        for key in ('from_id', 'text', 'attachments', 'peer_id', 'id'):
            if hasattr(message, key):
                out[key] = getattr(message, key)
        return out


def handle_incoming_message(message):
    """Обработка одного входящего сообщения (ошибка здесь не роняет весь процесс)."""
    message = _message_as_dict(message)
    user_id = message.get('from_id')
    if not user_id:
        print('⚠️ Сообщение без from_id, пропуск', flush=True)
        return
    text = (message.get('text') or '').strip()
    text_lower = text.lower()

    print(f"📩 Сообщение от {user_id}: {text}", flush=True)

    # Получить информацию о пользователе и сохранить в БД
    try:
        user_info = vk.users.get(user_ids=user_id)[0]
        db.add_user(user_id, user_info.get('first_name'), user_info.get('last_name'))
    except Exception:
        try:
            db.add_user(user_id)
        except Exception as e:
            print(f'⚠️ Не удалось сохранить пользователя: {e}', flush=True)

    # Инициализация состояния пользователя
    if user_id not in user_states:
        user_states[user_id] = {'step': 'start'}

    # Создаем или получаем диалог для пользователя
    if 'dialog_id' not in user_states[user_id]:
        try:
            dialog_id = db.create_dialog(user_id, 'active')
            user_states[user_id]['dialog_id'] = dialog_id
            print(f"✅ Создан диалог ID: {dialog_id} для пользователя {user_id}", flush=True)
        except Exception as e:
            print(f'⚠️ Не удалось создать диалог: {e}', flush=True)

    # Логируем входящее сообщение от пользователя
    try:
        db.log_message(user_id, text, None, user_states[user_id].get('step', 'unknown'))
    except Exception as e:
        print(f"⚠️ Ошибка логирования входящего сообщения: {e}")

    state = user_states[user_id]

    # Режим «иной вопрос»: бот не отвечает, пока пользователь не напишет «начать»
    if state['step'] == 'other_question_silent':
        if text_lower == 'начать' or '🚀 начать' in text_lower:
            reset_state(user_id)
            send_message(
                user_id,
                '👋 Добро пожаловать! Выберите нужную услугу:',
                keyboard=get_main_keyboard()
            )
        return

    # Универсальная обработка кнопки "Главное меню" для всех состояний
    if ('🏠' in text or 'главное меню' in text_lower) and state['step'] != 'start':
        reset_state(user_id)
        send_message(
            user_id,
            '👋 Главное меню:',
            keyboard=get_main_keyboard()
        )
        return

    # Универсальная обработка кнопки "Назад" для всех состояний  
    if ('⬅️' in text and 'назад' in text_lower) or text_lower == 'назад':
        if state['step'] != 'start':
            prev_step = get_navigation_state(state['step'])
            if prev_step == 'start':
                reset_state(user_id)
                send_message(
                    user_id,
                    '👋 Главное меню:',
                    keyboard=get_main_keyboard()
                )
            else:
                state['step'] = prev_step
                # Отправляем соответствующее сообщение для предыдущего шага
                if prev_step == 'choose_service_type':
                    send_message(
                        user_id,
                        '📝 Выберите тип документа:',
                        keyboard=get_service_type_keyboard()
                    )
                elif prev_step == 'booking_menu':
                    send_message(
                        user_id,
                        '🏢 Выберите интересующий пункт:',
                        keyboard=get_booking_menu_keyboard()
                    )
                elif prev_step == 'booking_name':
                    send_message(user_id, BOOKING_NAME_PROMPT)
                elif prev_step == 'booking_format':
                    send_message(
                        user_id,
                        '🎯 Выберите формат мероприятия:',
                        keyboard=get_booking_format_keyboard()
                    )
                elif prev_step == 'booking_capacity':
                    send_message(user_id, '👥 Введите количество участников (число):')
                elif prev_step == 'ps_date':
                    send_message(user_id, '🎮 Введите желаемую дату в формате ДД.ММ.ГГГГ:')
                elif prev_step == 'ps_time':
                    available_times = state.get('ps', {}).get('available_times', [])
                    send_message(
                        user_id,
                        '🕒 Выберите время начала (доступные слоты):',
                        keyboard=get_ps_time_keyboard(available_times)
                    )
                elif prev_step == 'ps_menu':
                    send_message(
                        user_id,
                        f'🎮 Бронирование PlayStation\n\n'
                        f'Бронь доступна только на неделю вперед, только на 1 час и только по будням (пн–пт). '
                        f'Забронировать можно не раньше чем за {BOOKING_MIN_ADVANCE_DAYS} календарный день.\n'
                        f'Продление — на месте у администратора.\n\nВыберите действие:',
                        keyboard=get_ps_menu_keyboard()
                    )
                elif prev_step == 'ps_cancel_date':
                    send_message(user_id, '❌ Введите дату брони для отмены (ДД.ММ.ГГГГ):')
                # elif prev_step == 'media_confirm':
                #     send_message(
                #         user_id,
                #         '🎬 Ознакомьтесь с критериями отбора медиапроектов.\n\nПодтвердите прочтение:',
                #         keyboard=get_yes_no_keyboard()
                #     )
        return

    # НАЧАЛЬНОЕ СОСТОЯНИЕ - показываем стартовую клавиатуру при первом входе
    if state['step'] == 'start' and not any(keyword in text_lower for keyword in ['начать', 'start', 'привет', 'меню', '📝', '🏢', '🎮', 'playstation', 'плейстейш', 'плейстейшен', 'проект', 'башн', 'иной', 'вопрос', 'проектная']):
        send_message(
            user_id,
            '👋 Добро пожаловать в бот Башни Политеха!\n\nНажмите "Начать" для работы с ботом:',
            keyboard=get_start_keyboard()
        )
        return

    # ГЛАВНОЕ МЕНЮ 
    if state['step'] == 'start':
        if text_lower in ['начать', '🚀', 'start', 'привет', 'меню'] or '🚀 начать' in text_lower:
            send_message(
                user_id,
                '👋 Добро пожаловать! Выберите нужную услугу:',
                keyboard=get_main_keyboard()
            )
        elif '📝' in text or 'служебн' in text_lower:
            send_message(
                user_id,
                '📝 Выберите тип документа:',
                keyboard=get_service_type_keyboard()
            )
            state['step'] = 'choose_service_type'
            return
        elif '📨' in text or ('письмо' in text_lower and 'поддержк' in text_lower):
            send_message(
                user_id,
                instructions['письмо поддержки'],
                keyboard=get_yes_no_keyboard()
            )
            state['service_type'] = 'письмо поддержки'
            state['step'] = 'support_letter_confirm'
        elif '🌍' in text or 'поездк' in text_lower:
            send_message(
                user_id,
                instructions['поездка'] + '\n\nВсё понятно? Остались вопросы?',
                keyboard=get_yes_no_keyboard()
            )
            state['step'] = 'trip_questions'
            return
        elif '🏢' in text or 'бронь' in text_lower or 'переговорк' in text_lower:
            send_message(
                user_id,
                '🏢 Добро пожаловать в раздел бронирования аудиторий Башни Политех!\n\nЗдесь вы сможете подобрать помещение для своего мероприятия и узнать все правила. Выберите интересующий пункт меню:',
                keyboard=get_booking_menu_keyboard()
            )
            state['step'] = 'booking_menu'
            return
        elif '🎮' in text or 'playstation' in text_lower or 'плейстейшн' in text_lower or 'плейстейшен' in text_lower or 'ps' == text_lower:
            send_message(
                user_id,
                f'🎮 Бронирование PlayStation\n\n'
                f'Бронь доступна только на неделю вперед, только на 1 час и только по будням (пн–пт). '
                f'Забронировать можно не раньше чем за {BOOKING_MIN_ADVANCE_DAYS} календарный день.\n'
                f'Продление — на месте у администратора.\n\n'
                f'⏰ Время работы: будни с 09:30 до 20:30\n\nВыберите действие:',
                keyboard=get_ps_menu_keyboard()
            )
            state['step'] = 'ps_menu'
            state['ps'] = {}
            return
        elif text == PROJECT_START_BUTTON or 'проектная среда' in text_lower:
            send_message(
                user_id,
                PROJECT_START_INTRO,
                keyboard=get_yes_no_keyboard()
            )
            state['step'] = 'project_start_confirm'
            return
        elif text == OTHER_QUESTION_BUTTON or 'иной вопрос' in text_lower:
            send_message(
                user_id,
                '✍️ Напишите интересующий вас вопрос — администратор Башни увидит его в этом чате и ответит.\n\n'
                'Чтобы снова пользоваться меню бота, напишите «начать».'
            )
            state['step'] = 'other_question_silent'
            return
        # elif '🎬' in text or 'медиа' in text_lower:
        #     send_message(
        #         user_id,
        #         '🎬 Ознакомьтесь с критериями отбора медиапроектов.\n\nПодтвердите прочтение:',
        #         keyboard=get_yes_no_keyboard()
        #     )
        #     state['step'] = 'confirm_criteria'
        #     state['media'] = {}
        #     continue
        else:
            send_message(
                user_id,
                '👋 Выберите услугу из меню:',
                keyboard=get_main_keyboard()
            )

    # СЛУЖЕБНЫЕ ЗАПИСКИ
    elif state['step'] == 'choose_service_type':
        if text_lower == 'аудитория':
            state['service_type'] = text_lower
            send_message(
                user_id,
                '❓ Согласовано ли бронирование аудитории? (128 ауд. ГЗ, каб. В.1.15 НИК, ответственные за корпуса)',
                keyboard=get_yes_no_keyboard()
            )
            state['step'] = 'auditorium_approved'
        elif text_lower == 'освобождение':
            state['service_type'] = text_lower
            send_message(
                user_id,
                '❓ Есть ли официальная причина освобождения? (Мероприятие в Календарном плане, Письмо приглашение и т.д.)',
                keyboard=get_yes_no_keyboard()
            )
            state['step'] = 'release_reason'
        elif text_lower == 'пропуск':
            state['service_type'] = text_lower
            send_message(
                user_id,
                instructions[text_lower] + '\n\n✅ Ознакомились с инструкцией?',
                keyboard=get_yes_no_keyboard()
            )
            state['step'] = 'confirm_instruction'
        elif '📨' in text or ('письмо' in text_lower and 'поддержк' in text_lower):
            send_message(
                user_id,
                instructions['письмо поддержки'],
                keyboard=get_yes_no_keyboard()
            )
            state['service_type'] = 'письмо поддержки'
            state['step'] = 'support_letter_confirm'
        elif '🌍' in text or 'поездк' in text_lower:
            send_message(
                user_id,
                instructions['поездка'] + '\n\nВсё понятно? Остались вопросы?',
                keyboard=get_yes_no_keyboard()
            )
            state['step'] = 'trip_questions'
        else:
            send_message(
                user_id,
                '❌ Пожалуйста, выберите тип из списка:',
                keyboard=get_service_type_keyboard()
            )

    # Обработка начальных вопросов для аудитории
    elif state['step'] == 'auditorium_approved':
        if text_lower == 'да':
            send_message(
                user_id,
                instructions['аудитория'] + '\n\n✅ Ознакомились с инструкцией?',
                keyboard=get_yes_no_keyboard()
            )
            state['step'] = 'confirm_instruction'
        elif text_lower == 'нет':
            send_message(
                user_id,
                '❌ Перед оформлением служебной записки необходимо забронировать аудиторию',
                keyboard=get_main_keyboard()
            )
            reset_state(user_id)
        else:
            send_message(
                user_id,
                '❌ Ответьте "Да" или "Нет":',
                keyboard=get_yes_no_keyboard()
            )

    # Обработка начальных вопросов для освобождения
    elif state['step'] == 'release_reason':
        if text_lower == 'да':
            send_message(
                user_id,
                instructions['освобождение'] + '\n\n✅ Ознакомились с инструкцией?',
                keyboard=get_yes_no_keyboard()
            )
            state['step'] = 'confirm_instruction'
        elif text_lower == 'нет':
            send_message(
                user_id,
                '❌ Перед оформлением служебной записки необходимо получить официальную причину освобождения',
                keyboard=get_main_keyboard()
            )
            reset_state(user_id)
        else:
            send_message(
                user_id,
                '❌ Ответьте "Да" или "Нет":',
                keyboard=get_yes_no_keyboard()
            )

    # Обработка письма поддержки
    elif state['step'] == 'support_letter_confirm':
        if text_lower == 'да':
            # Отправляем шаблон письма поддержки после подтверждения
            template_file = templates.get('письмо поддержки')
            if template_file and os.path.exists(template_file):
                send_document(user_id, template_file)

            send_message(
                user_id,
                '✅ Шаблон отправлен! Пожалуйста, заполните его и направьте специалисту.',
                keyboard=get_main_keyboard()
            )
            reset_state(user_id)
        elif text_lower == 'нет':
            send_message(
                user_id,
                '❌ Пожалуйста, ознакомьтесь с инструкцией и подтвердите:',
                keyboard=get_yes_no_keyboard()
            )
        else:
            send_message(
                user_id,
                '❌ Ответьте "Да" или "Нет":',
                keyboard=get_yes_no_keyboard()
            )

    elif state['step'] == 'project_start_confirm':
        if text_lower == 'да':
            if os.path.exists(PROJECT_START_FILE):
                if send_document(
                    user_id,
                    PROJECT_START_FILE,
                    message='📎 Инструкция по участию в проектной среде.',
                    keyboard=get_main_keyboard(),
                ):
                    reset_state(user_id)
                else:
                    send_message(
                        user_id,
                        '❌ Не удалось отправить файл. Попробуйте нажать «Да» ещё раз.',
                        keyboard=get_yes_no_keyboard(),
                    )
            else:
                send_message(
                    user_id,
                    '❌ Файл инструкции не найден. Обратитесь к администратору.',
                    keyboard=get_main_keyboard(),
                )
                reset_state(user_id)
        elif text_lower == 'нет':
            send_message(
                user_id,
                PROJECT_START_INTRO,
                keyboard=get_yes_no_keyboard(),
            )
        else:
            send_message(
                user_id,
                '❌ Ответьте «Да», чтобы получить инструкцию, или «Нет»:',
                keyboard=get_yes_no_keyboard(),
            )

    # Обработка поездки
    elif state['step'] == 'trip_questions':
        if text_lower == 'нет':
            send_message(
                user_id,
                '✅ Отлично! Оформляйте заявки через КИС.',
                keyboard=get_main_keyboard()
            )
            reset_state(user_id)
        elif text_lower == 'да':
            send_message(
                user_id,
                'ℹ️ Обратитесь с вопросами к специалисту: https://vk.com/nataleeeeeeeeshka',
                keyboard=get_main_keyboard()
            )
            reset_state(user_id)
        else:
            send_message(
                user_id,
                '❌ Ответьте "Да" или "Нет":',
                keyboard=get_yes_no_keyboard()
            )

    elif state['step'] == 'confirm_instruction':
        if text_lower == 'да':
            state['service_data'] = {}  # Инициализация словаря для данных служебки
            # Шаблоны и вложения для пропуска отправляются только после принятой даты (см. enter_date)
            send_message(user_id, '📅 Введите дату служебки в формате ДД.ММ.ГГГГ:')
            state['step'] = 'enter_date'
        elif text_lower == 'нет':
            send_message(
                user_id,
                '❌ Пожалуйста, ознакомьтесь с инструкцией и подтвердите:',
                keyboard=get_yes_no_keyboard()
            )
        else:
            send_message(
                user_id,
                '❌ Ответьте "Да" или "Нет":',
                keyboard=get_yes_no_keyboard()
            )

    elif state['step'] == 'enter_date':
        try:
            date_raw = text.replace(',', '.').replace('/', '.').strip()
            date = datetime.datetime.strptime(date_raw, '%d.%m.%Y').date()
            today = datetime.date.today()
            days_diff = (date - today).days
            date_display = date.strftime('%d.%m.%Y')

            # Валидация: минимум 3 дня, максимум 2 месяца (60 дней)
            if days_diff < 3:
                send_message(
                    user_id,
                    f'❌ Заявка отклонена!\n\nДата должна быть минимум за 3 дня от сегодняшней.\nУказанная дата: {date_display}\nДо даты осталось дней: {days_diff}',
                    keyboard=get_main_keyboard()
                )
                reset_state(user_id)
            elif days_diff > 60:
                max_date = today + datetime.timedelta(days=60)
                send_message(
                    user_id,
                    f'❌ Заявка отклонена!\n\nСлужебную записку можно сформировать только на ближайшие 2 месяца.\nМаксимальная доступная дата: {max_date.strftime("%d.%m.%Y")}',
                    keyboard=get_main_keyboard()
                )
                reset_state(user_id)
            else:
                # Сохраняем дату в состоянии
                if 'service_data' not in state:
                    state['service_data'] = {}
                state['service_data']['date'] = date_display

                service_type = state.get('service_type')
                if service_type == 'пропуск':
                    consent_file = os.path.join(SCRIPT_DIR, 'templates', 'СОГЛАСИЕ НА ОБРАБОТКУ (2).DOC')
                    if os.path.exists(consent_file):
                        send_document(user_id, consent_file)
                    participants_file = os.path.join(SCRIPT_DIR, 'templates', 'Шаблон_Участники (2).xlsx')
                    if os.path.exists(participants_file):
                        send_document(user_id, participants_file)

                template_file = templates.get(service_type)

                if template_file and os.path.exists(template_file):
                    if send_document(user_id, template_file):
                        send_message(
                            user_id,
                            f'✅ Дата принята: {date_display}\n\n📎 Заполните шаблон и отправьте файл в ответ.'
                        )
                        state['step'] = 'wait_file'
                    else:
                        send_message(
                            user_id,
                            '❌ Дата принята, но файл шаблона не удалось отправить (ошибка ВКонтакте при загрузке). '
                            'Попробуйте отправить ту же дату ещё раз через минуту. Если не поможет — напишите администратору.',
                            keyboard=get_main_keyboard(),
                        )
                else:
                    send_message(user_id, '❌ Шаблон не найден. Обратитесь к администратору.')
                    reset_state(user_id)
        except ValueError:
            send_message(user_id, '❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например, 20.12.2025)')

    elif state['step'] == 'wait_file':
        if 'attachments' in message and message['attachments']:
            # Валидация формата файла
            attachment = message['attachments'][0]
            if attachment['type'] == 'doc':
                doc = attachment['doc']
                file_ext = doc.get('ext', '').lower()
                allowed_formats = ['txt', 'docx', 'doc', 'pdf']

                if file_ext not in allowed_formats:
                    send_message(
                        user_id,
                        f'❌ Недопустимый формат файла: .{file_ext}\n\nРазрешенные форматы: {", ".join(allowed_formats)}\n\nПожалуйста, отправьте файл в правильном формате.'
                    )
                    return

            # Помечаем беседу как важную для проверяющих
            try:
                vk.messages.markAsImportantConversation(
                    peer_id=user_id,
                    important=1
                )
                print(f"📌 Диалог с пользователем {user_id} помечен как важный")
            except Exception as e:
                print(f"⚠️ Не удалось пометить диалог как важный: {e}")
                import traceback
                traceback.print_exc()

            # Сохраняем заявку в БД
            заявка_id = None
            try:
                service_type = state.get('service_type')
                service_data = state.get('service_data', {})
                service_id = service_type_ids.get(service_type, 1)
                date_str = service_data.get('date', '')
                dialog_id = state.get('dialog_id')

                # Преобразуем дату в ISO формат
                if date_str:
                    date_obj = datetime.datetime.strptime(date_str, '%d.%m.%Y')
                    date_iso = date_obj.isoformat()
                else:
                    date_iso = datetime.datetime.now().isoformat()

                # Обновляем состояние диалога
                if dialog_id:
                    db.update_dialog_state(dialog_id, 'служебка_обработана', f"Служебка: {service_type}")

                # Сохраняем в БД
                заявка_id = db.add_service_note(
                    vk_id=user_id,
                    id_служебки=service_id,
                    дата_мероприятия=date_iso,
                    id_диалога=dialog_id,
                    комментарии=f"Тип: {service_type}"
                )
                print(f"✅ Служебка сохранена в БД с ID: {заявка_id}, диалог: {dialog_id}")

                # Сохраняем документ в БД и связываем с заявкой
                doc_id = process_document(
                    user_id=user_id,
                    attachment=attachment,
                    тип_документа='служебка',
                    id_заявки=заявка_id
                )

                if doc_id:
                    print(f"✅ Документ #{doc_id} связан с заявкой #{заявка_id}")

            except Exception as e:
                print(f"⚠️ Ошибка сохранения служебки в БД: {e}")
                import traceback
                traceback.print_exc()

            send_message(
                user_id,
                '✅ Служебная записка принята и взята в работу!\n\nВаш запрос обрабатывается. Результат будет отправлен в течение 2-3 рабочих дней.\n\nСпасибо за обращение!',
                keyboard=get_main_keyboard()
            )
            reset_state(user_id)
        else:
            send_message(user_id, '❌ Пожалуйста, отправьте заполненный файл.')

    # БРОНЬ ПЕРЕГОВОРОК - МЕНЮ
    elif state['step'] == 'booking_menu':
        if 'правила' in text_lower or '📋' in text:
            send_message(
                user_id,
                '📋 Правила и время работы\n\n'
                'Кто может бронировать?\n'
                'Бронировать наши помещения могут Институты и подразделения СПбПУ, студенты и студенческие объединения, а также партнёры нашего Университета, которые имеют заверенный статус и ответственное лицо из числа работников. В других случаях — по согласованию с администрацией.\n\n'
                '⏰ Часы работы:\n'
                'По будням с 09:30 до 20:30. Завершение программы — не позднее 20:20.\n\n'
                '📝 Правила регистрации:\n'
                '• Бронирование — не позднее чем за 30 календарных дней до события\n'
                f'• Дата и время мероприятия в боте — не позднее чем через {BOOKING_ROOM_MAX_AHEAD_DAYS} суток с момента заявки\n'
                f'• Бронь возможна только на будни (пн–пт) и не раньше чем за {BOOKING_MIN_ADVANCE_DAYS} календарный день до мероприятия\n'
                '• Обязательна регистрация в Leader-ID минимум за 24 часа до начала. Без активной страницы события бронь аннулируется\n'
                '• Каждый участник должен иметь профиль в Leader-ID; у стойки — скан персонального QR-кода\n'
                '• Мультимедийное оборудование — по запросу через администратора или технического специалиста\n\n'
                'Спасибо, что планируете мероприятия с нами. Ждём вас в Башне!',
                keyboard=get_booking_menu_keyboard()
            )
        elif 'забронировать' in text_lower or '📅' in text:
            send_message(user_id, BOOKING_NAME_PROMPT)
            state['step'] = 'booking_name'
            state['booking'] = {}
        else:
            send_message(
                user_id,
                '🏢 Выберите интересующий пункт:',
                keyboard=get_booking_menu_keyboard()
            )

    elif state['step'] == 'booking_name':
        # Валидация: название не может состоять только из цифр
        if text.isdigit():
            send_message(user_id, '❌ Название мероприятия не может состоять только из цифр. Пожалуйста, введите корректное название:')
        else:
            state['booking']['name'] = text
            send_message(user_id, '📋 Укажите формат мероприятия:', keyboard=get_booking_format_keyboard())
            state['step'] = 'booking_format'

    elif state['step'] == 'booking_format':
        if text_lower == 'свой вариант':
            send_message(user_id, '📝 Введите свой формат мероприятия:')
            state['step'] = 'booking_format_custom'
        else:
            state['booking']['format'] = text
            send_message(user_id, '👥 Укажите количество участников:')
            state['step'] = 'booking_people'

    elif state['step'] == 'booking_format_custom':
        state['booking']['format'] = text
        send_message(user_id, '👥 Укажите количество участников:')
        state['step'] = 'booking_people'

    elif state['step'] == 'booking_people':
        try:
            people_count = parse_participants_count(text)
            if people_count < 1:
                send_message(user_id, '❌ Укажите число участников не меньше 1.')
                return
            state['booking']['people'] = people_count

            filtered_keyboard, suitable_rooms = get_filtered_rooms_keyboard(people_count)

            if suitable_rooms:
                send_message(
                    user_id,
                    f'🏢 Для {people_count} чел. показаны переговорки, которые по правилам можно забронировать при таком числе участников:'
                )
                send_meeting_room_previews(user_id, suitable_rooms)

                send_message(
                    user_id,
                    '🕒 Введите дату и время начала и окончания мероприятия в формате '
                    'ДД.ММ.ГГГГ ЧЧ:ММ-ЧЧ:ММ (например, 27.05.2026 16:30-17:30).\n'
                    f'• Только будни (пн–пт)\n'
                    f'• Не раньше чем через {BOOKING_MIN_ADVANCE_DAYS} календарный день (с {earliest_booking_date().strftime("%d.%m.%Y")})\n'
                    f'• Не позже чем через {BOOKING_ROOM_MAX_AHEAD_DAYS} суток с текущего момента'
                )
                state['step'] = 'booking_datetime'
                state['suitable_rooms'] = suitable_rooms  # Сохраняем список подходящих переговорок
            else:
                send_message(
                    user_id,
                    '❌ Нет переговорки под это число участников (в боте доступны залы до 100 человек по правилам каждого зала).\n\n👥 Укажите другое число участников:'
                )
        except ValueError:
            send_message(user_id, '❌ Введите корректное число участников.')

    elif state['step'] == 'booking_datetime':
        try:
            booking_start, booking_end = parse_booking_datetime_range(text)
            err = validate_meeting_booking_range(booking_start, booking_end)
            max_date = datetime.datetime.now() + datetime.timedelta(days=BOOKING_ROOM_MAX_AHEAD_DAYS)

            if err == 'past':
                send_message(
                    user_id,
                    '❌ Дата не может быть в прошлом. Введите дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ-ЧЧ:ММ:'
                )
            elif err == 'min_advance':
                send_message(
                    user_id,
                    f'❌ Бронь возможна не раньше чем через {BOOKING_MIN_ADVANCE_DAYS} календарный день.\n'
                    f'Самая ранняя допустимая дата: {earliest_booking_date().strftime("%d.%m.%Y")}.\n\n'
                    'Введите другой диапазон (ДД.ММ.ГГГГ ЧЧ:ММ-ЧЧ:ММ):'
                )
            elif err == 'weekday':
                send_message(
                    user_id,
                    '❌ Бронь переговорок доступна только по будням (пн–пт). Введите другую дату и время:'
                )
            elif err == 'max_ahead':
                send_message(
                    user_id,
                    f'❌ Бронь переговорки возможна не дальше чем на {BOOKING_ROOM_MAX_AHEAD_DAYS} суток от момента заявки (около 1 месяца).\n'
                    f'Самая поздняя допустимая дата и время окончания: {max_date.strftime("%d.%m.%Y %H:%M")}\n\n'
                    'Введите другой диапазон (ДД.ММ.ГГГГ ЧЧ:ММ-ЧЧ:ММ):'
                )
            else:
                state['booking']['datetime_start'] = booking_start
                state['booking']['datetime_end'] = booking_end
                send_message(
                    user_id,
                    '🖥️ Необходимо оборудование?',
                    keyboard=get_yes_no_keyboard()
                )
                state['step'] = 'booking_equipment_need'
        except ValueError as e:
            if str(e) == 'end before start':
                send_message(
                    user_id,
                    '❌ Время окончания должно быть позже времени начала. Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ-ЧЧ:ММ (например, 27.05.2026 16:30-17:30):'
                )
            else:
                send_message(
                    user_id,
                    '❌ Неверный формат. Используйте ДД.ММ.ГГГГ ЧЧ:ММ-ЧЧ:ММ (например, 27.05.2026 16:30-17:30):'
                )

    elif state['step'] == 'booking_equipment_need':
        if text_lower == 'да':
            send_message(user_id, '🖥️ Перечислите необходимое оборудование (например: проектор, доска):')
            state['booking']['equipment'] = []
            state['step'] = 'booking_equipment_list'
        elif text_lower == 'нет':
            state['booking']['equipment'] = []
            filtered_keyboard, _ = get_filtered_rooms_keyboard(
                int(state.get('booking', {}).get('people', 1) or 1)
            )

            send_message(user_id, '🚪 Выберите переговорку:', keyboard=filtered_keyboard)
            state['step'] = 'choose_room'
        else:
            send_message(
                user_id,
                '❌ Ответьте "Да" или "Нет":',
                keyboard=get_yes_no_keyboard()
            )

    elif state['step'] == 'booking_equipment_list':
        state['booking']['equipment'] = text
        filtered_keyboard, _ = get_filtered_rooms_keyboard(
            int(state.get('booking', {}).get('people', 1) or 1)
        )

        send_message(user_id, '🚪 Выберите переговорку:', keyboard=filtered_keyboard)
        state['step'] = 'choose_room'

    elif state['step'] == 'choose_room':
        people_n = int(state.get('booking', {}).get('people', 1) or 1)
        offered = offered_meeting_rooms(people_n)
        if text in offered:
            state['booking']['room'] = text
            booking = state['booking']
            dialog_id = state.get('dialog_id')

            # Сохраняем бронь в БД
            try:
                equipment_str = format_booking_equipment(booking.get('equipment'))
                time_range = format_booking_time_range(
                    booking['datetime_start'], booking['datetime_end']
                )

                # Получаем ID переговорки из маппинга
                room_id = room_name_to_id.get(text)

                # Обновляем состояние диалога
                if dialog_id:
                    db.update_dialog_state(
                        dialog_id,
                        'бронь_создана',
                        f"Бронь: {booking['name']}, {time_range}",
                    )

                заявка_id = db.add_room_booking(
                    vk_id=user_id,
                    название_мероприятия=booking['name'],
                    дата_и_время=booking['datetime_start'].isoformat(),
                    id_переговорки=room_id,
                    формат=booking.get('format', ''),
                    количество_человек=booking.get('people', 0),
                    необходимость_оборудования=equipment_str,
                    id_диалога=dialog_id
                )
                print(f"✅ Бронь переговорки сохранена в БД с ID: {заявка_id}, переговорка ID: {room_id}, диалог: {dialog_id}")
            except Exception as e:
                print(f"⚠️ Ошибка сохранения брони в БД: {e}")
                import traceback
                traceback.print_exc()

            send_message(user_id, build_room_booking_summary(booking), keyboard=get_main_keyboard())
            mark_conversation_for_admin_review(user_id, reason='бронь переговорки')
            reset_state(user_id)
        else:
            booking = state.get('booking', {})
            filtered_keyboard, _ = get_filtered_rooms_keyboard(
                int(booking.get('people', 1) or 1)
            )
            send_message(
                user_id,
                f'❌ Эта переговорка не подходит для {booking.get("people", 1)} человек по правилам вместимости.\n\nВыберите переговорку из списка подходящих:',
                keyboard=filtered_keyboard
            )

    # БРОНИРОВАНИЕ PLAYSTATION
    elif state['step'] == 'ps_menu':
        if 'забронировать' in text_lower or '✅' in text:
            send_message(user_id, '🎮 Введите желаемую дату в формате ДД.ММ.ГГГГ:')
            state['step'] = 'ps_date'
        elif 'занятость' in text_lower or '📅' in text:
            report = build_ps_week_report(datetime.date.today())
            send_message(user_id, report, keyboard=get_ps_menu_keyboard())
        elif 'отменить' in text_lower or '❌' in text:
            send_message(
                user_id,
                'Введите дату брони для отмены в формате ДД.ММ.ГГГГ:',
            )
            state['step'] = 'ps_cancel_date'
        else:
            send_message(user_id, 'Выберите действие:', keyboard=get_ps_menu_keyboard())

    elif state['step'] == 'ps_date':
        try:
            date_obj = datetime.datetime.strptime(text, '%d.%m.%Y').date()
            today = datetime.date.today()
            if date_obj < earliest_booking_date():
                send_message(
                    user_id,
                    f'❌ Бронь возможна не раньше чем через {BOOKING_MIN_ADVANCE_DAYS} календарный день '
                    f'(с {earliest_booking_date().strftime("%d.%m.%Y")}). Введите другую дату:'
                )
            elif (date_obj - today).days >= PS_BOOKING_DAYS:
                send_message(user_id, '❌ Бронь доступна только на неделю вперед. Введите другую дату:')
            elif not is_weekday(date_obj):
                send_message(user_id, '❌ PlayStation доступен только по будням (пн–пт). Введите другую дату:')
            else:
                state['ps']['date'] = text
                state['ps']['date_iso'] = date_obj.isoformat()
                available_times = get_ps_available_times(date_obj)
                state['ps']['available_times'] = available_times
                if not available_times:
                    send_message(
                        user_id,
                        f'❌ На {text} нет свободных слотов. Выберите другую дату:'
                    )
                else:
                    send_message(
                        user_id,
                        f'✅ Дата: {text}\n\n🕒 Выберите время начала (доступные слоты):',
                        keyboard=get_ps_time_keyboard(available_times)
                    )
                    state['step'] = 'ps_time'
        except ValueError:
            send_message(user_id, '❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например, 15.03.2026):')

    elif state['step'] == 'ps_time':
        available_times = state.get('ps', {}).get('available_times', [])
        if text not in available_times:
            send_message(
                user_id,
                '❌ Выберите время из доступных слотов:',
                keyboard=get_ps_time_keyboard(available_times)
            )
        else:
            state['ps']['time'] = text
            start_time = datetime.datetime.strptime(text, '%H:%M')
            end_time = (start_time + datetime.timedelta(hours=PS_SLOT_HOURS)).time()
            state['ps']['hours'] = PS_SLOT_HOURS
            state['ps']['end_time'] = end_time.strftime('%H:%M')
            summary = (
                f'📋 Подтвердите заявку на PlayStation:\n\n'
                f'📅 Дата: {state["ps"]["date"]}\n'
                f'🕐 Время: {state["ps"]["time"]} – {state["ps"]["end_time"]}\n'
                f'⏱ Продолжительность: {PS_SLOT_HOURS} ч.\n\n'
                f'Всё верно?'
            )
            send_message(user_id, summary, keyboard=get_yes_no_keyboard())
            state['step'] = 'ps_confirm'

    elif state['step'] == 'ps_confirm':
        if text_lower == 'да':
            ps = state['ps']
            dialog_id = state.get('dialog_id')
            try:
                if not db.is_ps_slot_available(ps['date_iso'], ps['time'], ps['end_time']):
                    available_times = get_ps_available_times(datetime.datetime.strptime(ps['date'], '%d.%m.%Y').date())
                    state['ps']['available_times'] = available_times
                    send_message(
                        user_id,
                        '❌ Этот слот уже занят. Выберите другое время:',
                        keyboard=get_ps_time_keyboard(available_times)
                    )
                    state['step'] = 'ps_time'
                    return

                booking_id = db.add_ps_booking(
                    vk_id=user_id,
                    дата=ps['date_iso'],
                    время_начала=ps['time'],
                    время_окончания=ps['end_time'],
                    количество_часов=ps['hours'],
                    id_диалога=dialog_id
                )
                if not db.add_ps_slot(
                    vk_id=user_id,
                    дата=ps['date_iso'],
                    время_начала=ps['time'],
                    время_окончания=ps['end_time'],
                    id_заявки=booking_id
                ):
                    send_message(
                        user_id,
                        '❌ Этот слот уже занят. Выберите другое время:',
                        keyboard=get_ps_time_keyboard(state['ps'].get('available_times', []))
                    )
                    state['step'] = 'ps_time'
                    return
                print(f'✅ Бронь PlayStation сохранена для пользователя {user_id}')
            except Exception as e:
                print(f'⚠️ Ошибка сохранения брони PS: {e}')
            send_message(
                user_id,
                f'✅ Заявка на PlayStation принята!\n\n'
                f'📅 Дата: {ps["date"]}\n'
                f'🕐 Время: {ps["time"]} – {ps["end_time"]}\n'
                f'⏱ Продолжительность: {ps["hours"]} ч.\n\n'
                f'{BOOKING_ADMIN_CONFIRM_LINE}',
                keyboard=get_main_keyboard()
            )
            mark_conversation_for_admin_review(user_id, reason='PlayStation')
            reset_state(user_id)
        elif text_lower == 'нет':
            send_message(
                user_id,
                '🎮 Введите желаемую дату снова в формате ДД.ММ.ГГГГ:'
            )
            state['ps'] = {}
            state['step'] = 'ps_date'
        else:
            send_message(user_id, '❌ Ответьте "Да" или "Нет":', keyboard=get_yes_no_keyboard())

    elif state['step'] == 'ps_cancel_date':
        try:
            date_obj = datetime.datetime.strptime(text, '%d.%m.%Y').date()
            state['ps_cancel_date_iso'] = date_obj.isoformat()
            state['ps_cancel_date_display'] = text
            send_message(user_id, 'Введите время начала брони для отмены (ЧЧ:ММ):')
            state['step'] = 'ps_cancel_time'
        except ValueError:
            send_message(user_id, '❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:')

    elif state['step'] == 'ps_cancel_time':
        try:
            datetime.datetime.strptime(text, '%H:%M')
            date_iso = state.get('ps_cancel_date_iso')
            if not date_iso:
                send_message(user_id, '❌ Сначала укажите дату брони (ДД.ММ.ГГГГ):')
                state['step'] = 'ps_cancel_date'
                return

            cancelled = db.cancel_ps_booking(user_id, date_iso, text)
            if not cancelled:
                date_display = state.get('ps_cancel_date_display')
                if date_display:
                    cancelled = db.cancel_ps_booking(user_id, date_display, text)

            if cancelled:
                send_message(
                    user_id,
                    f'✅ Бронь на {datetime.datetime.strptime(date_iso, "%Y-%m-%d").strftime("%d.%m.%Y")} {text} отменена.',
                    keyboard=get_ps_menu_keyboard()
                )
            else:
                owner_vk = None
                for d_try in (date_iso, state.get('ps_cancel_date_display')):
                    if not d_try:
                        return
                    owner_vk = db.get_ps_active_owner_for_slot(d_try, text)
                    if owner_vk is not None:
                        break
                if owner_vk is not None and owner_vk != user_id:
                    send_message(
                        user_id,
                        '❌ Нельзя отменить не вашу бронь.',
                        keyboard=get_ps_menu_keyboard(),
                    )
                else:
                    send_message(
                        user_id,
                        '❌ Активная бронь с такой датой и временем не найдена. Проверьте дату и время начала.',
                        keyboard=get_ps_menu_keyboard(),
                    )
            state['step'] = 'ps_menu'
        except ValueError:
            send_message(user_id, '❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 14:30):')

    # МЕДИАПРОЕКТЫ (отключено)
    # elif state['step'] == 'confirm_criteria':
    #     if text_lower == 'да':
    #         if os.path.exists(criteria_file):
    #             send_document(user_id, criteria_file)
    #
    #         template_file = os.path.join(os.path.dirname(__file__), 'template_release.docx')
    #         if os.path.exists(template_file):
    #             send_document(user_id, template_file)
    #
    #         send_message(user_id, '🎬 Введите название проекта:')
    #         state['step'] = 'media_name'
    #     elif text_lower == 'нет':
    #         send_message(
    #             user_id,
    #             '❌ Пожалуйста, ознакомьтесь с критериями и подтвердите:',
    #             keyboard=get_yes_no_keyboard()
    #         )
    #     else:
    #         send_message(
    #             user_id,
    #             '❌ Ответьте "Да" или "Нет":',
    #             keyboard=get_yes_no_keyboard()
    #         )
    #
    # elif state['step'] == 'media_name':
    #     state['media']['name'] = text
    #     send_message(user_id, '📋 Укажите формат проекта:', keyboard=get_media_format_keyboard())
    #     state['step'] = 'media_format'
    #
    # elif state['step'] == 'media_format':
    #     state['media']['format'] = text
    #     send_message(user_id, '🤝 Укажите необходимую поддержку:', keyboard=get_media_support_keyboard())
    #     state['step'] = 'media_support'
    #
    # elif state['step'] == 'media_support':
    #     state['media']['support'] = text
    #     send_message(user_id, '📢 Укажите желаемое место публикации:', keyboard=get_media_publication_keyboard())
    #     state['step'] = 'media_publication'
    #
    # elif state['step'] == 'media_publication':
    #     if text_lower == 'свой вариант':
    #         send_message(user_id, '📝 Введите своё место публикации:')
    #         state['step'] = 'media_publication_custom'
    #     else:
    #         state['media']['publication'] = text
    #         send_message(user_id, '📝 Опишите суть проекта (кратко, основная идея):')
    #         state['step'] = 'media_description'
    #
    # elif state['step'] == 'media_publication_custom':
    #     state['media']['publication'] = text
    #     send_message(user_id, '📝 Опишите суть проекта (кратко, основная идея):')
    #     state['step'] = 'media_description'
    #
    # elif state['step'] == 'media_description':
    #     state['media']['description'] = text
    #     media = state['media']
    #     dialog_id = state.get('dialog_id')
    #     try:
    #         if dialog_id:
    #             db.update_dialog_state(dialog_id, 'медиапроект_создан', f"Медиапроект: {media['name']}")
    #         заявка_id = db.add_media_project(
    #             vk_id=user_id,
    #             название=media['name'],
    #             формат=media['format'],
    #             описание=media['description'],
    #             необходимая_поддержка=media.get('support', ''),
    #             место_публикации=media.get('publication', ''),
    #             id_диалога=dialog_id
    #         )
    #         print(f"✅ Медиапроект сохранен в БД с ID: {заявка_id}, диалог: {dialog_id}")
    #     except Exception as e:
    #         print(f"⚠️ Ошибка сохранения медиапроекта в БД: {e}")
    #         import traceback
    #         traceback.print_exc()
    #     summary = f'''✅ Заявка на медиапроект зарегистрирована!
    #
    # 🎬 Детали проекта:
    # • Название: {media['name']}
    # • Формат: {media['format']}
    # • Поддержка: {media['support']}
    # • Публикация: {media['publication']}
    # • Описание: {media['description']}
    #
    # 📋 Следующие шаги:
    # 1. Ваш проект будет рассмотрен в течение 5 рабочих дней
    # 2. Вы получите уведомление о решении
    # 3. При одобрении с вами свяжется куратор проекта
    #
    # Спасибо! Ваша заявка принята в работу.'''
    #     send_message(user_id, summary, keyboard=get_main_keyboard())
    #     reset_state(user_id)

    # Пользователи, застрявшие в старых шагах медиапроекта — в главное меню
    elif state['step'] in (
        'confirm_criteria', 'media_name', 'media_format', 'media_support',
        'media_publication', 'media_publication_custom', 'media_description',
    ):
        send_message(
            user_id,
            'Раздел «Медиапроект» временно недоступен. Выберите другую услугу:',
            keyboard=get_main_keyboard(),
        )
        reset_state(user_id)

    # ============== ОБРАБОТКА НЕИЗВЕСТНЫХ КОМАНД ==============
    else:
        # Проверяем, не является ли это просто отправкой документа
        if 'attachments' in message and message['attachments']:
            attachment = message['attachments'][0]
            if attachment['type'] == 'doc':
                # Сохраняем документ как "общий"
                doc_id = process_document(
                    user_id=user_id,
                    attachment=attachment,
                    тип_документа='общий',
                    id_заявки=None
                )

                if doc_id:
                    doc = attachment['doc']
                    file_name = doc.get('title', 'документ')
                    send_message(
                        user_id,
                        f'✅ Документ "{file_name}" получен и сохранен!\n\nДокумент будет рассмотрен администратором.',
                        keyboard=get_main_keyboard()
                    )
                else:
                    send_message(
                        user_id,
                        '❌ Ошибка при сохранении документа.',
                        keyboard=get_main_keyboard()
                    )
            else:
                send_message(
                    user_id,
                    '❌ Неизвестная команда. Вернитесь в главное меню:',
                    keyboard=get_main_keyboard()
                )
        else:
            send_message(
                user_id,
                '❌ Неизвестная команда. Вернитесь в главное меню:',
                keyboard=get_main_keyboard()
            )
        # Не сбрасываем состояние при получении документа
        if state['step'] != 'start' and not ('attachments' in message and message['attachments']):
            reset_state(user_id)


def main():
    global _stats_thread_started
    print("🤖 Бот запущен и слушает события...", flush=True)

    # Один поток статистики на весь процесс (при перезапуске main не плодим новые)
    with _stats_thread_lock:
        if not _stats_thread_started:
            stats_thread = threading.Thread(
                target=update_statistics_periodically,
                daemon=True,
                name='stats-updater',
            )
            stats_thread.start()
            _stats_thread_started = True
            print("📊 Поток обновления статистики запущен", flush=True)

    for event in vk_events():
        try:
            if event.type != VkBotEventType.MESSAGE_NEW:
                continue
            if not getattr(event, 'from_user', False):
                continue
            handle_incoming_message(getattr(event, 'message', None))
        except Exception as e:
            print(f"❌ Ошибка обработки события: {e}", flush=True)
            traceback.print_exc()
            try:
                msg = _message_as_dict(getattr(event, 'message', None))
                uid = msg.get('from_id')
                if uid:
                    send_message(
                        uid,
                        '⚠️ Произошла техническая ошибка. Попробуйте ещё раз или вернитесь в главное меню.',
                        keyboard=get_main_keyboard(),
                    )
                    reset_state(uid)
            except Exception as notify_err:
                print(f"⚠️ Не удалось уведомить пользователя об ошибке: {notify_err}", flush=True)


def run_bot_forever():
    """Перезапуск main() при критических сбоях (для работы на сервере без systemd)."""
    restart_delay = 10
    while True:
        try:
            main()
        except KeyboardInterrupt:
            print('⏹ Остановка бота по запросу пользователя.', flush=True)
            break
        except SystemExit:
            raise
        except Exception as e:
            print(f'💥 Критическая ошибка бота, перезапуск через {restart_delay} с: {e}', flush=True)
            traceback.print_exc()
        else:
            print('⚠️ main() завершился неожиданно, перезапуск...', flush=True)
        time.sleep(restart_delay)
        restart_delay = min(restart_delay * 2, 300)
        try:
            recreate_longpoll()
        except Exception as re_err:
            print(f'⚠️ Переподключение Long Poll перед перезапуском: {re_err}', flush=True)


if __name__ == '__main__':
    run_bot_forever()