"""
Запуск VK-бота с UTF-8 в консоли Windows (эмодзи в print).
Использование: python run_server.py
"""
import os
import runpy

if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    runpy.run_module("bot", run_name="__main__")
