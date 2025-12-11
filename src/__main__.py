"""
Точка входа для запуска бота через `python -m src`.
"""

from src.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
