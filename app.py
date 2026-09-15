import os
import time
import json
import requests

TOKEN = os.environ.get('BOT_TOKEN', '')
WEBHOOK_PATH = '/tg_bot'
API = f'https://api.telegram.org/bot{TOKEN}'

def log(s, ts='INFO'):
    dt = time.strftime('%d.%m.%Y %H:%M:%S')
    try:
        with open('log.txt', 'a', encoding='utf-8') as f:
            f.write(f'{dt};{ts};{s}\n')
    except Exception:
        pass
    print(f'{dt};{ts};{s}', flush=True)


def send_message(chat_id, text, keyboard=None):
    url = f'{API}/sendMessage'
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard, ensure_ascii=False)
    try:
        r = requests.post(url, data=payload, timeout=10)
        log(f'sendMessage status={r.status_code} response={r.text[:200]}', 'DEBUG')
        if not r.ok:
            log(f'sendMessage failed: {r.text}', 'Ошибка')
    except Exception as e:
        log(f'sendMessage exception: {e}', 'Ошибка')


def answer_callback(callback_id, text=None):
    url = f'{API}/answerCallbackQuery'
    payload = {'callback_query_id': callback_id}
    if text:
        payload['text'] = text
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        log(f'answerCallback exception: {e}', 'Ошибка')


def kb_main():
    return {
        'inline_keyboard': [
            [{'text': '▶️ Начать работу', 'callback_data': 'work'}],
            [{'text': '☕ Перерыв 5 мин', 'callback_data': 'short_break'}],
            [{'text': '🛋 Длинный перерыв 15 мин', 'callback_data': 'long_break'}],
            [{'text': '🍅 Мои помидорки', 'callback_data': 'stats'}],
            [{'text': '❓ Что такое Pomodoro?', 'callback_data': 'about'}],
            [{'text': '⚙️ Как настроить?', 'callback_data': 'settings'}],
        ]
    }


def kb_back():
    return {
        'inline_keyboard': [
            [{'text': '⬅️ В меню', 'callback_data': 'menu'}],
        ]
    }


def handle_work(chat_id):
    text = (
        '🍅 <b>Работаем 25 минут!</b>\n\n'
        'Сосредоточься на одной задаче. Не отвлекайся на телефон, '
        'соцсети и чаты. Когда время выйдет - бот пришлёт уведомление '
        'и предложит перерыв.\n\n'
        '<i>Совет: запиши, что именно ты делаешь эти 25 минут.</i>'
    )
    send_message(chat_id, text, kb_back())


def handle_short_break(chat_id):
    text = (
        '☕ <b>Перерыв 5 минут</b>\n\n'
        'Встань, разомнись, попей воды. Не бери телефон - '
        'лучше посмотри в окно или пройдись.\n\n'
        'После перерыва возвращайся к работе.'
    )
    send_message(chat_id, text, kb_back())


def handle_long_break(chat_id):
    text = (
        '🛋 <b>Длинный перерыв 15-30 минут</b>\n\n'
        'Ты сделал 4 помидорки - можно отдохнуть подольше. '
        'Поешь, прогуляйся, отвлекись полностью.\n\n'
        'После отдыха - снова в бой.'
    )
    send_message(chat_id, text, kb_back())


def handle_stats(chat_id):
    # можно подключить БД. пока заглушка.
    text = (
        '🍅 <b>Мои помидорки</b>\n\n'
        'Сегодня: <b>0</b> помидорок\n'
        'За неделю: <b>0</b>\n'
        'Всего: <b>0</b>\n\n'
        '<i>Счётчик появится после подключения базы данных.</i>'
    )
    send_message(chat_id, text, kb_back())


def handle_about(chat_id):
    text = (
        '❓ <b>Что такое Pomodoro?</b>\n\n'
        'Метод Pomodoro придумал Франческо Чирилло в конце 1980-х. '
        'Суть простая: ты работаешь <b>25 минут</b> без отвлечений, '
        'затем <b>5 минут</b> отдыхаешь. После четырёх таких циклов - '
        'длинный перерыв <b>15-30 минут</b>.\n\n'
        '<b>Зачем это нужно:</b>\n'
        '• Дисциплина - ты не залипаешь в задаче бесконечно.\n'
        '• Концентрация - короткие отрезки легче выдержать.\n'
        '• Отдых - мозг успевает восстановиться.\n'
        '• Прогресс - видно, сколько «помидорок» сделано за день.\n\n'
        '<i>Название «помидор» - потому что Чирилло использовал '
        'кухонный таймер в виде помидора.</i>'
    )
    send_message(chat_id, text, kb_back())


