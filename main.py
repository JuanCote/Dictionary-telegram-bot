import logging
import os

from aiogram import Bot, Dispatcher, executor, types, md

from buttons import main_kb

API_TOKEN = os.getenv('telegram-key')

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


@dp.message_handler()
async def echo(message: types.Message):
    await message.answer('Андрей самый тупой чел в мире!')


@dp.message_handler(commands=['start'])
async def echo(message: types.Message):
    await message.answer('lol', reply_markup=main_kb)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)