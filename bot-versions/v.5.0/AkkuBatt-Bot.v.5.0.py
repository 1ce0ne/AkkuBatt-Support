# ===============================================
# =============== БИБЛИОТЕКИ БОТА ===============
# ===============================================

import telebot
import os
import threading
import time
import re
import pytz
from datetime import datetime, timedelta
from telebot import types
from flask import Flask, Response
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient
from bson.objectid import ObjectId

# =================================================
# =============== КОНФИГУРАЦИЯ БОТА ===============
# =================================================

API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = os.environ.get('DATABASE_NAME', 'AkkuBattBotSup')
PHOTOS_DIR = os.environ.get('PHOTOS_DIR', 'photos')

client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]
reports_collection = db['reports']

bot = telebot.TeleBot(API_TOKEN, threaded=True)

# ==============================================
# =============== ЗАПУСК СЕРВЕРА ===============
# ==============================================

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return Response("OK", status=200)

def run_flask():
    app.run(host='0.0.0.0', port=5000)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# ==================================================
# =============== ПЕРЕМЕННЫЕ И ФЛАГИ ===============
# ==================================================

# Переменные флагов
flag = False
photo_process_flag = False
last_media_group_id = None
processed_media_groups = {}
reject_reason_data = {}
question_data = {}

# Создание папки /photos
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

# ====================================================
# =============== ОЧИСТКА ПАПКИ PHOTOS ===============
# ====================================================

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


# Ежедневная очистка в 00:00 по МСК
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Moscow'))
scheduler.add_job(clean_photos_dir, 'cron', hour=0, minute=0)
scheduler.start()

# ====================================================================
# =============== Создание и использование базы данных ===============
# ====================================================================

def init_mongodb():
    try:
        # Создаем коллекцию с валидацией схемы (если не существует)
        db.create_collection("reports", validator={
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["user_id", "created_at"],
                "properties": {
                    "id": {"bsonType": "int"},
                    "user_id": {"bsonType": ["int", "long"]},  # Разрешаем оба типа
                    "photo": {"bsonType": "string"},
                    "rental_time": {"bsonType": "string"},
                    "scooter_number": {"bsonType": "string"},
                    "phone_number": {"bsonType": "string"},
                    "card_number": {"bsonType": "string"},
                    "description_of_the_problem": {"bsonType": "string"},
                    "sent": {"bsonType": "int", "minimum": 0, "maximum": 1},
                    "returned": {"bsonType": "int", "minimum": 0, "maximum": 2},
                    "refund_amount": {"bsonType": "double"},
                    "created_at": {"bsonType": "date"}
                }
            }
        })

        # Создаем индекс для автоинкремента id
        db.reports.create_index("id", unique=True)

        # Создаем последовательность для автоинкремента
        if "counters" not in db.list_collection_names():
            db.counters.insert_one({
                "_id": "reportid",
                "seq": 0
            })

    except Exception as e:
        # Коллекция уже существует
        print(f"MongoDB collection already exists: {e}")

# Функция для получения следующего ID
def get_next_sequence_value(sequence_name):
    counter = db.counters.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"seq": 1}},
        return_document=True
    )
    return counter["seq"]

init_mongodb()

# ======================================
# =============== ТЕКСТА ===============
# ======================================

# Тутор по установке
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

# Туториал по установке
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

# Туториал по использованию самоката
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

# Объяснение куда списывается 300 рублей
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

# Туториал как остановить аренду
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

# Туториал что делать если нет кнопки завершить
FinishRentManualText = (
    'Если кнопка "Завершить" не отображается на главном экране:\n\n'

    '1. Нажмите на иконку самоката 🛴 (третья сверху справа в приложении, с красной пометкой)\n'
    '2. Выберите самокат, аренду которого хотите завершить\n'
    '3. Появится кнопка "Завершить" - нажмите ее\n\n'

    'Важно:\n'
    '— После нажатия не забудьте подтвердить завершение аренды\n\n'
)

# Что делать если самокат не работает
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

# Где я могу кататься
WhereICanRide = (
    'Кататься можно только в разрешенных зонах:\n\n'

    '1) Разрешенные зоны:\n'
    '   - Обозначены зеленым цветом на карте 🗺️\n'
    '   - Кататься можно только в этих зонах\n\n'

    '2) При выезде за границы:\n'
    '   - Самокат автоматически блокируется\n'
    '   - Для разблокировки вернитесь в зеленую зону\n\n'
)

