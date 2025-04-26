import telebot
import sqlite3
import os
import threading
import time
import re
import pytz
from datetime import datetime, timedelta
from telebot import types
from flask import Flask, Response
from apscheduler.schedulers.background import BackgroundScheduler

# =====================================================================================================================

API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
BUG_AND_FEEDBACK_ID = os.environ.get('REPORTS_CHAT_ID')
DATABASE = os.environ.get('DATABASE_PATH', 'Reports.db')
BUGS_DB = os.environ.get('BUGS_DB_PATH', 'BugReports.db')
FEEDBACK_DB = os.environ.get('FEEDBACK_DB_PATH', 'Feedback.db')
PHOTOS_DIR = os.environ.get('PHOTOS_DIR', 'photos')


bot = telebot.TeleBot(API_TOKEN, threaded=True)

# =====================================================================================================================

app = Flask(__name__)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return Response("OK", status=200)

# Запуск Flask в отдельном потоке
def run_flask():
    app.run(host='0.0.0.0', port=5000)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# =====================================================================================================================
# =====================================================================================================================

# Переменные флагов
flag = False
photo_process_flag = False
last_media_group_id = None
processed_media_groups = {}
reject_reason_data = {}
bug_report_states = {}
feedback_states = {}


# Создание папки /photos
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

# =====================================================================================================================
# =====================================================================================================================