def handle_settings(chat_id):
    text = (
        '⚙️ <b>Как настроить Pomodoro через бота</b>\n\n'
        '1. Открой меню кнопкой ниже.\n'
        '2. Выбери режим: работа / короткий перерыв / длинный перерыв.\n'
        '3. Следи за уведомлениями - бот напомнит, когда время выйдет.\n'
        '4. Веди счёт помидорок: каждая завершённая сессия = 🍅.\n\n'
        '<b>Рекомендации:</b>\n'
        '• Начни с 25/5. Если тяжело - попробуй 50/10.\n'
        '• Не пропускай перерывы - это часть метода.\n'
        '• Записывай задачи заранее, чтобы не тратить время на выбор.\n\n'
        '<i>Скоро здесь появятся настройки длительности и уведомлений.</i>'
    )
    send_message(chat_id, text, kb_back())


def handle_menu(chat_id):
    text = (
        '🍅 <b>Pomodoro-бот</b>\n\n'
        'Выбери, что делать:\n'
        '• Начать работу - 25 минут фокуса.\n'
        '• Перерыв - 5 или 15 минут.\n'
        '• Мои помидорки - счётчик за день.\n'
        '• Что такое Pomodoro - короткое объяснение.\n'
        '• Как настроить - рекомендации.'
    )
    send_message(chat_id, text, kb_main())


def application(environ, start_response):
    try:
        path = environ.get('PATH_INFO', '').lower()
        method = environ.get('REQUEST_METHOD', 'GET')

        # healthcheck для Render
        if path == '/healthcheck':
            start_response('200 OK', [('Content-Type', 'text/plain; charset=utf-8')])
            return [b'OK']

        if path == WEBHOOK_PATH and method == 'POST':
            try:
                raw = environ['wsgi.input'].read()
            except Exception as e:
                log(f'read wsgi.input error: {e}', 'Ошибка')
                raw = b''

            text = raw.decode('UTF-8', errors='replace')
            log(f'RAW: {text}', 'DEBUG')

            try:
                data = json.loads(text)
            except Exception as e:
                log(f'JSON parse error: {e} | raw: {text}', 'Ошибка')
                start_response('200 OK', [('Content-Type', 'text/plain')])
                return [b'ok']

            message = data.get('message')
            if message:
                chat_id = message['chat']['id']
                first_name = message['from'].get('first_name', 'друг')
                user_text = (message.get('text') or '').strip()

                if user_text == '/start':
                    send_message(
                        chat_id,
                        f'Привет, {first_name}! 👋\n\n'
                        f'Я — Pomodoro-бот. Помогу тебе работать '
                        f'по методу «помидора»: 25 минут фокуса, 5 минут отдыха.\n\n'
                        f'Выбери действие в меню ниже 👇',
                        kb_main()
                    )
                elif user_text == '/menu':
                    handle_menu(chat_id)
                elif user_text == '/about':
                    handle_about(chat_id)
                elif user_text == '/stats':
                    handle_stats(chat_id)
                elif user_text == '/help':
                    handle_settings(chat_id)
                else:
                    send_message(
                        chat_id,
                        'Я понимаю команды:\n'
                        '/start — начать\n'
                        '/menu — меню\n'
                        '/about — что такое Pomodoro\n'
                        '/stats — мои помидорки\n'
                        '/help — как настроить',
                        kb_main()
                    )

            callback = data.get('callback_query')
            if callback:
                callback_id = callback['id']
                chat_id = callback['message']['chat']['id']
                action = callback.get('data', '')

                answer_callback(callback_id)

                if action == 'work':
                    handle_work(chat_id)
                elif action == 'short_break':
                    handle_short_break(chat_id)
                elif action == 'long_break':
                    handle_long_break(chat_id)
                elif action == 'stats':
                    handle_stats(chat_id)
                elif action == 'about':
                    handle_about(chat_id)
                elif action == 'settings':
                    handle_settings(chat_id)
                elif action == 'menu':
                    handle_menu(chat_id)

            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'ok']

        log(f'Вызов неизвестного URL: {path}', 'DEBUG')
        start_response('200 OK', [('Content-Type', 'text/plain; charset=utf-8')])
        return [b'Bot is running.']

    except Exception as e:
        log(f'GLOBAL ERROR: {e}', 'Ошибка')
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'ok']
