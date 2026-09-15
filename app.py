import os
import time
import json
import requests

TOKEN = os.environ.get('BOT_TOKEN', '')
WEBHOOK_PATH = '/tg_bot'

def log(s, ts='Запись'):
    dt = time.strftime('%d.%m.%Y %H:%M:%S')
    with open('log.txt', 'a', encoding='utf-8') as f:
        f.write(f'{dt};{ts};{s}\n')

def send_message(chat_id, text):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    try:
        r = requests.post(url, data={'chat_id': chat_id, 'text': text}, timeout=10)
        if not r.ok:
            log(f'sendMessage failed: {r.text}', 'Ошибка')
    except Exception as e:
        log(f'sendMessage exception: {e}', 'Ошибка')

def application(environ, start_response):
    try:
        path = environ.get('PATH_INFO', '').lower()
        method = environ.get('REQUEST_METHOD', 'GET')

        # отвечаем 200, чтобы сервис не усыплялся
        if path == '/healthcheck':
            start_response('200 OK', [('Content-Type', 'text/plain; charset=utf-8')])
            return [b'OK']

        # Основной webhook
        if path == WEBHOOK_PATH and method == 'POST':
            # читаем тело
            length = int(environ.get('CONTENT_LENGTH', 0) or 0)
            raw = environ['wsgi.input'].read(length) if length else b''
            text = raw.decode('UTF-8')

            text = text.replace('\n', ' ')

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
                user_text = message.get('text', '')

                if user_text == '/start':
                    reply = f'Ну, привет, {first_name}!'
                else:
                    reply = f'Ты написал: {user_text}'

                send_message(chat_id, reply)

            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'ok']
          
        log(f'Вызов неизвестного URL: {path}')
        start_response('200 OK', [('Content-Type', 'text/plain; charset=utf-8')])
        return [b'Bot is running.']

    except Exception as e:
        log(str(e), 'Ошибка')
        # ВСЕГДА 200, чтобы Telegram не заблокировал webhook
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'ok']