# Функция для очистки папки с фото
def clean_photos_dir():
    try:
        now = datetime.now(pytz.timezone('Europe/Moscow'))
        print(f"Попытка очистки папки photos в {now.strftime('%Y-%m-%d %H:%M:%S')}")

        for filename in os.listdir(PHOTOS_DIR):
            file_path = os.path.join(PHOTOS_DIR, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    print(f"Удален файл: {file_path}")
            except Exception as e:
                print(f"Ошибка при удалении файла {file_path}: {e}")

        print("Очистка папки photos завершена")
    except Exception as e:
        print(f"Ошибка в функции очистки папки photos: {e}")


# Настройка планировщика для ежедневной очистки в 00:00 по МСК
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Moscow'))
scheduler.add_job(clean_photos_dir, 'cron', hour=0, minute=0)
scheduler.start()

# =====================================================================================================================
# =====================================================================================================================

# Сообщения
RegistrationTutorialText = (
    'Для использования самоката установите приложение «Akku-Batt» на свой смартфон.\n\n'

    '1) Установите приложение:\n'
    '   - Отсканируйте QR-код на самокате 📱\n'
    '   - Или загрузите из магазинов:\n'
    '     • App Store\n'
    '     • RuStore\n'
    '     • APK-файл с сайта akku-batt.ru\n\n'

    '2) Запустите приложение и:\n'
    '   - Ознакомьтесь с:\n'
    '     • Правилами оферты 📄\n'
    '     • Политикой конфиденциальности\n'
    '   - Подтвердите, что вам 18+\n\n'

    '3) Зарегистрируйтесь:\n'
    '   - Введите свои данные ✏️\n\n'

    '4) Привяжите банковскую карту:\n'
    '   - Для оплаты поездок 💳'
)

# =====================================================================================================================

RentTutorialText = (
    'Для аренды самоката и безопасного завершения поездки:\n\n'

    '1) Начало аренды:\n'
    '   - Найдите самокат на карте или перед собой 🗺️\n'
    '   - Введите номер самоката или отсканируйте QR-код в приложении\n\n'

    '2) Подтверждение аренды:\n'
    '   - Выберите подходящий тариф\n'
    '   - Нажмите "Начать аренду"\n'
    '   - Дождитесь активации (экран самоката загорится) 🔄\n\n'

    '3) Проверка самоката:\n'
    '   - Обязательно осмотрите на повреждения 👀\n'
    '   - Проверьте работу тормозов\n\n'

    '4) Завершение аренды:\n'
    '   - Оставьте на отмеченной парковке 🅿\n'
    '   - Самостоятельно завершите через приложение иначе списание средств продолжится\n\n'

    'Приятной поездки! 🛴💨'
)

# =====================================================================================================================

HowToRideTutorialText = (
    'Инструкция по использованию самоката:\n\n'

    '1) Начало движения:\n'
    '   - Снимите самокат с подножки плавным движением вперед\n'
    '   - Встаньте одной ногой на деку\n'
    '   - Толкнитесь другой ногой\n'
    '   - Плавно нажмите ручку газа под большим пальцем правой руки 👆\n\n'

    '2) Смена скоростных режимов:\n'
    '   - Дважды нажмите кнопку на самокате 🔄\n'
    '   - Выберите режим:\n'
    '     • Эко 🌱\n'
    '     • Драйв 🚀\n'
    '     • Спорт ⚡\n\n'

    '3) Управление фонарём:\n'
    '   - Нажмите один раз кнопку на самокате 💡\n\n'

    '⚠ Не забывайте:\n'
    '   - Включать фары в тёмное время суток 🌙\n'
    '   - Соблюдать правила безопасности\n\n'

    'Желаем вам приятной поездки! 😊'
)

# =====================================================================================================================

WhereMoneyText = (
    'Когда вы берете самокат в аренду, с вашей карты блокируются 300 рублей в качестве залога для оплаты поездки. 💰\n\n'

    'Как происходит списание:\n'
    '1. По окончании поездки с карты списывается стоимость аренды, а заблокированный залог мгновенно возвращается. 🔄\n'
    '2. Если на карте недостаточно средств для оплаты, списание происходит из заблокированной суммы.\n\n'

    'Важно знать:\n'
    '— Обработка транзакции банком может занять до двух суток. ⏳\n'
    '— После обработки вместо 300 рублей вы увидите реальную стоимость поездки, а баланс карты будет пополнен.\n\n'

    'Рекомендация:\n'
    'Для быстрого расчёта с банком убедитесь, что на карте есть дополнительные средства помимо блокируемого залога. 💳'
)

# =====================================================================================================================

HowStopRentText = (
    'Для завершения аренды обязательно выполните следующие действия:\n\n'

    '1. Оставьте самокат на одной из разрешенных парковок, отмеченных в приложении синим цветом. 🅿️\n'
    '2. Нажмите кнопку "Завершить" в приложении.\n'
    '3. Подтвердите завершение аренды, нажав появившуюся кнопку подтверждения.\n'
    '4. Дождитесь сообщения о успешном завершении аренды. ✅\n\n'

    'Важно знать:\n'
    '— Если не завершить аренду, списание средств будет продолжаться. ⚠️\n'
    '— Аренду можно завершить ТОЛЬКО на выделенных парковках.\n\n'

    'Рекомендация:\n'
    'Всегда проверяйте уведомление в приложении о завершении аренды, чтобы избежать лишних списаний. 📱'
)

# =====================================================================================================================

FinishRentManualText = (
    'Если кнопка "Завершить" не отображается на главном экране:\n\n'

    '1. Нажмите на иконку самоката 🛴 (третья сверху справа в приложении, с красной пометкой)\n'
    '2. Выберите самокат, аренду которого хотите завершить\n'
    '3. Появится кнопка "Завершить" - нажмите ее\n\n'

    'Важно:\n'
    '— После нажатия не забудьте подтвердить завершение аренды\n\n'
)

# =====================================================================================================================

ScooterDontWork = (
    'Правила использования самоката в зонах катания:\n\n'

    '— Разрешенная зона отмечена в приложении зеленым цветом ✅\n'
    '— Запрещенная зона выделена красным цветом ⛔\n\n'

    'Что важно знать:\n'
    '1. При выезде за разрешенную зону или въезде в запрещенную самокат автоматически блокируется\n'
    '2. Для разблокировки вернитесь в зеленую зону или покиньте красную\n'
    '3. Если разблокировка не произошла автоматически:\n'
    '   • Нажмите кнопку "Управление" в приложении\n'
    '   • Или используйте иконку самоката 🛴 (третья сверху справа с красной отметкой)\n'
    '   • Выберите нужный самокат и разблокируйте его\n\n'

    'Рекомендация:\n'
    'Следите за границами зон на карте приложения, чтобы избежать блокировки'
)

# =====================================================================================================================

WhereICanRide = (
    'Кататься можно только в разрешенных зонах:\n\n'

    '1) Разрешенные зоны:\n'
    '   - Обозначены зеленым цветом на карте 🗺️\n'
    '   - Кататься можно только в этих зонах\n\n'

    '2) При выезде за границы:\n'
    '   - Самокат автоматически блокируется\n'
    '   - Для разблокировки вернитесь в зеленую зону\n\n'
)

# =====================================================================================================================

ReturnDidNotArrivee = (
    'Если возврат средств не пришёл, значит, '
    'на вашей карте было недостаточно средств для выбранного тарифа 💳\n\n'
    'В таком случае средства были взяты из залога.'
)

# =====================================================================================================================

ScooterControlsText = (
    'Управление элементами самоката:\n\n'

    '1) Фара самоката:\n'
    '   - Управляется кнопкой на рулевой панели\n'
    '   - Одинарное нажатие - вкл/выкл 💡\n'
    '   - Рекомендуется всегда держать фару включенной\n\n'

    '2) Режимы движения:\n'
    '   - Доступны 3 варианта:\n'
    '     • Эко (экономичный) 🌱\n'
    '     • Драйв (стандартный) 🚀\n'
    '     • Спорт (максимальная скорость) ⚡\n'
    '   - Переключение двойным нажатием кнопки\n'
    '   - Выбирайте наиболее комфортный режим\n\n'

    'Для вашей безопасности используйте фару в любое время суток.'
)

# =====================================================================================================================

BugReportAgreement = (
    'Пользовательское соглашение для отправки отчёта об ошибке (баге)\n\n'

    '1. Цель отправки:\n'
    'Вы помогаете нам улучшить сервис. Мы ценим вашу помощь и постараемся исправить проблему максимально быстро. 🚀\n\n'

    '2. Требования к отчёту:\n'
    '- Подробно опишите проблему\n'
    '- Укажите последовательность действий, которые привели к ошибке\n'
    '- По возможности приложите скриншоты/видео 📸\n'
    '- Укажите технические данные (ОС)\n\n'

    '3. Конфиденциальность:\n'
    '- Не отправляйте личные данные (пароли, платёжную информацию) 🔒\n'
    '- Мы можем использовать отчёт для улучшения сервиса без публикации ваших персональных данных\n\n'

    '4. Обратная связь:\n'
    '- Мы рассмотрим ваш отчёт, но не гарантируем ответ на каждый\n'
    '- При исправлении ошибки можем уведомить вас, если вы оставили контакты ✉️\n\n'

    '5. Авторские права:\n'
    '- Отправляя отчёт, вы соглашаетесь на его использование для исправления ошибок\n\n'

    '6. Подтверждение:\n'
    'Нажимая "Согласен с условиями", вы подтверждаете согласие с данными условиями ✅'
)

# =====================================================================================================================

FeedbackAgreement = (
    'Пользовательское соглашение для отправки предложения по улучшению сервиса\n\n'

    '1. Цель отправки:\n'
    'Мы приветствуем ваши идеи по улучшению сервиса! Ваше предложение поможет нам сделать продукт лучше. 💡\n\n'

    '2. Требования к предложению:\n'
    '- Чётко и детально опишите вашу идею\n'
    '- Объясните, как это улучшит сервис\n'
    '- По возможности приведите примеры или аналогии из других сервисов 📊\n\n'

    '3. Конфиденциальность:\n'
    '- Не присылайте конфиденциальную или личную информацию 🔒\n'
    '- Мы можем использовать предложение для разработки, но не обязаны его реализовывать\n\n'

    '4. Обратная связь:\n'
    '- Мы рассмотрим предложение, но не гарантируем ответ или внедрение\n'
    '- При реализации идеи можем уведомить вас (если оставили контакты) ✉️\n\n'

    '5. Авторские права:\n'
    '- Отправляя предложение, вы соглашаетесь на его использование без компенсации\n'
    '- Авторство может быть признано по нашему усмотрению ©️\n\n'

    '6. Подтверждение:\n'
    'Нажимая "Согласен с условиями", вы подтверждаете согласие с данными условиями ✅'
)

# =====================================================================================================================
# =====================================================================================================================

# Локальная база данных для хранения отчетов
def initialize_db():
    create_base = sqlite3.connect(DATABASE)
    cursor = create_base.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            photo TEXT,
            rental_time TEXT,
            scooter_number TEXT,
            phone_number TEXT,
            card_number TEXT,
            description_of_the_problem TEXT,
            sent INTEGER DEFAULT 0,
            returned INTEGER DEFAULT 0
        )
    ''')

    create_base.commit()
    create_base.close()

    # =====================================================================================================================

    bugs_base = sqlite3.connect(BUGS_DB)
    bugs_cursor = bugs_base.cursor()
    bugs_cursor.execute('''
            CREATE TABLE IF NOT EXISTS bug_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                bug_description TEXT,
                steps_to_reproduce TEXT,
                os_info TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                sent INTEGER DEFAULT 0
            )
        ''')
    bugs_base.commit()
    bugs_base.close()

    # =====================================================================================================================

    feedback_base = sqlite3.connect(FEEDBACK_DB)
    feedback_cursor = feedback_base.cursor()
    feedback_cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                idea_description TEXT,
                improvement_explanation TEXT,
                examples TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                sent INTEGER DEFAULT 0
            )
        ''')
    feedback_base.commit()
    feedback_base.close()

initialize_db()

# =====================================================================================================================

# Парсинг базы на неотправленные отчёты
def get_reports():
    try:
        with sqlite3.connect(DATABASE) as parsing_base:
            cursor = parsing_base.cursor()
            cursor.execute("SELECT * FROM reports WHERE sent = 0")
            reports = cursor.fetchall()

    except sqlite3.Error as e:
        print(f"Ошибка при получении отчетов: {e}")
        reports = []

    return reports

