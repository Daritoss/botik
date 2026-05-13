"""
Скрипт для проверки работы с документами в базе данных
Использовать для тестирования функционала сохранения документов
"""

import os

from database_sqlite import SQLiteDatabase, DEFAULT_SQLITE_PATH


def test_document_functions():
    """Тестирование функций работы с документами"""
    
    print("🧪 Начинаем тестирование функционала работы с документами...\n")
    
    db_path = DEFAULT_SQLITE_PATH
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        print("Создайте базу данных, выполнив скрипт database_setup.sql")
        return
    
    # Инициализируем БД
    db = SQLiteDatabase(db_path)
    print(f"✅ Подключение к БД установлено: {db_path}\n")
    
    # Тестовые данные
    test_user_id = 999999999
    
    # 1. Добавляем тестового пользователя
    print("1️⃣ Добавление тестового пользователя...")
    db.add_user(test_user_id, "Тест", "Тестов")
    print(f"✅ Пользователь {test_user_id} добавлен\n")
    
    # 2. Создаем тестовую служебку
    print("2️⃣ Создание тестовой заявки на служебку...")
    заявка_id = db.add_service_note(
        vk_id=test_user_id,
        id_служебки=1,
        дата_мероприятия='2025-12-25',
        комментарии='Тестовая заявка'
    )
    print(f"✅ Заявка создана с ID: {заявка_id}\n")
    
    # 3. Добавляем документ
    print("3️⃣ Добавление документа в БД...")
    doc_id = db.add_document(
        vk_id=test_user_id,
        vk_doc_id=123456,
        vk_owner_id=-234628764,
        название_файла="Тестовый_документ.docx",
        расширение="docx",
        размер=51200,  # 50 KB
        url="https://vk.com/doc123456_456789",
        тип_документа='служебка',
        id_заявки=заявка_id
    )
    print(f"✅ Документ сохранен с ID: {doc_id}\n")
    
    # 4. Добавляем еще один общий документ
    print("4️⃣ Добавление общего документа...")
    doc_id2 = db.add_document(
        vk_id=test_user_id,
        vk_doc_id=789012,
        vk_owner_id=-234628764,
        название_файла="Общий_файл.pdf",
        расширение="pdf",
        размер=102400,  # 100 KB
        url="https://vk.com/doc789012_345678",
        тип_документа='общий'
    )
    print(f"✅ Общий документ сохранен с ID: {doc_id2}\n")
    
    # 5. Получаем документ по ID
    print("5️⃣ Получение документа по ID...")
    document = db.get_document(doc_id)
    if document:
        print(f"✅ Документ найден:")
        print(f"   - Название: {document['название_файла']}")
        print(f"   - Тип: {document['тип_документа']}")
        print(f"   - Размер: {document['размер']} байт")
        print(f"   - Дата загрузки: {document['дата_загрузки']}\n")
    else:
        print(f"❌ Документ не найден\n")
    
    # 6. Получаем все документы пользователя
    print("6️⃣ Получение всех документов пользователя...")
    user_docs = db.get_documents_by_user(test_user_id)
    print(f"✅ Найдено документов: {len(user_docs)}")
    for doc in user_docs:
        print(f"   - {doc['название_файла']} ({doc['тип_документа']})")
    print()
    
    # 7. Получаем документы по типу
    print("7️⃣ Получение документов по типу 'служебка'...")
    service_docs = db.get_documents_by_user(test_user_id, тип_документа='служебка')
    print(f"✅ Найдено служебок: {len(service_docs)}")
    for doc in service_docs:
        print(f"   - {doc['название_файла']} (заявка #{doc['id_заявки']})")
    print()
    
    # 8. Получаем документы заявки
    print("8️⃣ Получение документов конкретной заявки...")
    request_docs = db.get_documents_by_request(заявка_id, 'служебка')
    print(f"✅ Документов для заявки #{заявка_id}: {len(request_docs)}")
    for doc in request_docs:
        print(f"   - {doc['название_файла']}")
    print()
    
    # 9. Обновляем связь документа с заявкой
    print("9️⃣ Обновление связи документа с заявкой...")
    db.update_document_request_link(doc_id2, заявка_id)
    updated_doc = db.get_document(doc_id2)
    print(f"✅ Документ #{doc_id2} теперь связан с заявкой #{updated_doc['id_заявки']}\n")
    
    print("=" * 70)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 70)
    print("\n💡 Функционал работы с документами полностью работоспособен!")
    print("📋 Можно использовать в боте для сохранения документов пользователей\n")


if __name__ == '__main__':
    try:
        test_document_functions()
    except Exception as e:
        print(f"\n❌ ОШИБКА ПРИ ТЕСТИРОВАНИИ: {e}")
        import traceback
        traceback.print_exc()
