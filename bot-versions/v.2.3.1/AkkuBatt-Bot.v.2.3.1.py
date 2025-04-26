import telebot
import sqlite3
import os
import threading
import time
import re
from datetime import datetime, timedelta
from telebot import types

# Конфигурация бота
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
DATABASE = os.environ.get('DATABASE_PATH', 'Reports.db')
PHOTOS_DIR = os.environ.get('PHOTOS_DIR', 'photos')

bot = telebot.TeleBot(API_TOKEN, threaded=True)

# Переменная флага для отслеживания формы отчёта
flag = False

# Переменная флага для проверки валидности отправки данных
photo_process_flag = False

# Создание папки /photos
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

# Инструкции
RegistrationTutorialText = ('Для использования самоката установите приложение «Akku-Batt» на свой смартфон.\n\n'
                            '1) Установите приложение, отсканировав QR-код на самокате или перейдя на сайт: https://akku-batt.rent.\n'
                            '2) Зарегистрируйтесь, введя свои данные.\n'
                            '3) Привяжите банковскую карту для оплаты.\n')

RentTutorialText = ('Для того чтобы взять самокат в аренду:\n\n'
                    '1) Найдите ближайший самокат: Это можно сделать на карте в приложении.\n'
                    '2) Выберите понравившийся самокат: Введите его номер или отсканируйте QR-код.\n'
                    '3) Выберите тариф: Определите подходящий вам тариф и нажмите "Начать аренду".\n'
                    '4) Проверьте самокат: Осмотрите его на наличие повреждений и проверьте тормоза для вашей безопасности.\n'
                    '5) Ждите активации: Подождите, пока экран самоката загорится.\n\n'
                    'Приятного вам пути!')

HowToRideTutorialText = ('Инструкция по использованию самоката:\n\n'
                         '1) Снимите самокат с подножки плавным движением вперёд.\n'
                         '2) Толкнитесь одной ногой и зажмите ручку газа, чтобы начать движение.\n'
                         '3) Для того чтобы изменить скоростные режимы, дважды нажмите кнопку на самокате и выберите подходящий вам режим:\n'
                         '- Эко\n'
                         '- Драйв\n'
                         '- Спорт\n'
                         '4) Чтобы включить фонарь, нажмите один раз кнопку на самокате.\n\n'
                         '️Не забывайте включать фары в тёмное время суток для вашей безопасности!')