# =====================================================================================================================

# Подготовка данных для отправки отчета
def mark_as_sent(report_id):
    try:
        with sqlite3.connect(DATABASE) as check_info:
            cursor = check_info.cursor()
            cursor.execute("UPDATE reports SET sent = 1 WHERE id = ?", (report_id,))
            check_info.commit()

    except sqlite3.Error as e:
        print(f"Ошибка при обновлении отчета: {e}")

# =====================================================================================================================

def send_reports():
    while True:
        reports = get_reports()
        for report in reports:
            try:
                # Распаковываем только нужные нам поля (первые 10)
                id, user_id, photo, rent_data, scooter_number, phone_number, card_number, description_of_the_problem, sent, returned = report[:10]

                try:
                    with sqlite3.connect(DATABASE) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM reports WHERE phone_number = ?", (phone_number,))
                        report_count = cursor.fetchone()[0]
                except sqlite3.Error as e:
                    print(f"Ошибка при получении количества отчетов: {e}")
                    report_count = 1

                message = (
                    f"📝 Report: #{id}\n"
                    f"───────────────────────────────\n"
                    f"👤 User ID: {user_id}\n"
                    f"📱 Номер телефона: {phone_number}\n"
                    f"🔢 Количество отчетов от этого номера: {report_count}\n"
                    f"⏱️ Дата и время начала аренды: {rent_data}\n"
                    f"🛴 Номер самоката: {scooter_number}\n"
                    f"💳 Номер карты: {card_number}\n"
                    f"📋 Описание: {description_of_the_problem}\n"
                    f"───────────────────────────────"
                )

                try:
                    # Создаем интерактивные кнопки
                    markup = types.InlineKeyboardMarkup()
                    approve_button = types.InlineKeyboardButton(
                        "Возврат оформлен",
                        callback_data=f'return_approve_{id}_{user_id}'
                    )
                    reject_button = types.InlineKeyboardButton(
                        "Отклонить заявку",
                        callback_data=f'return_reject_{id}_{user_id}'
                    )
                    markup.add(approve_button, reject_button)

                    if photo and os.path.isfile(photo):
                        try:
                            with open(photo, 'rb') as photo_file:
                                sent_message = bot.send_photo(
                                    CHAT_ID,
                                    photo_file,
                                    caption=message,
                                    reply_markup=markup
                                )
                                if sent_message.message_id:
                                    mark_as_sent(id)
                        except Exception as e:
                            print(f"Ошибка при отправке фото: {e}")
                            bot.send_message(
                                CHAT_ID,
                                message + f"\n[Фото не удалось загрузить: {photo}]",
                                reply_markup=markup
                            )
                            mark_as_sent(id)
                    else:
                        bot.send_message(
                            CHAT_ID,
                            message,
                            reply_markup=markup
                        )
                        mark_as_sent(id)
                except Exception as e:
                    print(f"Ошибка при отправке сообщения: {e}")
                    continue

            except Exception as e:
                print(f"Ошибка при обработке отчета: {e}")
                continue

        time.sleep(60)

# =====================================================================================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('return_'))
def handle_return_decision(call):
    try:
        action, report_id, user_id = call.data.split('_')[1:]
        report_id = int(report_id)
        user_id = int(user_id)

        if action == 'approve':
            # Сохраняем данные для запроса суммы возврата
            reject_reason_data[call.from_user.id] = {
                'report_id': report_id,
                'user_id': user_id,
                'message_id': call.message.message_id,
                'chat_id': call.message.chat.id,
                'current_text': call.message.caption if call.message.caption else call.message.text
            }

            # Запрашиваем сумму возврата
            msg = bot.send_message(
                call.message.chat.id,
                "Укажите сумму возврата ответом на это сообщение:",
                reply_to_message_id=call.message.message_id
            )

            # Регистрируем следующий шаг - обработку суммы
            bot.register_next_step_handler(msg, process_refund_amount)

            bot.answer_callback_query(call.id, "Укажите сумму возврата")

        elif action == 'reject':
            # Сохраняем данные для запроса причины
            reject_reason_data[call.from_user.id] = {
                'report_id': report_id,
                'user_id': user_id,
                'message_id': call.message.message_id,
                'chat_id': call.message.chat.id,
                'current_text': call.message.caption if call.message.caption else call.message.text
            }

            # Запрашиваем причину отклонения
            msg = bot.send_message(
                call.message.chat.id,
                "Укажите причину отклонения заявки ответом на это сообщение:",
                reply_to_message_id=call.message.message_id
            )

            # Регистрируем следующий шаг - обработку причины
            bot.register_next_step_handler(msg, process_reject_reason)

            bot.answer_callback_query(call.id, "Укажите причину отклонения")

    except Exception as e:
        print(f"Ошибка при обработке callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")

# Этот процесс работает во втором потоке
reporting_thread = threading.Thread(target=send_reports)
reporting_thread.start()

# =====================================================================================================================

def process_refund_amount(message):
    try:
        user_id = message.from_user.id
        if user_id not in reject_reason_data:
            return

        # Проверяем, что это ответ на сообщение бота
        if not message.reply_to_message or message.reply_to_message.from_user.id != bot.get_me().id:
            # Удаляем сообщение пользователя, если это не ответ
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except:
                pass

            # Повторно запрашиваем сумму
            msg = bot.send_message(
                message.chat.id,
                "Пожалуйста, укажите сумму возврата, используя кнопку 'Ответить' на моё сообщение.",
                reply_to_message_id=reject_reason_data[user_id]['message_id']
            )
            bot.register_next_step_handler(msg, process_refund_amount)
            return

        # Проверяем, что введена корректная сумма
        try:
            refund_amount = float(message.text.replace(',', '.'))
            if refund_amount <= 0:
                raise ValueError
        except ValueError:
            msg = bot.send_message(
                message.chat.id,
                "Пожалуйста, укажите корректную сумму возврата (число больше 0).",
                reply_to_message_id=reject_reason_data[user_id]['message_id']
            )
            bot.register_next_step_handler(msg, process_refund_amount)
            return

        data = reject_reason_data[user_id]

        # Обновляем статус в БД
        update_return_status(data['report_id'], 1, data['user_id'], refund_amount)

        # Формируем новый текст
        status_text = f"\n\n✅ Заявка одобрена\nСумма возврата: {refund_amount}₽"
        new_text = (data['current_text'] or "") + status_text

        # Обновляем оригинальное сообщение
        try:
            bot.edit_message_text(
                chat_id=data['chat_id'],
                message_id=data['message_id'],
                text=new_text,
                reply_markup=None
            )
        except:
            try:
                bot.edit_message_caption(
                    chat_id=data['chat_id'],
                    message_id=data['message_id'],
                    caption=new_text,
                    reply_markup=None
                )
            except Exception as e:
                print(f"Ошибка при обновлении сообщения: {e}")

        # Отправляем уведомление пользователю
        bot.send_message(
            data['user_id'],
            f"Заявка на возврат одобрена. Сумма возврата: {refund_amount}₽"
        )

        # Удаляем временные данные
        if user_id in reject_reason_data:
            del reject_reason_data[user_id]

    except Exception as e:
        print(f"Ошибка при обработке суммы возврата: {e}")
        bot.send_message(
            message.chat.id,
            "Произошла ошибка при обработке суммы. Попробуйте еще раз."
        )