# Возврат не пришёл
ReturnDidNotArrivee = (
    'Если возврат средств не пришёл, значит, '
    'на вашей карте было недостаточно средств для выбранного тарифа 💳\n\n'
    'В таком случае средства были взяты из залога.'
)

# Управление самокатом
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

# ============================================
# =============== Парсинг базы ===============
# ============================================

# Парсинг базы на неотправленные отчёты
def get_reports():
    try:
        reports = list(db.reports.find({"sent": 0}).sort("created_at", 1))
        return reports
    except Exception as e:
        print(f"Ошибка при получении отчетов: {e}")
        return []


# =================================================
# =============== Получение отчетов ===============
# =================================================

# Подготовка данных для отправки отчёта
def mark_as_sent(report_id):
    try:
        db.reports.update_one(
            {"id": report_id},
            {"$set": {"sent": 1}}
        )
    except Exception as e:
        print(f"Ошибка при обновлении отчета: {e}")

# =======================================================
# =============== Кол-во отчетов с номера ===============
# =======================================================

def get_report_count_by_phone(phone_number):
    try:
        return db.reports.count_documents({"phone_number": phone_number})
    except Exception as e:
        print(f"Ошибка при получении количества отчетов: {e}")
        return 1

# ===============================================
# =============== Отправка отчёта ===============
# ===============================================

