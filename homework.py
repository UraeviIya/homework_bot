import logging
import os
import time
from http import HTTPStatus

import sys
import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TOKENS = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    logger.info(f'Сообщение отправлено {message}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
    except telegram.error as error:
        raise error('Сбой отправки сообщения')


def get_api_answer(current_timestamp):
    """Отправляет запрос к API на ENDPOINT и получает данные."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logger.info(f'Отправлен запрос к API: {params}')
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params
                                         )
    except Exception as error:
        raise Exception(f'Ошибка при запросе к основному API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        raise Exception(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except ValueError:
        raise ValueError('Ошибка парсинга ответа из формата json')


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    homeworks = response.get('homeworks')
    if 'homeworks' and 'current_date' not in response.keys():
        raise KeyError('Отсутствуют ключи')
    if not isinstance(homeworks, list):
        raise TypeError('Ответ API не является словарём')
    return homeworks


def parse_status(homework):
    """
    Извлекаем статус конкретной домашней работы.
    В случае успеха, возврящяем один из вердиктов словаря HOMEWORK_STATUSES
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if 'status' not in homework:
        raise Exception(f'Ошибка. Значение статуса пустое: {homework_status}')
    if 'homework_name' not in homework:
        raise KeyError(f'Ошибка. Значение имени работы пусто: {homework_name}')
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'Недокументированный статус : {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения.
    Которые необходимы для работы программы.
    При отсутствии переменной вернем False, иначе-True
    """
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутсвует один или несколько токенов')
        sys.exit('Отсутсвует один или несколько токенов')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                if homework is not None:
                    send_message(bot, homework)
            else:
                logger.debug('Нет новых статусов')
            current_timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