# =====================================================================================================================

def process_reject_reason(message):
    try:
        user_id = message.from_user.id
        if user_id not in reject_reason_data:
            return

        # Проверяем, что это ответ на сообщение бота
        if not message.reply_to_message or message.reply_to_message.from_user.id != bot.get_me().id:
            # Удаляем сообщение пользователя, если это не ответ
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except:
                pass

            # Повторно запрашиваем причину
            msg = bot.send_message(
                message.chat.id,
                "Пожалуйста, укажите причину отклонения, используя кнопку 'Ответить' на моё сообщение.",
                reply_to_message_id=reject_reason_data[user_id]['message_id']
            )
            bot.register_next_step_handler(msg, process_reject_reason)
            return

        data = reject_reason_data[user_id]
        reason = message.text

        # Обновляем статус в БД
        update_return_status(data['report_id'], 2, data['user_id'])

        # Формируем новый текст
        status_text = f"\n\n❌ Заявка отклонена\nПричина: {reason}"
        new_text = (data['current_text'] or "") + status_text

        # Обновляем оригинальное сообщение
        try:
            bot.edit_message_text(
                chat_id=data['chat_id'],
                message_id=data['message_id'],
                text=new_text,
                reply_markup=None
            )
        except:
            try:
                bot.edit_message_caption(
                    chat_id=data['chat_id'],
                    message_id=data['message_id'],
                    caption=new_text,
                    reply_markup=None
                )
            except Exception as e:
                print(f"Ошибка при обновлении сообщения: {e}")

        # Отправляем уведомление пользователю
        bot.send_message(
            data['user_id'],
            f"Ваша заявка на возврат была отклонена.\nПричина: {reason}"
        )

        # Удаляем временные данные
        if user_id in reject_reason_data:
            del reject_reason_data[user_id]

    except Exception as e:
        print(f"Ошибка при обработке причины отклонения: {e}")
        bot.send_message(
            message.chat.id,
            "Произошла ошибка при обработке причины. Попробуйте еще раз."
        )

# =====================================================================================================================

def update_return_status(report_id, status, user_id, refund_amount=None):
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE reports SET returned = ? WHERE id = ?", (status, report_id))
            conn.commit()

            # # Отправляем сообщение пользователю (для approve)
            # if status == 1 and refund_amount is not None:
            #     bot.send_message(user_id, f"Заявка на возврат одобрена. Сумма возврата: {refund_amount}₽")
            # elif status == 1:
            #     bot.send_message(user_id, "Заявка на возврат одобрена")
            # # Для reject сообщение отправляется в process_reject_reason с причиной

    except sqlite3.Error as e:
        print(f"Ошибка при обновлении статуса возврата: {e}")

# =====================================================================================================================
# =====================================================================================================================

