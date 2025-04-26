import telebot
from telebot import types
import sqlite3
import os
import threading
import time
import re

flag = False

API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
DATABASE = os.environ.get('DATABASE_PATH', 'Reports.db')
PHOTOS_DIR = os.environ.get('PHOTOS_DIR', 'photos')

bot = telebot.TeleBot(API_TOKEN, threaded=True)

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

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

conn.commit()
conn.close()

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


def is_valid_russian_phone_number(phone_number):
    pattern = re.compile(r'^(?:\+7|8|7)?\d{10}$')
    return bool(pattern.match(phone_number))


def initialize_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()


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


@bot.message_handler(func=lambda message: message.text == "🔙 Назад")
def back_to_menu_rent(message):
    global flag
    flag = False

    help_button_handler(message)


@bot.message_handler(func=lambda message: message.text == "🔙 Нaзaд")
def back_to_menu_rent2(message):
    global flag
    flag = False

    problem_of_rent(message)


def ensure_photos_directory():
    if not os.path.exists(PHOTOS_DIR):
        os.makedirs(PHOTOS_DIR)


def get_reports():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM reports WHERE sent = 0")
        reports = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Ошибка при получении отчетов: {e}")
        reports = []
    finally:
        conn.close()

    return reports


def mark_as_sent(report_id):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("UPDATE reports SET sent = 1 WHERE id = ?", (report_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при обновлении отчета: {e}")
    finally:
        conn.close()


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
                else:
                    bot.send_message(CHAT_ID, message)
            except Exception as e:
                print(f"Ошибка при отправке сообщения: {e}")

            mark_as_sent(id)

        time.sleep(60)


reporting_thread = threading.Thread(target=send_reports)
reporting_thread.start()


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

# Меню по кнопке "Как арендовать самокат"
@bot.message_handler(func=lambda message: message.text == "Как арендовать самокат❓")
def help_button_handler(message):
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


@bot.message_handler(func=lambda message: message.text == "🛴 Как установить приложение?")
def how_to_install_app(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    ne_nashli_chto_iskali = types.KeyboardButton("Не нашли что искали?")
    button_back_to_menu_rent = types.KeyboardButton("🔙 Назад")

    markup.add(ne_nashli_chto_iskali)
    markup.add(button_back_to_menu_rent)

    bot.send_message(message.chat.id, RegistrationTutorialText, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🔙 Нaзад")
def go_back_install_app(message):
    global flag
    flag = False

    how_to_install_app(message)

@bot.message_handler(func=lambda message: message.text == "Туториал по установке")
def tutor_how_install(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    button_back_to_menu_install = types.KeyboardButton("🔙 Нaзад")

    markup.add(BackToMainMenuButton)
    markup.add(button_back_to_menu_install)

    bot.send_message(message.chat.id, "Тут будет про туториал установки", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Туториал по регистрации")
def tutor_how_register(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    button_back_to_menu_install = types.KeyboardButton("🔙 Нaзад")

    markup.add(BackToMainMenuButton)
    markup.add(button_back_to_menu_install)

    bot.send_message(message.chat.id, "Тут будет про туториал регистрации", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Туториал по привязке карты")
def tutor_how_con_card(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    BackToMainMenuButton = types.KeyboardButton("В главное меню")
    button_back_to_menu_install = types.KeyboardButton("🔙 Нaзад")

    markup.add(BackToMainMenuButton)
    markup.add(button_back_to_menu_install)

    bot.send_message(message.chat.id, "Тут будет про туториал подключения карты", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🛴 Как взять в аренду самокат?")
def how_to_rent_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    ne_nashli_chto_iskali = types.KeyboardButton("Не нашли что искали?")
    button_back_to_menu_rent = types.KeyboardButton("🔙 Назад")
    markup.add(ne_nashli_chto_iskali)
    markup.add(button_back_to_menu_rent)

    bot.send_message(message.chat.id, RentTutorialText, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Не могу завершить аренду, что делать❓")
def problem_of_rent(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kak_zavershyt_arendu = types.KeyboardButton("⚠️ Как завершить аренду?")
    gde_mozhno_katatsa = types.KeyboardButton("⚠️ Где можно кататься?")
    samokat_ne_edet = types.KeyboardButton("⚠️ Самокат перестал ехать")
    button_back_to_menu = types.KeyboardButton("В главное меню")

    markup.add(kak_zavershyt_arendu)
    markup.add(gde_mozhno_katatsa)
    markup.add(samokat_ne_edet)
    markup.add(button_back_to_menu)

    bot.send_message(message.chat.id,
                     'Выберите, что вас интересует:',
                     reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "⚠️ Как завершить аренду?")
def kak_zavershyt_rent(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_in_blue_zone = types.KeyboardButton("Я уже в синей зоне")
    button_back_to_menu = types.KeyboardButton("Назад в меню")
    button_back_to_menu_rent = types.KeyboardButton("🔙 Нaзaд")

    markup.add(button_in_blue_zone)
    markup.add(button_back_to_menu)
    markup.add(button_back_to_menu_rent)

    bot.send_message(message.chat.id, 'Чтобы завершить аренду самоката, Вам необходимо вернуть его в зоны, '
                                      'отмеченные синим цветом на карте.\n\n'
                                      'Пока Вы находитесь вне этих зон, завершение аренды будет невозможным.',
                                      reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Я уже в синей зоне")
def i_in_blue_zone(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    button_back_to_menu_rent = types.KeyboardButton("🔙 Нaзaд")

    markup.add(button_back_to_menu)
    markup.add(button_back_to_menu_rent)

    bot.send_message(message.chat.id,
                     'Если Вы уже находитесь в синей зоне, выполните следующие шаги:\n\n'
                     '1. Зайдите в приложение.\n'
                     '2. В нижней части экрана найдите вкладку с арендованными Вами самокатами.\n'
                     '3. Нажмите на эту вкладку.\n'
                     '4. Далее, нажмите на кнопку «Завершить аренду».',reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "⚠️ Где можно кататься?")
def gde_mozhno_ezdit(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    button_back_to_menu_rent = types.KeyboardButton("🔙 Нaзaд")

    markup.add(button_back_to_menu)
    markup.add(button_back_to_menu_rent)

    bot.send_message(message.chat.id, 'Разрешенные зоны обозначены на карте в приложении зеленым цветом.\n\n'
                                      'Если вы покидаете границы этой зоны, самокат автоматически блокируется '
                                      'до тех пор, пока вы не вернетесь в разрешенное пространство.',
                                      reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "⚠️ Самокат перестал ехать")
def samokat_ne_edet(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    button_back_to_menu_rent = types.KeyboardButton("🔙 Нaзaд")

    markup.add(button_back_to_menu)
    markup.add(button_back_to_menu_rent)

    bot.send_message(message.chat.id, 'Если Ваш самокат неожиданно перестал работать, это означает, '
                                      'что Вы выехали за пределы зоны, предназначенной для катания.\n\n'
                                      'Чтобы продолжить поездку, Вам нужно вернуть самокат в разрешенную зону.',
                                      reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "🛴 Как кататься?")
def how_to_ride_on_scooter(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    ne_nashli_chto_iskali = types.KeyboardButton("Не нашли что искали?")
    button_back_to_menu_rent = types.KeyboardButton("🔙 Назад")

    markup.add(ne_nashli_chto_iskali)
    markup.add(button_back_to_menu_rent)

    bot.send_message(message.chat.id, HowToRideTutorialText, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Не нашли что искали?")
def ne_nashli_chto_iskalii(message):
    global flag
    flag = False

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    markup.add(button_back_to_menu)

    bot.send_message(message.chat.id, 'Если Вы не нашли нужный вам пункт, позвоните по номеру: +7XXXXXXXXXX',
                                      reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Сломался самокат? Нужен возврат❓")
def report(message):
    global flag
    flag = True
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    markup.add(button_back_to_menu)

    bot.send_message(message.chat.id, "Для оформления заявки на возврат, пожалуйста, заполните форму.\n\n"
                                      "Пришлите, пожалуйста, одно фото вашего самоката (не более одного фото).",
                                      reply_markup=markup)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    global flag
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
        bot.send_message(message.chat.id, "Укажите пожалуйста время начала аренды (ДД.ММ, ЧАС.МИНУТА)",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_rental_time, photo_path)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при обработке фото: {str(e)}")


def process_rental_time(message, photo_path):
    if message.text == "В главное меню":
        back_to_menu(message)
        return

    rental_time = message.text.strip()

    # Проверка на правильность формата времени
    if not validate_rental_time(rental_time):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("В главное меню"))
        bot.send_message(message.chat.id,
                         "Некорректный формат времени. Пожалуйста, введите время в формате: ДД.ММ, ЧАС.МИНУТА",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_rental_time, photo_path)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("В главное меню"))
    bot.send_message(message.chat.id, "Укажите пожалуйста номер Вашего самоката",
                     reply_markup=markup)
    bot.register_next_step_handler(message, process_scooter_number, rental_time, photo_path)


def process_scooter_number(message, rental_time, photo_path):
    if message.text == "В главное меню":
        back_to_menu(message)
        return

    scooter_number = message.text

    if not scooter_number.isdigit():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("В главное меню"))
        bot.send_message(message.chat.id,
                         "Пожалуйста, введите числовой номер самоката.",
                         reply_markup=markup)
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
                                           "Пожалуйста, введите номер в формате: +7/7 или 8.",
                         reply_markup=markup)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    markup.add(button_back_to_menu)

    bot.send_message(message.chat.id, "Укажите, пожалуйста, последние 4 цифры вашей карты, которая "
                                       "привязана к профилю Akku-Batt.",
                     reply_markup=markup)
    bot.register_next_step_handler(message, process_card_number, scooter_number, phone_number,
                                   rental_time, photo_path)


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
                                           "Пожалуйста, укажите номер снова.",
                         reply_markup=markup)
        bot.register_next_step_handler(message, process_card_number, scooter_number, phone_number,
                                       rental_time, photo_path)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_back_to_menu = types.KeyboardButton("В главное меню")
    markup.add(button_back_to_menu)

    bot.send_message(message.chat.id, "Опишите пожалуйста Вашу проблему",
                     reply_markup=markup)
    bot.register_next_step_handler(message, process_description, scooter_number, phone_number,
                                   card_number, rental_time, photo_path)


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
                                      "Вы можете оставить самокат и поискать новый по близости.",
                     reply_markup=markup)


def save_report(photo, scooter_number, phone_number, card_number, rental_time, description):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO reports (photo, scooter_number, phone_number, card_number, rental_time, description_of_the_problem)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (photo, scooter_number, phone_number, card_number, rental_time, description))

    conn.commit()
    conn.close()


def validate_rental_time(rental_time):
    # Здесь должна быть реализация проверки формата времени (ДД.ММ, ЧАС.МИНУТА)
    import re
    pattern = r'^\d{2}\.\d{2} \d{2}:\d{2}$'
    return bool(re.match(pattern, rental_time))



bot.infinity_polling()