def send_reports():
    while True:
        reports = get_reports()
        for report in reports:
            try:
                report_id = report["id"]
                user_id = report["user_id"]
                photo = report.get("photo", "")
                rent_data = report.get("rental_time", "")
                scooter_number = report.get("scooter_number", "")
                phone_number = report.get("phone_number", "")
                card_number = report.get("card_number", "")
                description_of_the_problem = report.get("description_of_the_problem", "")

                report_count = get_report_count_by_phone(phone_number)

                message = (
                    f"📝 Report: #{report_id}\n"
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

                # Создаем интерактивные кнопки
                markup = types.InlineKeyboardMarkup(row_width=2)
                approve_button = types.InlineKeyboardButton(
                    "Подтвердить возврат",
                    callback_data=f'return_approve_{report_id}_{user_id}'
                )
                reject_button = types.InlineKeyboardButton(
                    "Отклонить заявку",
                    callback_data=f'return_reject_{report_id}_{user_id}'
                )
                # question_button = types.InlineKeyboardButton(
                #     "Уточняющий вопрос",
                #     callback_data=f'return_question_{report_id}_{user_id}'
                # )
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
                                mark_as_sent(report_id)
                    except Exception as e:
                        print(f"Ошибка при отправке фото: {e}")
                        bot.send_message(
                            CHAT_ID,
                            message + f"\n[Фото не удалось загрузить: {photo}]",
                            reply_markup=markup
                        )
                        mark_as_sent(report_id)
                else:
                    bot.send_message(
                        CHAT_ID,
                        message,
                        reply_markup=markup
                    )
                    mark_as_sent(report_id)

            except Exception as e:
                print(f"Ошибка при обработке отчета: {e}")
                continue

        time.sleep(60)


# ===================================================
# =============== Вердикт по возврату ===============
# ===================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('return_'))
def handle_return_decision(call):
    try:
        action, report_id, user_id = call.data.split('_')[1:]
        user_id = int(user_id)

        if action == 'approve':
            # Сохраняем данные для запроса суммы возврата
            reject_reason_data[call.from_user.id] = {
                'report_id': report_id,
                'user_id': user_id,
                'message_id': call.message.message_id,
                'chat_id': call.message.chat.id,
                'current_text': call.message.caption if call.message.caption else call.message.text,
                'step': 'waiting_for_refund_amount'
            }

            # Запрашиваем сумму возврата
            msg = bot.send_message(
                call.message.chat.id,
                "Укажите сумму возврата:",
                reply_to_message_id=call.message.message_id
            )

            bot.answer_callback_query(call.id, "Укажите сумму возврата")

        elif action == 'reject':
            # Сохраняем данные для запроса причины
            reject_reason_data[call.from_user.id] = {
                'report_id': report_id,
                'user_id': user_id,
                'message_id': call.message.message_id,
                'chat_id': call.message.chat.id,
                'current_text': call.message.caption if call.message.caption else call.message.text,
                'step': 'waiting_for_reject_reason'
            }

            # Запрашиваем причину отклонения
            msg = bot.send_message(
                call.message.chat.id,
                "Укажите причину отклонения заявки ответом на это сообщение:",
                reply_to_message_id=call.message.message_id
            )

            bot.answer_callback_query(call.id, "Укажите причину отклонения")


        # elif action == 'question':
        #
        #     # Сохраняем данные для запроса вопроса
        #     reject_reason_data[call.from_user.id] = {
        #         'report_id': report_id,
        #         'user_id': user_id,
        #         'message_id': call.message.message_id,
        #         'chat_id': call.message.chat.id,
        #         'current_text': call.message.caption if call.message.caption else call.message.text,
        #         'step': 'waiting_for_question'
        #     }
        #
        #     msg = bot.send_message(
        #         call.message.chat.id,
        #         "Введите уточняющий вопрос для пользователя (он сможет ответить на ваше сообщение):",
        #         reply_to_message_id=call.message.message_id
        #     )
        #
        #     bot.answer_callback_query(call.id, "Введите вопрос для пользователя")

    except Exception as e:
        print(f"Ошибка при обработке callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")


# Этот процесс работает во втором потоке
reporting_thread = threading.Thread(target=send_reports)
reporting_thread.start()


# ===============================================
# =============== Ответ от админа ===============
# ===============================================

@bot.message_handler(
    func=lambda message: message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id)
def handle_replied_message(message):
    try:
        user_id = message.from_user.id
        if user_id not in reject_reason_data:
            return

        data = reject_reason_data[user_id]

        if data.get('step') == 'waiting_for_refund_amount':
            # Обработка суммы возврата
            try:
                refund_amount = float(message.text.replace(',', '.'))

                if refund_amount <= 0:
                    raise ValueError

                # Сохраняем сумму и переходим к запросу комментария
                reject_reason_data[user_id]['refund_amount'] = refund_amount
                reject_reason_data[user_id]['step'] = 'waiting_for_comment'

                msg = bot.send_message(
                    message.chat.id,
                    "Добавьте комментарий (если нет, то напишите \"-\"):",
                    reply_to_message_id=data['message_id']
                )

                # Удаляем предыдущие сообщения
                try:
                    bot.delete_message(message.chat.id, message.message_id)  # Сообщение администратора
                    bot.delete_message(message.chat.id, message.reply_to_message.message_id)  # Сообщение бота
                except Exception as e:
                    print(f"Ошибка при удалении сообщений: {e}")

            except ValueError:
                msg = bot.send_message(
                    message.chat.id,
                    "Пожалуйста, укажите корректную сумму возврата (например: 100 или 50.50):",
                    reply_to_message_id=data['message_id']
                )

        elif data.get('step') == 'waiting_for_comment':
            # Обработка комментария
            comment = message.text if message.text != "-" else None
            refund_amount = reject_reason_data[user_id]['refund_amount']

            # Обновляем статус в БД
            update_return_status(data['report_id'], 1, data['user_id'], refund_amount)

            # Формируем новый текст
            status_text = f"\n\n✅ Заявка одобрена\nСумма возврата: {refund_amount}₽"
            if comment:
                status_text += f"\nКомментарий: {comment}"
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
            user_message = f"Заявка на возврат одобрена. Сумма: {refund_amount}₽"
            if comment:
                user_message += f"\nКомментарий: {comment}"
            bot.send_message(data['user_id'], user_message)

            # Удаляем временные данные
            if user_id in reject_reason_data:
                del reject_reason_data[user_id]

            # Удаляем сообщения бота и администратора
            try:
                bot.delete_message(message.chat.id, message.message_id)  # Сообщение администратора
                bot.delete_message(message.chat.id, message.reply_to_message.message_id)  # Сообщение бота
                # Удаляем предыдущие сообщения бота (запрос суммы и комментария)
                for msg_id in range(message.reply_to_message.message_id - 1, message.reply_to_message.message_id - 3, -1):
                    bot.delete_message(message.chat.id, msg_id)
            except Exception as e:
                print(f"Ошибка при удалении сообщений: {e}")

        elif data.get('step') == 'waiting_for_reject_reason':
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

            # Удаляем сообщения бота и администратора
            try:
                bot.delete_message(message.chat.id, message.message_id)  # Сообщение администратора
                bot.delete_message(message.chat.id, message.reply_to_message.message_id)  # Сообщение бота
            except Exception as e:
                print(f"Ошибка при удалении сообщений: {e}")

    except Exception as e:
        print(f"Ошибка при обработке ответа: {e}")
        bot.send_message(
            message.chat.id,
            "Произошла ошибка при обработке. Попробуйте еще раз."
        )

# # ===============================================
# # =============== Ответ от админа ===============
# # ===============================================

# def process_reject_reason(message):
#     try:
#         user_id = message.from_user.id
#         if user_id not in reject_reason_data:
#             return
#
#         # Проверяем, что это ответ на сообщение бота
#         if not message.reply_to_message or message.reply_to_message.from_user.id != bot.get_me().id:
#             # Удаляем сообщение пользователя, если это не ответ
#             try:
#                 bot.delete_message(message.chat.id, message.message_id)
#             except:
#                 pass
#
#             # Повторно запрашиваем причину
#             msg = bot.send_message(
#                 message.chat.id,
#                 "Пожалуйста, укажите причину отклонения, используя кнопку 'Ответить' на моё сообщение.",
#                 reply_to_message_id=reject_reason_data[user_id]['message_id']
#             )
#             bot.register_next_step_handler(msg, process_reject_reason)
#             return
#
#         data = reject_reason_data[user_id]
#         reason = message.text
#
#         # Обновляем статус в БД
#         update_return_status(data['report_id'], 2, data['user_id'])
#
#         # Формируем новый текст
#         status_text = f"\n\n❌ Заявка отклонена\nПричина: {reason}"
#         new_text = (data['current_text'] or "") + status_text
#
#         # Обновляем оригинальное сообщение
#         try:
#             bot.edit_message_text(
#                 chat_id=data['chat_id'],
#                 message_id=data['message_id'],
#                 text=new_text,
#                 reply_markup=None
#             )
#         except:
#             try:
#                 bot.edit_message_caption(
#                     chat_id=data['chat_id'],
#                     message_id=data['message_id'],
#                     caption=new_text,
#                     reply_markup=None
#                 )
#             except Exception as e:
#                 print(f"Ошибка при обновлении сообщения: {e}")
#
#         # Отправляем уведомление пользователю
#         bot.send_message(
#             data['user_id'],
#             f"Ваша заявка на возврат была отклонена.\nПричина: {reason}"
#         )
#
#         # Удаляем временные данные
#         if user_id in reject_reason_data:
#             del reject_reason_data[user_id]
#
#     except Exception as e:
#         print(f"Ошибка при обработке причины отклонения: {e}")
#         bot.send_message(
#             message.chat.id,
#             "Произошла ошибка при обработке причины. Попробуйте еще раз."
#         )


# ===============================================
# =============== Ответ от пользователя ===============
# ===============================================

# @bot.message_handler(
#     func=lambda message:
#     message.reply_to_message and
#     message.from_user.id in question_data and
#     message.reply_to_message.message_id == question_data[message.from_user.id]["question_message_id"]
# )
# def handle_user_answer(message):
#     try:
#         user_id = message.from_user.id
#         data = question_data.get(user_id)
#
#         if not data:
#             bot.reply_to(message, "❌ Сессия устарела. Начните заново.")
#             return
#
#         # Логируем данные для отладки
#         print(f"Данные вопроса: {data}")
#         print(f"ID сообщения с вопросом: {data['question_message_id']}")
#         print(f"ID ответного сообщения: {message.reply_to_message.message_id}")
#
#         # Отправляем ответ администратору
#         bot.send_message(
#             data['admin_chat_id'],
#             f"📩 Ответ от пользователя на вопрос:\n\"{data['question']}\"\n\n💬 Ответ: {message.text}\n\nВыберите действие:",
#             reply_to_message_id=data['admin_message_id'],
#             reply_markup=create_decision_keyboard(data['report_id'], user_id)
#         )
#
#         # Удаляем данные вопроса
#         if user_id in question_data:
#             del question_data[user_id]
#
#     except Exception as e:
#         print(f"Ошибка в handle_user_answer: {e}")
#         bot.reply_to(message, "⚠ Произошла ошибка. Попробуйте ещё раз.")
#
#
# def create_decision_keyboard(report_id, user_id):
#     markup = types.InlineKeyboardMarkup(row_width=2)
#     approve_button = types.InlineKeyboardButton(
#         "Подтвердить возврат",
#         callback_data=f'return_approve_{report_id}_{user_id}'
#     )
#     reject_button = types.InlineKeyboardButton(
#         "Отклонить заявку",
#         callback_data=f'return_reject_{report_id}_{user_id}'
#     )
#     markup.add(approve_button, reject_button)
#     return markup

# ==================================================
# =============== Обновление статуса ===============
# ==================================================

def update_return_status(report_id, status, user_id, refund_amount=None):
    try:
        update_data = {"$set": {"returned": status}}
        if refund_amount is not None:
            update_data["$set"]["refund_amount"] = refund_amount

        db.reports.update_one(
            {"id": report_id},
            update_data
        )
    except Exception as e:
        print(f"Ошибка при обновлении статуса возврата: {e}")

# ============================================
# =============== Главное меню ===============
# ============================================

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

    markup.add(WhereMyMoneyButton, CreateReportButton)
    markup.add(HelpWithMoneyButton, ProblemWithStopRent)

    bot.send_message(message.chat.id,
                     'Вы в главном меню чат поддержки «Akku-Batt», выберите в чем Вам нужно помочь?',
                     reply_markup=markup)


# ==============================================
# =============== Стартовое меню ===============
# ==============================================

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

    markup.add(WhereMyMoneyButton, CreateReportButton)
    markup.add(HelpWithMoneyButton, ProblemWithStopRent)

    bot.send_message(message.chat.id,
                     'Здравствуйте, Вы написали в чат-бот поддержку «Akku-Batt». В чем Вам нужно помочь?',
                     reply_markup=markup)


# ============================================
# =============== Кнопки назад ===============
# ============================================

# Обработка кнопки "Назад", которая отправляет в туториал по аренде
@bot.message_handler(func=lambda message: message.text == "🔙 Назад")
def back_to_rent_tutorial(message):
    global flag
    flag = False

    tutorial_how_rent_scooter(message)

# Обработка кнопки "Назад", которая отправляет в туториал как остановить аренду
@bot.message_handler(func=lambda message: message.text == "🔙 Нaзaд")
def back_to_stop_rent_tutorial(message):
    global flag
    flag = False

    problem_with_stop_rent(message)

# Обработка кнопки "Назад", которая отправляет в туториал как установить приложение
@bot.message_handler(func=lambda message: message.text == "🔙 Нaзад")
def go_back_install_app(message):
    global flag
    flag = False

    how_to_install_app(message)

# Обработка кнопки "Назад", которая отправляет в туториал как установить приложение
@bot.message_handler(func=lambda message: message.text == "🔙 Haзaд")
def go_back_install_to_problem(message):
    global flag
    flag = False

    problem_with_scooter(message)

# =====================================================
# =============== Почему списалось 300р ===============
# =====================================================

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

# ==================================================
# =============== Не пришёл возврат? ===============
# ==================================================

@bot.message_handler(func=lambda message: message.text == "💸 Не пришёл возврат?")
def return_did_not_arrive(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, ReturnDidNotArrivee, reply_markup=markup)

# ======================================================
# =============== Как арендовать самокат ===============
# ======================================================

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

# ==========================================================
# =============== Как установить приложение? ===============
# ==========================================================

@bot.message_handler(func=lambda message: message.text == "🛴 Как установить приложение?")
def how_to_install_app(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentTutorial = types.KeyboardButton("🔙 Назад")
    markup.add(BackToRentTutorial, BackToMainMenuButton)

    bot.send_message(message.chat.id, RegistrationTutorialText, reply_markup=markup)

# ======================================================
# =============== Как арендовать самокат ===============
# ======================================================

@bot.message_handler(func=lambda message: message.text == "🛴 Как арендовать самокат?")
def how_to_rent_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Назад")
    markup.add(BackToRentMenuButton, BackToMainMenuButton)

    bot.send_message(message.chat.id, RentTutorialText, reply_markup=markup)

# =============================================
# =============== Как кататься? ===============
# =============================================

@bot.message_handler(func=lambda message: message.text == "🛴 Как кататься?")
def how_to_ride_on_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Назад")

    markup.add(BackToRentMenuButton, BackToMainMenuButton)

    bot.send_message(message.chat.id, HowToRideTutorialText, reply_markup=markup)

# ================================================
# =============== Разрешенные зоны ===============
# ================================================

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
        message.chat.id, WhereICanRide, reply_markup=markup)

# =====================================================
# =============== Как завершить поездку ===============
# =====================================================

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

# ====================================================
# =============== Нет кнопки завершить ===============
# ====================================================

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

# ====================================================
# =============== Как завершить аренду ===============
# ====================================================

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


# ==================================================
# =============== Где можно кататься ===============
# ==================================================

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

# ===================================================
# =============== Не нашли что искали ===============
# ===================================================

@bot.message_handler(func=lambda message: message.text == "Не нашли что искали❓")
def did_not_find_the_researched(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, 'Если Вы не нашли нужный вам пункт, позвоните по номеру: +7(926)013-43-85',
                     reply_markup=markup)

# ==================================================
# =============== Где можнo кататься ===============
# ==================================================

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

# ======================================================
# =============== Самoкат перестал ехать ===============
# ======================================================

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

# =====================================================
# =============== Cамокат едет медленно ===============
# =====================================================

@bot.message_handler(func=lambda message: message.text == "🛴 Cамокат едет медленно?")
def why_scooter_so_slowly(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Haзaд")

    markup.add(BackToRentMenuButton, BackToMainMenuButton)

    bot.send_message(message.chat.id, ScooterControlsText, reply_markup=markup)

# ====================================================
# =============== Проблема с самокатом ===============
# ====================================================

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

# =============================================
# =============== Нужен возврат ===============
# =============================================

@bot.message_handler(func=lambda message: message.text == "Нужен возврат❓")
def report(message):
    global flag, photo_process_flag
    flag = True
    photo_process_flag = True

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id,
                     "Для оформления заявки на возврат средств потребуется предоставить дополнительные данные. \n\n"
                     "Пожалуйста, прикрепите одну фотографию вашего самоката.",
                     reply_markup=markup)


# =======================================================
# =============== Валидация данных (Фото) ===============
# =======================================================

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

# =======================================================
# =============== Валидация данных (Дата) ===============
# =======================================================

def validate_correct_rental_time(rental_time):
    try:
        datetime.strptime(rental_time, "%d.%m %H:%M")
        return True
    except ValueError:
        return False

# =======================================================
# =============== Валидация данных (Дата) ===============
# =======================================================

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

# ========================================================
# =============== Получение даты и времени ===============
# ========================================================

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

# =========================================================
# =============== Получение номера самоката ===============
# =========================================================

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


# ==========================================================
# =============== Валидация данных (Телефон) ===============
# ==========================================================

def format_phone_number(phone_number):
    phone_number = phone_number.strip()

    digits = ''.join(c for c in phone_number if c.isdigit())

    if len(digits) == 11:
        if digits.startswith('7'):
            return '+' + digits
        elif digits.startswith('8'):
            return '+7' + digits[1:]
    elif len(digits) == 10:
        return '+7' + digits

    return None

# ==========================================================
# =============== Валидация данных (Телефон) ===============
# ==========================================================

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


# =========================================================
# =============== Получение номера телефона ===============
# =========================================================

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


# ======================================================
# =============== Получение номера карты ===============
# ======================================================

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


# ===========================================================
# =============== Получение описания проблемы ===============
# ===========================================================

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
                                          "Вы можете оставить самокат и поискать новый поблизости.",
                         reply_markup=markup)
    except Exception as e:
        print(f"Ошибка при сохранении отчета: {e}")
        bot.send_message(message.chat.id, "Не удалось отправить заявку, заполните снова", reply_markup=markup)