# Локальная база данных для хранения отчетов
def initialize_db():
    create_base = sqlite3.connect(DATABASE)
    cursor = create_base.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo TEXT,
            rental_time TEXT,
            scooter_number TEXT,
            phone_number TEXT,
            card_number TEXT,
            description_of_the_problem TEXT,
            sent INTEGER DEFAULT 0
        )
    ''')

    create_base.commit()
    create_base.close()

initialize_db()

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

# Подготовка данных для отправки отчета
def mark_as_sent(report_id):
    try:
        with sqlite3.connect(DATABASE) as check_info:
            cursor = check_info.cursor()
            cursor.execute("UPDATE reports SET sent = 1 WHERE id = ?", (report_id,))
            check_info.commit()

    except sqlite3.Error as e:
        print(f"Ошибка при обновлении отчета: {e}")

# Отправка отчета
def send_reports():
    while True:
        reports = get_reports()
        for report in reports:
            id, photo, rent_data, scooter_number, phone_number, card_number, description_of_the_problem, _ = report

            message = (
                f"Report: #{id}\n"
                f"Дата и время начала аренды: {rent_data}\n"
                f"Номер самоката: {scooter_number}\n"
                f"Номер телефона: {phone_number}\n"
                f"Номер карты: {card_number}\n"
                f"Описание: {description_of_the_problem}"
            )

            try:
                if photo and os.path.isfile(photo):
                    with open(photo, 'rb') as photo_file:
                        bot.send_photo(CHAT_ID, photo_file, caption=message)
                    os.remove(photo)
                else:
                    bot.send_message(CHAT_ID, message)
            except Exception as e:
                print(f"Ошибка при отправке сообщения: {e}")

            mark_as_sent(id)

        time.sleep(60) # Проверка отчётов раз в 1 минуту

# Этот процесс работает во втором потоке
reporting_thread = threading.Thread(target=send_reports)
reporting_thread.start()

# Обработка кнопки "В главное меню"
@bot.message_handler(func=lambda message: message.text == "В главное меню")
def back_to_menu(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    HelpWithMoneyButton = types.KeyboardButton("Как арендовать самокат❓")
    WhereMyMoneyButton = types.KeyboardButton("Почему списалось 300 рублей❓")
    CreateReportButton = types.KeyboardButton("Сломался самокат? Нужен возврат❓")
    ProblemWithStopRent = types.KeyboardButton("Не могу завершить аренду, что делать❓")

    markup.add(HelpWithMoneyButton)
    markup.add(WhereMyMoneyButton)
    markup.add(CreateReportButton)
    markup.add(ProblemWithStopRent)

    bot.send_message(message.chat.id,
                     'Вы в главном меню чат поддержки «Akku-Batt», выберите в чем Вам нужно помочь?',
                     reply_markup=markup)

# Обработка кнопки "/start"
@bot.message_handler(commands=['start'])
def start_message(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    HelpWithMoneyButton = types.KeyboardButton("Как арендовать самокат❓")
    WhereMyMoneyButton = types.KeyboardButton("Почему списалось 300 рублей❓")
    CreateReportButton = types.KeyboardButton("Сломался самокат? Нужен возврат❓")
    ProblemWithStopRent = types.KeyboardButton("Не могу завершить аренду, что делать❓")

    markup.add(HelpWithMoneyButton)
    markup.add(WhereMyMoneyButton)
    markup.add(CreateReportButton)
    markup.add(ProblemWithStopRent)

    bot.send_message(message.chat.id,
                     'Здравствуйте, Вы написали в чат-бот поддержку «Akku-Batt». В чем Вам нужно помочь?',
                     reply_markup=markup)

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

# Обработка кнопки "Почему списалось 300 рублей?"
@bot.message_handler(func=lambda message: message.text == "Почему списалось 300 рублей❓")
def where_my_money_button(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    ReturnDidNotArrive = types.KeyboardButton("💸 Не пришёл возврат?")
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(ReturnDidNotArrive)
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id,
                     'При аренде самоката с вашей карты списывается залог в 300 рублей, который вернётся в конце поездки.\n\n'
                     'Иногда возврат занимает больше времени, но мы гарантируем, что средства будут возвращены в течение суток.',
                     reply_markup=markup)

# Обработка кнопки "Не пришёл возврат?"
@bot.message_handler(func=lambda message: message.text == "💸 Не пришёл возврат?")
def return_did_not_arrive(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id,
                     'Если возврат средств не пришёл, значит, на вашей карте было недостаточно средств для выбранного вами тарифа.\n\n'
                     'В таком случае средства для вашего катания были взяты из этого залога.',
                     reply_markup=markup)

# Обработка кнопки "Как арендовать самокат?"
@bot.message_handler(func=lambda message: message.text == "Как арендовать самокат❓")
def tutorial_how_rent_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    TutorialHowInstallAppButton = types.KeyboardButton("🛴 Как установить приложение?")
    TutorialHowStartRentButton = types.KeyboardButton("🛴 Как взять в аренду самокат?")
    TutorialHowRideButton = types.KeyboardButton("🛴 Как кататься?")
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(TutorialHowInstallAppButton)
    markup.add(TutorialHowStartRentButton)
    markup.add(TutorialHowRideButton)
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, 'Выберите, что вас интересует:', reply_markup=markup)

# Обработка кнопки "Как установить приложение?"
@bot.message_handler(func=lambda message: message.text == "🛴 Как установить приложение?")
def how_to_install_app(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    DidNotFindTheSearched = types.KeyboardButton("Не нашли что искали?")
    BackToRentTutorial = types.KeyboardButton("🔙 Назад")

    markup.add(DidNotFindTheSearched)
    markup.add(BackToRentTutorial)

    bot.send_message(message.chat.id, RegistrationTutorialText, reply_markup=markup)

# Обработка кнопки "Как взять в аренду самокат?"
@bot.message_handler(func=lambda message: message.text == "🛴 Как взять в аренду самокат?")
def how_to_rent_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    DidNotFindTheSearched = types.KeyboardButton("Не нашли что искали?")
    BackToRentMenuButton = types.KeyboardButton("🔙 Назад")
    markup.add(DidNotFindTheSearched)
    markup.add(BackToRentMenuButton)

    bot.send_message(message.chat.id, RentTutorialText, reply_markup=markup)

# Обработка кнопки "Не могу завершить аренду, что делать?"
@bot.message_handler(func=lambda message: message.text == "Не могу завершить аренду, что делать❓")
def problem_with_stop_rent(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    HowToEndRent = types.KeyboardButton("⚠️ Как завершить аренду?")
    WhereYouCanRide = types.KeyboardButton("⚠️ Где можно кататься?")
    ScooterNotGoes = types.KeyboardButton("⚠️ Самокат перестал ехать")
    BackToMainMenuButton = types.KeyboardButton("В главное меню")

    markup.add(HowToEndRent)
    markup.add(WhereYouCanRide)
    markup.add(ScooterNotGoes)
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id,
                     'Выберите, что вас интересует:',
                     reply_markup=markup)

# Обработка кнопки "Как завершить аренду?"
@bot.message_handler(func=lambda message: message.text == "⚠️ Как завершить аренду?")
def how_to_end_rent(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    iAlreadyInTheBlueZone = types.KeyboardButton("Я уже в синей зоне")
    BackToMainMenuButton = types.KeyboardButton("Назад в меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Нaзaд")

    markup.add(iAlreadyInTheBlueZone)
    markup.add(BackToMainMenuButton)
    markup.add(BackToRentMenuButton)

    bot.send_message(message.chat.id, 'Чтобы завершить аренду самоката, Вам необходимо вернуть его в зоны, '
                                      'отмеченные синим цветом на карте.\n\n'
                                      'Пока Вы находитесь вне этих зон, завершение аренды будет невозможным.',
                     reply_markup=markup)

# Обработка кнопки "Я уже в синей зоне"
@bot.message_handler(func=lambda message: message.text == "Я уже в синей зоне")
def i_already_in_the_blue_zone(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Нaзaд")

    markup.add(BackToMainMenuButton)
    markup.add(BackToRentMenuButton)

    bot.send_message(message.chat.id,
                     'Если Вы уже находитесь в синей зоне, выполните следующие шаги:\n\n'
                     '1. Зайдите в приложение.\n'
                     '2. В нижней части экрана найдите вкладку с арендованными Вами самокатами.\n'
                     '3. Нажмите на эту вкладку.\n'
                     '4. Далее, нажмите на кнопку «Завершить аренду».', reply_markup=markup)

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

    bot.send_message(message.chat.id, 'Разрешенные зоны обозначены на карте в приложении зеленым цветом.\n\n'
                                      'Если вы покидаете границы этой зоны, самокат автоматически блокируется '
                                      'до тех пор, пока вы не вернетесь в разрешенное пространство.',
                     reply_markup=markup)

# Обработка кнопки "Самокат перестал ехать"
@bot.message_handler(func=lambda message: message.text == "⚠️ Самокат перестал ехать")
def scooter_not_goes(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    BackToRentMenuButton = types.KeyboardButton("🔙 Нaзaд")

    markup.add(BackToMainMenuButton)
    markup.add(BackToRentMenuButton)

    bot.send_message(message.chat.id, 'Если Ваш самокат неожиданно перестал работать, это означает, '
                                      'что Вы выехали за пределы зоны, предназначенной для катания.\n\n'
                                      'Чтобы продолжить поездку, Вам нужно вернуть самокат в разрешенную зону.',
                     reply_markup=markup)

# Обработка кнопки "Как кататься?"
@bot.message_handler(func=lambda message: message.text == "🛴 Как кататься?")
def how_to_ride_on_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    DidNotFindTheSearched = types.KeyboardButton("Не нашли что искали?")
    BackToRentMenuButton = types.KeyboardButton("🔙 Назад")

    markup.add(DidNotFindTheSearched)
    markup.add(BackToRentMenuButton)

    bot.send_message(message.chat.id, HowToRideTutorialText, reply_markup=markup)

# Обработка кнопки "Не нашли что искали?"
@bot.message_handler(func=lambda message: message.text == "Не нашли что искали?")
def did_not_find_the_researched(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, 'Если Вы не нашли нужный вам пункт, позвоните по номеру: +7XXXXXXXXXX', # Нужно изменить номер!!!
                     reply_markup=markup)

# Обработка кнопки "Сломался самокат? Нужен возврат?", начало подготовки отчета
@bot.message_handler(func=lambda message: message.text == "Сломался самокат? Нужен возврат❓")
def report(message):
    global flag, photo_process_flag
    flag = True
    photo_process_flag = True  # Устанавливаем флаг, что пользователь начал процесс отправки фото
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    markup.add(BackToMainMenuButton)

    bot.send_message(message.chat.id, "Для оформления заявки на возврат, пожалуйста, заполните форму.\n\n"
                                      "Пришлите, пожалуйста, одно фото вашего самоката (не более одного фото).",
                     reply_markup=markup)

# Проверка на валидность отправки данных (Фото)
@bot.message_handler(func=lambda message: flag and photo_process_flag and message.content_type != 'photo')
def handle_non_photo(message):
    bot.send_message(message.chat.id, "Пожалуйста, пришлите фото самоката.")

# Сохранение фото
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    global flag, photo_process_flag
    if not flag:
        return

    try:
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

        if rental_datetime > now_time:
            return False

        elif rental_datetime < now_time - timedelta(days=30):
            return False

        return True
    except ValueError:
        return False

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

# Получение Номера самоката
def process_scooter_number(message, rental_time, photo_path):
    if message.text == "В главное меню":
        back_to_menu(message)
        return

    scooter_number = message.text

    if not scooter_number.isdigit():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("В главное меню"))

        bot.send_message(message.chat.id,
                         "Пожалуйста, введите числовой номер самоката.", reply_markup=markup)
        bot.register_next_step_handler(message, process_scooter_number, rental_time, photo_path)
        return

    if len(scooter_number) != 4:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("В главное меню"))

        bot.send_message(message.chat.id,
                         "Номер самоката должен содержать ровно 4 символа. Пожалуйста, укажите номер снова.",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_scooter_number, rental_time, photo_path)

    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("В главное меню"))
        bot.send_message(message.chat.id, "Укажите пожалуйста Ваш номер телефона",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_phone_number, scooter_number, rental_time, photo_path)

# Проверка на валидность отправки данных (Номер телефона)
def is_valid_russian_phone_number(phone_number):
    pattern = re.compile(r'^(?:\+7|8|7)?\d{10}$')
    return bool(pattern.match(phone_number))

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
                                          "Пожалуйста, введите номер в формате: +7/7 или 8.", reply_markup=markup)
        bot.register_next_step_handler(message, process_phone_number, scooter_number, rental_time, photo_path)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    markup.add(button_back_to_menu)

    bot.send_message(message.chat.id, "Укажите пожалуйста последние 4 цифры вашей карты, которая "
                                      "привязана к профилю Akku-Batt.", reply_markup=markup)
    bot.register_next_step_handler(message, process_card_number, scooter_number, phone_number,
                                   rental_time, photo_path)

# Получение номера карты (Последние 4 цифры)
def process_card_number(message, scooter_number, phone_number, rental_time, photo_path):
    if message.text == "В главное меню":
        back_to_menu(message)
        return

    card_number = message.text

    if len(card_number) != 4:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        button_back_to_menu = types.KeyboardButton("В главное меню")
        markup.add(button_back_to_menu)

        bot.send_message(message.chat.id, "Номер карты должен содержать ровно 4 символа.\n"
                                          "Пожалуйста, укажите номер снова.", reply_markup=markup)
        bot.register_next_step_handler(message, process_card_number, scooter_number, phone_number,
                                       rental_time, photo_path)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    markup.add(button_back_to_menu)

    bot.send_message(message.chat.id, "Опишите пожалуйста Вашу проблему", reply_markup=markup)
    bot.register_next_step_handler(message, process_description, scooter_number, phone_number,
                                   card_number, rental_time, photo_path)

# Получение описания проблемы
def process_description(message, scooter_number, phone_number, card_number, rental_time, photo_path):
    if message.text == "В главное меню":
        back_to_menu(message)
        return

    description = message.text

    save_report(photo_path, scooter_number, phone_number, card_number, rental_time, description)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    markup.add(button_back_to_menu)

    bot.send_message(message.chat.id, "Спасибо за Ваше обращение, мы приняли его в обработку.\n\n"
                                      "Вы можете оставить самокат и поискать новый по близости.", reply_markup=markup)

# Сохранение репорта в базу данных
def save_report(photo, scooter_number, phone_number, card_number, rental_time, description):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO reports (photo, scooter_number, phone_number, card_number, rental_time, description_of_the_problem)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (photo, scooter_number, phone_number, card_number, rental_time, description))

    conn.commit()
    conn.close()

# Запуск бота
bot.infinity_polling()