# Функция для получения неотправленных отчетов о багах
def get_unsent_bug_reports():
    try:
        with sqlite3.connect(BUGS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bug_reports WHERE sent = 0")
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Ошибка при получении отчетов о багах: {e}")
        return []

# =====================================================================================================================

# Функция для пометки отчета о баге как отправленного
def mark_bug_report_as_sent(report_id):
    try:
        with sqlite3.connect(BUGS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE bug_reports SET sent = 1 WHERE id = ?", (report_id,))
            conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при обновлении статуса отчета о баге: {e}")

# =====================================================================================================================

# Функция для отправки отчетов о багах
def send_bug_reports():
    while True:
        try:
            reports = get_unsent_bug_reports()
            for report in reports:
                report_id, user_id, bug_description, steps_to_reproduce, os_info, timestamp, sent = report

                message = (
                    f"📝 Новый отчет о баге #{report_id}\n"
                    f"───────────────────────────────\n"
                    f"👤 User ID: {user_id}\n"
                    f"📅 Дата: {timestamp}\n\n"
                    f"📝 Описание бага:\n{bug_description}\n\n"
                    f"🔍 Шаги воспроизведения:\n{steps_to_reproduce}\n\n"
                    f"💻 ОС: {os_info}\n"
                    f"───────────────────────────────"
                )

                try:
                    bot.send_message(
                        BUG_AND_FEEDBACK_ID,
                        message,
                        parse_mode='Markdown'
                    )
                    mark_bug_report_as_sent(report_id)
                except Exception as e:
                    print(f"Ошибка при отправке отчета о баге: {e}")
                    continue

        except Exception as e:
            print(f"Ошибка в основном цикле отправки отчетов о багах: {e}")

        time.sleep(60)


# Запускаем поток для отправки отчетов о багах
bug_reporting_thread = threading.Thread(target=send_bug_reports)
bug_reporting_thread.start()

# =====================================================================================================================
# =====================================================================================================================

# Функция для получения неотправленных предложений
def get_unsent_feedback():
    try:
        with sqlite3.connect(FEEDBACK_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM feedback WHERE sent = 0")
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Ошибка при получении предложений: {e}")
        return []

# =====================================================================================================================

# Функция для пометки предложения как отправленного
def mark_feedback_as_sent(feedback_id):
    try:
        with sqlite3.connect(FEEDBACK_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE feedback SET sent = 1 WHERE id = ?", (feedback_id,))
            conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при обновлении статуса предложения: {e}")

# =====================================================================================================================

# Функция для отправки предложений
def send_feedback_reports():
    while True:
        try:
            feedbacks = get_unsent_feedback()
            for feedback in feedbacks:
                feedback_id, user_id, idea_description, improvement_explanation, examples, timestamp, sent = feedback

                message = (
                    f"💡 Новое предложение #{feedback_id}\n"
                    f"───────────────────────────────\n"
                    f"👤 User ID: {user_id}\n"
                    f"📅 Дата: {timestamp}\n\n"
                    f"📝 Описание идеи:\n{idea_description}\n\n"
                    f"🔄 Как это улучшит сервис:\n{improvement_explanation}\n\n"
                    f"🌐 Примеры/аналогии:\n{examples}\n"
                    f"───────────────────────────────"
                )

                try:
                    bot.send_message(
                        BUG_AND_FEEDBACK_ID,
                        message,
                        parse_mode='Markdown'
                    )
                    mark_feedback_as_sent(feedback_id)
                except Exception as e:
                    print(f"Ошибка при отправке предложения: {e}")
                    continue

        except Exception as e:
            print(f"Ошибка в основном цикле отправки предложений: {e}")

        time.sleep(60)


# Запускаем поток для отправки предложений
feedback_thread = threading.Thread(target=send_feedback_reports)
feedback_thread.start()

# =====================================================================================================================
# =====================================================================================================================


# Обработка кнопки "В главное меню"
@bot.message_handler(func=lambda message: message.text == "В главное меню")
def back_to_menu(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    HelpWithMoneyButton = types.KeyboardButton("Как арендовать самокат❓")
    WhereMyMoneyButton = types.KeyboardButton("Почему списалось 300₽❓")
    CreateReportButton = types.KeyboardButton("Проблема с самокатом❓")
    ProblemWithStopRent = types.KeyboardButton("Как завершить поездку❓")
    BugsAndSuggestions = types.KeyboardButton("Баги или предложения❓")

    markup.add(WhereMyMoneyButton, CreateReportButton)
    markup.add(HelpWithMoneyButton, ProblemWithStopRent)
    markup.add(BugsAndSuggestions)

    bot.send_message(message.chat.id,
                     'Вы в главном меню чат поддержки «Akku-Batt», выберите в чем Вам нужно помочь?',
                     reply_markup=markup)

# =====================================================================================================================

# Обработка кнопки "/start"
@bot.message_handler(commands=['start'])
def start_message(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    HelpWithMoneyButton = types.KeyboardButton("Как арендовать самокат❓")
    WhereMyMoneyButton = types.KeyboardButton("Почему списалось 300₽❓")
    CreateReportButton = types.KeyboardButton("Проблема с самокатом❓")
    ProblemWithStopRent = types.KeyboardButton("Как завершить поездку❓")
    BugsAndSuggestions = types.KeyboardButton("Баги или предложения❓")

    markup.add(WhereMyMoneyButton, CreateReportButton)
    markup.add(HelpWithMoneyButton, ProblemWithStopRent)
    markup.add(BugsAndSuggestions)

    bot.send_message(message.chat.id,
                     'Здравствуйте, Вы написали в чат-бот поддержку «Akku-Batt». В чем Вам нужно помочь?',
                     reply_markup=markup)

# =====================================================================================================================
# =====================================================================================================================

# Обработка кнопки "Назад", которая отправляет в туториал по аренде
@bot.message_handler(func=lambda message: message.text == "🔙 Назад")
def back_to_rent_tutorial(message):
    global flag
    flag = False

    tutorial_how_rent_scooter(message)

# =====================================================================================================================

# Обработка кнопки "Назад", которая отправляет в туториал как остановить аренду
@bot.message_handler(func=lambda message: message.text == "🔙 Нaзaд")
def back_to_stop_rent_tutorial(message):
    global flag
    flag = False

    problem_with_stop_rent(message)

# =====================================================================================================================

# Обработка кнопки "Назад", которая отправляет в туториал как установить приложение
@bot.message_handler(func=lambda message: message.text == "🔙 Нaзад")
def go_back_install_app(message):
    global flag
    flag = False

    how_to_install_app(message)

# =====================================================================================================================

# Обработка кнопки "Назад", которая отправляет в туториал как установить приложение
@bot.message_handler(func=lambda message: message.text == "🔙 Haзaд")
def go_back_install_to_problem(message):
    global flag
    flag = False

    problem_with_scooter(message)

# =====================================================================================================================
# =====================================================================================================================

@bot.message_handler(func=lambda message: message.text == "Баги или предложения❓")
def bugs_and_suggestions(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    ReportBugButton = types.KeyboardButton("Сообщить о баге")
    ReportSuggestionsButton = types.KeyboardButton("Отзывы и предложения")
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(ReportBugButton, ReportSuggestionsButton)
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, "Выберите одну из предложенных кнопок.",
                     reply_markup=markup)

# =====================================================================================================================

@bot.message_handler(func=lambda message: message.text == "Сообщить о баге")
def report_bug_start(message):

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    AgreeButton = types.KeyboardButton("Согласен с условиями")
    DeclineButton = types.KeyboardButton("Отказываюсь принимать условия")
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(AgreeButton, DeclineButton)
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, BugReportAgreement, reply_markup=markup)

# =====================================================================================================================

@bot.message_handler(func=lambda message: message.text == "Согласен с условиями")
def start_bug_report(message):
    bug_report_states[message.from_user.id] = {
        'step': 1,
        'data': {}
    }

    msg = bot.send_message(message.chat.id,
                           "Опишите баг, что он делает и как мешает работе",
                           reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("В главное меню"))

    bot.register_next_step_handler(msg, process_bug_description)

# =====================================================================================================================

def process_bug_description(message):
    user_id = message.from_user.id

    if message.text == "В главное меню":
        del bug_report_states[user_id]
        back_to_menu(message)
        return

    if user_id not in bug_report_states:
        bug_report_states[user_id] = {'step': 1, 'data': {}}

    bug_report_states[user_id]['data']['bug_description'] = message.text
    bug_report_states[user_id]['step'] = 2

    msg = bot.send_message(message.chat.id,
                           "Что вы сделали, чтобы добиться этого бага? Какая последовательность действий?",
                           reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("В главное меню"))

    bot.register_next_step_handler(msg, process_steps_to_reproduce)

# =====================================================================================================================

def process_steps_to_reproduce(message):
    user_id = message.from_user.id

    if message.text == "В главное меню":
        del bug_report_states[user_id]
        back_to_menu(message)
        return
      
    if user_id not in bug_report_states:
        bug_report_states[user_id] = {'step': 2, 'data': {}}

    bug_report_states[user_id]['data']['steps_to_reproduce'] = message.text
    bug_report_states[user_id]['step'] = 3

    msg = bot.send_message(message.chat.id,
                           "Какую ОС (Android/IOS) вы используете?",
                           reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("В главное меню"))

    bot.register_next_step_handler(msg, process_os_info)

# =====================================================================================================================

def process_os_info(message):
    user_id = message.from_user.id

    if message.text == "В главное меню":
        del bug_report_states[user_id]
        back_to_menu(message)
        return

    if user_id not in bug_report_states:
        bug_report_states[user_id] = {'step': 3, 'data': {}}

    bug_report_states[user_id]['data']['os_info'] = message.text

    try:
        with sqlite3.connect(BUGS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bug_reports (user_id, bug_description, steps_to_reproduce, os_info)
                VALUES (?, ?, ?, ?)
            ''', (
                user_id,
                bug_report_states[user_id]['data']['bug_description'],
                bug_report_states[user_id]['data']['steps_to_reproduce'],
                bug_report_states[user_id]['data']['os_info']
            ))
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving bug report: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при сохранении отчета. Пожалуйста, попробуйте позже.")
        return

    bot.send_message(message.chat.id,
                     "Спасибо за действия в улучшении сервиса!",
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("В главное меню"))

    del bug_report_states[user_id]

# =====================================================================================================================

@bot.message_handler(func=lambda message: message.text == "Отказываюсь принимать условия")
def decline_bug_report(message):
    bot.send_message(message.chat.id,
                     "Вы отказались от отправки отчета об ошибке.",
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("В главное меню"))

# =====================================================================================================================
# =====================================================================================================================

# Обработчик кнопки "Отзывы и предложения"
@bot.message_handler(func=lambda message: message.text == "Отзывы и предложения")
def feedback_start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    AgreeButton = types.KeyboardButton("Сoгласен с условиями")
    DeclineButton = types.KeyboardButton("Oтказываюсь принимать условия")
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(AgreeButton, DeclineButton)
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, FeedbackAgreement, reply_markup=markup)

# =====================================================================================================================

# Обработчик согласия с условиями для предложений
@bot.message_handler(func=lambda message: message.text == "Сoгласен с условиями")
def start_feedback_process(message):
    feedback_states[message.from_user.id] = {
        'step': 1,
        'data': {}
    }

    msg = bot.send_message(message.chat.id,
                           "Опишите вашу идею чётко и детально.",
                           reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("В главное меню"))

    bot.register_next_step_handler(msg, process_idea_description)

# =====================================================================================================================

def process_idea_description(message):
    user_id = message.from_user.id

    if message.text == "В главное меню":
        del feedback_states[user_id]
        back_to_menu(message)
        return

    if user_id not in feedback_states:
        feedback_states[user_id] = {'step': 1, 'data': {}}

    feedback_states[user_id]['data']['idea_description'] = message.text
    feedback_states[user_id]['step'] = 2

    msg = bot.send_message(message.chat.id,
                           "Объясните, как это улучшит сервис.",
                           reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("В главное меню"))

    bot.register_next_step_handler(msg, process_improvement_explanation)

# =====================================================================================================================

def process_improvement_explanation(message):
    user_id = message.from_user.id

    if message.text == "В главное меню":
        del feedback_states[user_id]
        back_to_menu(message)
        return

    if user_id not in feedback_states:
        feedback_states[user_id] = {'step': 2, 'data': {}}

    feedback_states[user_id]['data']['improvement_explanation'] = message.text
    feedback_states[user_id]['step'] = 3

    msg = bot.send_message(message.chat.id,
                           "Если возможно, приведите примеры или аналогии из других сервисов.",
                           reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("В главное меню"))

    bot.register_next_step_handler(msg, process_examples)

# =====================================================================================================================

def process_examples(message):
    user_id = message.from_user.id

    if message.text == "В главное меню":
        del feedback_states[user_id]
        back_to_menu(message)
        return

    if user_id not in feedback_states:
        feedback_states[user_id] = {'step': 3, 'data': {}}

    feedback_states[user_id]['data']['examples'] = message.text

    try:
        with sqlite3.connect(FEEDBACK_DB) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feedback (user_id, idea_description, improvement_explanation, examples)
                VALUES (?, ?, ?, ?)
            ''', (
                user_id,
                feedback_states[user_id]['data']['idea_description'],
                feedback_states[user_id]['data']['improvement_explanation'],
                feedback_states[user_id]['data']['examples']
            ))
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving feedback: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при сохранении предложения. Пожалуйста, попробуйте позже.")
        return

    bot.send_message(message.chat.id,
                     "Спасибо за ваше предложение! Мы ценим ваш вклад в улучшение сервиса.",
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("В главное меню"))

    del feedback_states[user_id]

# =====================================================================================================================

# Обработчик отказа от условий для предложений
@bot.message_handler(func=lambda message: message.text == "Oтказываюсь принимать условия")
def decline_feedback(message):
    bot.send_message(message.chat.id,
                     "Вы отказались от отправки предложения.",
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("В главное меню"))

# =====================================================================================================================
# =====================================================================================================================


# Обработка кнопки "Почему списалось 300 рублей?"
@bot.message_handler(func=lambda message: message.text == "Почему списалось 300₽❓")
def where_my_money_button(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    ReturnDidNotArrive = types.KeyboardButton("💸 Не пришёл возврат?")
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(ReturnDidNotArrive)
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, WhereMoneyText,
                     reply_markup=markup)

# =====================================================================================================================

# Обработка кнопки "Не пришёл возврат?"
@bot.message_handler(func=lambda message: message.text == "💸 Не пришёл возврат?")
def return_did_not_arrive(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, ReturnDidNotArrivee, reply_markup=markup)

# =====================================================================================================================
# =====================================================================================================================

# Обработка кнопки "Как арендовать самокат?"
@bot.message_handler(func=lambda message: message.text == "Как арендовать самокат❓")
def tutorial_how_rent_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    TutorialHowInstallAppButton = types.KeyboardButton("🛴 Как установить приложение?")
    TutorialHowStartRentButton = types.KeyboardButton("🛴 Как арендовать самокат?")
    WhereGreenZone = types.KeyboardButton("⚠️ Разрешенные зоны для катания")
    TutorialHowRideButton = types.KeyboardButton("🛴 Как кататься?")
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(TutorialHowInstallAppButton, TutorialHowStartRentButton)
    markup.add(TutorialHowRideButton, WhereGreenZone)
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, 'Выберите, что вас интересует:', reply_markup=markup)

# =====================================================================================================================

# Обработка кнопки "Как установить приложение?"
@bot.message_handler(func=lambda message: message.text == "🛴 Как установить приложение?")
def how_to_install_app(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentTutorial = types.KeyboardButton("🔙 Назад")
    markup.add(BackToRentTutorial, BackToMainMenuButton)

    bot.send_message(message.chat.id, RegistrationTutorialText, reply_markup=markup)

# =====================================================================================================================

# Обработка кнопки "Как взять в аренду самокат?"
@bot.message_handler(func=lambda message: message.text == "🛴 Как арендовать самокат?")
def how_to_rent_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Назад")
    markup.add(BackToRentMenuButton, BackToMainMenuButton)

    bot.send_message(message.chat.id, RentTutorialText, reply_markup=markup)

# =====================================================================================================================

# Обработка кнопки "Как кататься?"
@bot.message_handler(func=lambda message: message.text == "🛴 Как кататься?")
def how_to_ride_on_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Назад")

    markup.add(BackToRentMenuButton, BackToMainMenuButton)

    bot.send_message(message.chat.id, HowToRideTutorialText, reply_markup=markup)

# =====================================================================================================================

# Обработка кнопки "Где можно кататься?"
@bot.message_handler(func=lambda message: message.text == "⚠️ Разрешенные зоны для катания")
def where_you_can_ride(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Назад")

    markup.add(BackToMainMenuButton)
    markup.add(BackToRentMenuButton)

    bot.send_message(
        message.chat.id, WhereICanRide, reply_markup=markup
    )
# =====================================================================================================================
# =====================================================================================================================

# Обработка кнопки "Не могу завершить аренду, что делать?"
@bot.message_handler(func=lambda message: message.text == "Как завершить поездку❓")
def problem_with_stop_rent(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    HowToEndRent = types.KeyboardButton("⚠️ Как завершить аренду?")
    DontHaveButtonStopRent = types.KeyboardButton("⚠️ Нет кнопки завершить")
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(HowToEndRent, DontHaveButtonStopRent)
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id,'Выберите, что вас интересует:', reply_markup=markup)

# =====================================================================================================================

# Обработка кнопки "Нет кнопки завершить"
@bot.message_handler(func=lambda message: message.text == "⚠️ Нет кнопки завершить")
def how_to_end_rent(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Нaзaд")

    markup.add(BackToMainMenuButton)
    markup.add(BackToRentMenuButton)

    bot.send_message(message.chat.id, FinishRentManualText,
                     reply_markup=markup)

# =====================================================================================================================

# Обработка кнопки "Как завершить аренду?"
@bot.message_handler(func=lambda message: message.text == "⚠️ Как завершить аренду?")
def how_to_end_rent(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Нaзaд")

    markup.add(BackToMainMenuButton)
    markup.add(BackToRentMenuButton)

    bot.send_message(message.chat.id, HowStopRentText,
                     reply_markup=markup)


# =====================================================================================================================

# Обработка кнопки "Где можно кататься?"
@bot.message_handler(func=lambda message: message.text == "⚠️ Где можно кататься?")
def where_you_can_ride(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Нaзaд")

    markup.add(BackToMainMenuButton)
    markup.add(BackToRentMenuButton)

    bot.send_message(
        message.chat.id, WhereICanRide, reply_markup=markup
    )

# =====================================================================================================================
# =====================================================================================================================

# Обработка кнопки "Не нашли что искали?"
@bot.message_handler(func=lambda message: message.text == "Не нашли что искали❓")
def did_not_find_the_researched(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, 'Если Вы не нашли нужный вам пункт, позвоните по номеру: +7(926)013-43-85',
                     reply_markup=markup)

# =====================================================================================================================
# =====================================================================================================================

# Обработка кнопки "Где можно кататься?"
@bot.message_handler(func=lambda message: message.text == "⚠️ Где можнo кататься?")
def where_you_can_ride(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Haзaд")

    markup.add(BackToMainMenuButton)
    markup.add(BackToRentMenuButton)

    bot.send_message(
        message.chat.id, WhereICanRide, reply_markup=markup
    )

# =====================================================================================================================

# Обработка кнопки "Самокат перестал ехать"
@bot.message_handler(func=lambda message: message.text == "⚠️ Самoкат перестал ехать")
def scooter_not_goes(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Haзaд")

    markup.add(BackToMainMenuButton)
    markup.add(BackToRentMenuButton)

    bot.send_message(message.chat.id, ScooterDontWork,
                     reply_markup=markup)

# =====================================================================================================================

@bot.message_handler(func=lambda message: message.text == "🛴 Cамокат едет медленно?")
def why_scooter_so_slowly(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Haзaд")

    markup.add(BackToRentMenuButton, BackToMainMenuButton)

    bot.send_message(message.chat.id, ScooterControlsText, reply_markup=markup)

# =====================================================================================================================

@bot.message_handler(func=lambda message: message.text == "Проблема с самокатом❓")
def problem_with_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    ScooterNotGoes = types.KeyboardButton("⚠️ Самoкат перестал ехать")
    ScooterIsSoSlowly = types.KeyboardButton("🛴 Cамокат едет медленно?")
    INeedReturn = types.KeyboardButton("Нужен возврат❓")
    DidNotFindTheSearched = types.KeyboardButton("Не нашли что искали❓")
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(INeedReturn, ScooterNotGoes)
    markup.add(ScooterIsSoSlowly, DidNotFindTheSearched)
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, 'Выберите, что вас интересует:', reply_markup=markup)

# =====================================================================================================================
# =====================================================================================================================

# Обработка кнопки "Нужен возврат?", начало подготовки отчета
@bot.message_handler(func=lambda message: message.text == "Нужен возврат❓")
def report(message):
    global flag, photo_process_flag
    flag = True
    photo_process_flag = True 

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, "Для оформления заявки на возврат средств потребуется предоставить дополнительные данные. \n\n"
                                      "Пожалуйста, прикрепите одну фотографию вашего самоката.",
                     reply_markup=markup)

# =====================================================================================================================

# Сохранение фото с проверкой количества и на валидность
@bot.message_handler(content_types=['photo', 'video'])
def handle_media(message):
    global flag, photo_process_flag, processed_media_groups
    if not flag:
        return

    if message.media_group_id is not None:
        if message.media_group_id not in processed_media_groups:
            processed_media_groups[message.media_group_id] = True
            bot.send_message(message.chat.id, "Пришлите только одно фото самоката.")
        return
    else:
        processed_media_groups = {}

    if message.content_type == 'video':
        bot.send_message(message.chat.id, "Для создания заявки принимается только фото.\n"
                                          "Пришлите пожалуйста фото самоката.")
        return

    try:
        # Обработка одиночного фото
        photo_file = bot.get_file(message.photo[-1].file_id)
        photo_path = os.path.join(PHOTOS_DIR, f"{photo_file.file_id}.jpg")

        downloaded_file = bot.download_file(photo_file.file_path)
        with open(photo_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("В главное меню"))

        bot.send_message(message.chat.id, "Укажите пожалуйста время начала аренды (ДД.ММ ЧЧ:ММ)",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_rental_time, photo_path)

        photo_process_flag = False

    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при обработке фото: {str(e)}")

# =====================================================================================================================

# Проверка на валидность отправки данных (Дата и время)
def validate_correct_rental_time(rental_time):
    try:
        datetime.strptime(rental_time, "%d.%m %H:%M")
        return True

    except ValueError:
        return False

# Проверка на валидность отправки данных (Насколько давно была дата)
def validate_rental_time(rental_time):
    try:
        rental_datetime = datetime.strptime(rental_time, "%d.%m %H:%M")
        now_time = datetime.now()
        rental_datetime = rental_datetime.replace(year=now_time.year)

        if rental_datetime < now_time - timedelta(days=30):
            return False

        return True
    except ValueError:
        return False

# =====================================================================================================================

# Получение даты и времени
def process_rental_time(message, photo_path):
    if message.text == "В главное меню":
        back_to_menu(message)
        return

    rental_time = message.text.strip()

    if not validate_correct_rental_time(rental_time):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("В главное меню"))
        bot.send_message(message.chat.id,
                         "Некорректный формат времени. Пожалуйста, введите время в формате: ДД.ММ ЧЧ:ММ",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_rental_time, photo_path)
        return

    elif not validate_rental_time(rental_time):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("В главное меню"))
        bot.send_message(message.chat.id,
                         "Дата вашей аренды должна быть не раньше текущего времени и не позднее чем через 30 дней.\n"
                         "Пожалуйста, введите время в формате: ДД.ММ ЧЧ:ММ",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_rental_time, photo_path)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("В главное меню"))

    bot.send_message(message.chat.id, "Укажите, пожалуйста, номер Вашего самоката", reply_markup=markup)
    bot.register_next_step_handler(message, process_scooter_number, rental_time, photo_path)

# =====================================================================================================================

# Получение Номера самоката
def process_scooter_number(message, rental_time, photo_path):
    if message.text == "В главное меню":
        back_to_menu(message)
        return

    scooter_number = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("В главное меню"))

    # Проверка, что номер состоит только из цифр
    if not scooter_number.isdigit():
        bot.send_message(message.chat.id,
                         "Введите числовой номер самоката, длиной в 4 цифры. Пожалуйста, укажите номер снова.",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_scooter_number, rental_time, photo_path)
        return

    # Проверка длины номера
    if len(scooter_number) != 4:
        bot.send_message(message.chat.id,
                         "Номер самоката должен содержать ровно 4 цифры. Пожалуйста, укажите номер снова.",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_scooter_number, rental_time, photo_path)
        return

    # Если проверки пройдены, запрашиваем номер телефона
    bot.send_message(message.chat.id, "Укажите пожалуйста Ваш номер телефона",
                     reply_markup=markup)
    bot.register_next_step_handler(message, process_phone_number, scooter_number, rental_time, photo_path)

# =====================================================================================================================

def format_phone_number(phone_number):
    phone_number = phone_number.strip()

    if phone_number.startswith('+7'):
        # Убираем + и проверяем длину
        formatted = '8' + phone_number[2:]
    elif phone_number.startswith('7'):
        # Заменяем 8 на 7
        formatted = '8' + phone_number[1:]
    elif phone_number.startswith('8'):
        # Оставляем как есть
        formatted = phone_number
    else:
        return None

    if len(formatted) == 11 and formatted.isdigit():
        return formatted
    return None

# =====================================================================================================================

# Проверка на валидность отправки данных (Номер телефона)
def is_valid_russian_phone_number(phone_number):
    phone_number = phone_number.strip()

    if phone_number.startswith('+7'):
        if len(phone_number) != 12:
            return False
    elif phone_number.startswith(('7', '8')):
        if len(phone_number) != 11:
            return False
    else:
        return False

    # Проверяем, что остальные символы - цифры
    digits = phone_number[1:] if phone_number.startswith('+') else phone_number
    if not digits.isdigit():
        return False

    return True

# =====================================================================================================================

# Получение номера телефона
def process_phone_number(message, scooter_number, rental_time, photo_path):
    if message.text == "В главное меню":
        back_to_menu(message)
        return

    phone_number = message.text.strip()

    if not is_valid_russian_phone_number(phone_number):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        button_back_to_menu = types.KeyboardButton("В главное меню")
        markup.add(button_back_to_menu)

        bot.send_message(message.chat.id, "Некорректный номер телефона. "
                         "Пожалуйста, введите номер в формате: +7XXX..., 7XXX... или 8XXX...",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_phone_number, scooter_number, rental_time, photo_path)
        return

    # Форматируем номер
    formatted_number = format_phone_number(phone_number)
    if not formatted_number:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        button_back_to_menu = types.KeyboardButton("В главное меню")
        markup.add(button_back_to_menu)

        bot.send_message(message.chat.id, "Ошибка форматирования номера. "
                         "Пожалуйста, введите номер в формате: +7XXX..., 7XXX... или 8XXX...",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_phone_number, scooter_number, rental_time, photo_path)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    markup.add(button_back_to_menu)

    bot.send_message(message.chat.id, "Укажите пожалуйста последние 4 цифры Вашей карты, которая "
                     "привязана к профилю Akku-Batt.", reply_markup=markup)
    bot.register_next_step_handler(message, process_card_number, scooter_number, formatted_number,
                                 rental_time, photo_path)

# =====================================================================================================================

# Получение номера карты (Последние 4 цифры)
def process_card_number(message, scooter_number, phone_number, rental_time, photo_path):
    if message.text == "В главное меню":
        back_to_menu(message)
        return

    card_number = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("В главное меню"))

    # Проверка, что номер состоит только из цифр
    if not card_number.isdigit():
        bot.send_message(message.chat.id,
                        "Введите числовой номер карты, последние 4 цифры. Пожалуйста, укажите номер снова.",
                        reply_markup=markup)
        bot.register_next_step_handler(message, process_card_number,
                                     scooter_number, phone_number, rental_time, photo_path)
        return

    # Проверка длины номера
    if len(card_number) != 4:
        bot.send_message(message.chat.id,
                        "Номер карты должен содержать ровно 4 цифры. Пожалуйста, укажите номер снова.",
                        reply_markup=markup)
        bot.register_next_step_handler(message, process_card_number,
                                     scooter_number, phone_number, rental_time, photo_path)
        return

    # Если проверки пройдены, запрашиваем описание проблемы
    bot.send_message(message.chat.id,
                    "Опишите пожалуйста Вашу проблему",
                    reply_markup=markup)
    bot.register_next_step_handler(message, process_description,
                                 scooter_number, phone_number, card_number,
                                 rental_time, photo_path)

# =====================================================================================================================

def process_description(message, scooter_number, phone_number, card_number, rental_time, photo_path):
    if message.text == "В главное меню":
        back_to_menu(message)
        return

    description = message.text
    user_id = message.from_user.id

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    markup.add(button_back_to_menu)

    try:
        save_report(photo_path, scooter_number, phone_number, card_number, rental_time, description, user_id)

        bot.send_message(message.chat.id, "Спасибо за Ваше обращение, мы приняли его в обработку.\n\n"
                                          "Рассмотрение заявки пройдет в течении трёх рабочих дней. "
                                          "Для уточнения информации, с вами могут связаться наши сотрудники.\n\n"
                                          "Вы можете оставить самокат и поискать новый по близости.",
                         reply_markup=markup)
    except Exception as e:
        print(f"Ошибка при сохранении отчета: {e}")
        bot.send_message(message.chat.id, "Не удалось отправить заявку, заполните снова", reply_markup=markup)


# =====================================================================================================================

def save_report(photo, scooter_number, phone_number, card_number, rental_time, description, user_id):
    conn = None
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO reports (
                photo, 
                scooter_number, 
                phone_number, 
                card_number, 
                rental_time, 
                description_of_the_problem,
                user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (photo, scooter_number, phone_number, card_number, rental_time, description, user_id))

        conn.commit()
    except Exception as e:
        raise e
    finally:
        if conn:
            conn.close()

# =====================================================================================================================
# =====================================================================================================================

# Обработка всех остальных сообщений
@bot.message_handler(func=lambda message: True)
def handle_unknown_message(message):

    if flag == False and photo_process_flag == False:
        if message.text not in ["Как арендовать самокат❓",
                                "Почему списалось 300₽❓",
                                "Проблема с самокатом❓",
                                "Как завершить поездку❓",
                                "В главное меню"]:
            bot.send_message(message.chat.id,
                             "Извините, я Вас не понял. Пожалуйста, выберите одну из предложенных кнопок.")

# =====================================================================================================================
# =====================================================================================================================

# Запуск бота
if __name__ == '__main__':
    print("Бот запущен...")
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling()