# ========================================================
# =============== Сохранение в базу данных ===============
# ========================================================

def save_report(photo, scooter_number, phone_number, card_number, rental_time, description, user_id):
    try:
        report_id = get_next_sequence_value("reportid")

        db.reports.insert_one({
            "id": report_id,
            "user_id": int(user_id),
            "photo": photo,
            "rental_time": rental_time,
            "scooter_number": scooter_number,
            "phone_number": phone_number,
            "card_number": card_number,
            "description_of_the_problem": description,
            "sent": 0,
            "returned": 0,
            "created_at": datetime.now()
        })
    except Exception as e:
        raise e


# ===========================================================
# =============== Обработка текста вне заявки ===============
# ===========================================================

@bot.message_handler(func=lambda message: True)
def handle_unknown_message(message):
    # Игнорируем сообщения не в ответ в чате с отчетами
    if message.chat.id == int(CHAT_ID) and not message.reply_to_message:
        return

    if flag == False and photo_process_flag == False:
        if message.text not in ["Как арендовать самокат❓",
                                "Почему списалось 300₽❓",
                                "Проблема с самокатом❓",
                                "Как завершить поездку❓",
                                "В главное меню"]:
            bot.send_message(message.chat.id,
                             "Извините, я Вас не понял. Пожалуйста, выберите одну из предложенных кнопок.")


# ===========================================
# =============== Запуск бота ===============
# ===========================================

if __name__ == '__main__':
    print("Бот запущен...")
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling()
