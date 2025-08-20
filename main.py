import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv
from flask import Flask, request

# --- Конфигурация логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Загрузка переменных окружения ---
load_dotenv()  # Для локальной разработки из файла .env
BOT_TOKEN = os.environ.get('BOT_TOKEN')
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')  # Важно для webhook на Render

if not BOT_TOKEN:
    raise ValueError("ОШИБКА: Переменная окружения BOT_TOKEN не найдена!")

# --- Инициализация приложения бота и Flask ---
application = Application.builder().token(BOT_TOKEN).build()
flask_app = Flask(__name__)

# --- Обработчики команд для бота ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /start"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.first_name}) запустил бота.")
    await update.message.reply_text(
        "Привет! Я твой первый бот, запущенный на Render! Рад тебя видеть."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает любое текстовое сообщение, которое не является командой."""
    user_message = update.message.text
    logger.info(f"Пользователь {update.effective_user.id} отправил сообщение: {user_message}")
    await update.message.reply_text("Я пока понимаю только команду /start 😉")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки и уведомляет пользователя."""
    logger.error("Исключение при обработке обновления:", exc_info=context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text("Произошла ошибка при обработке вашего запроса.")

# --- Регистрация обработчиков ---
application.add_handler(CommandHandler("start", start_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_error_handler(error_handler)

# --- Webhook и Flask маршруты ---
@flask_app.route('/')
def index():
    return "Бот активен и работает в режиме webhook! 🚀"

@flask_app.route('/webhook', methods=['POST'])
async def webhook():
    """Эндпоинт для получения обновлений от Telegram."""
    try:
        update_data = await request.get_json()
        update = Update.de_json(update_data, application.bot)
        await application.update_queue.put(update)
        return '', 200
    except Exception as e:
        logger.error(f"Ошибка в обработке webhook: {e}")
        return '', 403

async def set_webhook():
    """Устанавливает URL для webhook на серверах Telegram."""
    webhook_url = f"https://{RENDER_EXTERNAL_HOSTNAME}/webhook"
    logger.info(f"Устанавливаю webhook на: {webhook_url}")
    await application.bot.set_webhook(url=webhook_url)

# --- Главная функция для запуска ---
def main():
    # Режим разработки (локальный polling)
    if not RENDER_EXTERNAL_HOSTNAME:
        logger.info("Запуск в режиме Polling...")
        application.run_polling()
    # Режим продакшена на Render (Webhook)
    else:
        # Запускаем установку webhook при старте приложения
        application.run_polling(close_loop=False)  # Инициализирует внутренние loop и прочее
        with flask_app.app_context():
            application.create_task(set_webhook())
        # Flask запустится ниже, а бот будет работать в фоне

if __name__ == '__main__':
    # Если RENDER_EXTERNAL_HOSTNAME задан (на Render), запускаем Flask в основном потоке.
    # Бот работает асинхронно в фоне.
    if RENDER_EXTERNAL_HOSTNAME:
        # Получаем порт из переменной окружения Render
        port = int(os.environ.get('PORT', 10000))
        logger.info(f"Запуск Flask приложения на порту {port}")
        flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    else:
        # Локальный запуск
        main()
