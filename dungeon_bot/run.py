#!/usr/bin/env python3
"""
Скрипт запуска бота
"""
import asyncio
import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
