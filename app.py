import os
import time
import json
import sqlite3
import random
import threading
import requests
from openai import OpenAI

# токен бота берём из переменных окружения
TOKEN = os.environ.get('BOT_TOKEN', '')
WEBHOOK_PATH = '/tg_bot'
API = f'https://api.telegram.org/bot{TOKEN}'
DB_PATH = 'pomodoro.db'

# ключ gemini api
GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '')
# подключаемся к gemini через совместимый с openai интерфейс
client = OpenAI(
    api_key=GEMINI_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
) if GEMINI_KEY else None

# память ии {chat_id: [сообщения]}
AI_MEMORY = {}

# активные таймеры{chat_id: {'timer': Timer, 'mode': str, 'remaining': int, 'end_time': float}}
ACTIVE_TIMERS = {}

STATUS_EMOJI = {
    'work': '🍅',
    'short_break': '☕',
    'long_break': '🛋',
    'idle': '😴',
}

ACHIEVEMENTS = {
    'first_pomodoro': {'icon': '🥇', 'name': 'Первая помидорка'},
    'ten_day':        {'icon': '💪', 'name': '10 помидорок за день'},
    'hundred_total':  {'icon': '🏆', 'name': '100 помидорок всего'},
    'streak_5':       {'icon': '🔥', 'name': '5 дней подряд'},
    'night_owl':      {'icon': '🌙', 'name': 'Работал после 22:00'},
}

LEVELS = [
    (0,   'Новичок'),
    (10,  'Фокусник'),
    (50,  'Мастер Pomodoro'),
    (200, 'Гуру продуктивности'),
]

BREAK_TIPS = [
    'Встань и разомнись 2 минуты.',
    'Выпей стакан воды.',
    'Посмотри в окно, дай глазам отдохнуть.',
    'Сделай дыхание 4-7-8: вдох 4, задержка 7, выдох 8.',
    'Пройдись по комнате.',
    'Разомни шею и плечи.',
]


def log(s, ts='INFO'):
    # просто пишем в файл и в stdout (stdout видно в render logs)
    dt = time.strftime('%d.%m.%Y %H:%M:%S')
    try:
        with open('log.txt', 'a', encoding='utf-8') as f:
            f.write(f'{dt};{ts};{s}\n')
    except Exception:
        pass
    print(f'{dt};{ts};{s}', flush=True)


def progress_bar(elapsed, total, width=10):
    # рисуем прогресс из блоков, на будущее
    if total <= 0:
        return '░' * width
    filled = int(width * elapsed / total)
    filled = max(0, min(width, filled))
    return '█' * filled + '░' * (width - filled)


def ask_ai(chat_id, user_question):
    # отладка. видим, что функция вообще вызывается
    log(f'ask_ai called: chat={chat_id}, q={user_question[:50]}', 'DEBUG')

    # если ключа нет, молча выходим
    if client is None:
        log('ask_ai: client is None — GITHUB_TOKEN не задан', 'Ошибка')
        return None

    if chat_id not in AI_MEMORY:
        AI_MEMORY[chat_id] = []

    messages = [
        {'role': 'system', 'content': (
            'Ты — дружелюбный помощник Pomodoro-бота. '
            'Помогаешь с продуктивностью, концентрацией, '
            'тайм-менеджментом и методом Pomodoro. '
            'Отвечай кратко (2-4 предложения), дружелюбно, на русском. '
            'Если вопрос не по теме — вежливо верни разговор к продуктивности.'
        )}
    ]
    messages.extend(AI_MEMORY[chat_id][-6:])
    messages.append({'role': 'user', 'content': user_question})

    try:
        response = client.chat.completions.create(
            # было model='gpt-4o'
            model='gemini-3.6-flash',
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        answer = response.choices[0].message.content.strip()

        AI_MEMORY[chat_id].append({'role': 'user', 'content': user_question})
        AI_MEMORY[chat_id].append({'role': 'assistant', 'content': answer})
        AI_MEMORY[chat_id] = AI_MEMORY[chat_id][-12:]

        log(f'ask_ai ok: {answer[:60]}', 'DEBUG')
        return answer
    except Exception as e:
        # тут будет видно точную причину
        log(f'ask_ai error: {type(e).__name__}: {e}', 'Ошибка')
        return None


def db_init():
    # создаём таблицы если их ещё нет
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            first_name TEXT,
            tomatoes_today INTEGER DEFAULT 0,
            tomatoes_total INTEGER DEFAULT 0,
            last_date TEXT,
            streak INTEGER DEFAULT 0,
            last_pomodoro_date TEXT,
            xp INTEGER DEFAULT 0,
            achievements TEXT DEFAULT '',
            awaiting_task INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            task TEXT,
            started_at TEXT,
            finished_at TEXT,
            duration INTEGER
        )
    ''')
    conn.commit()
    conn.close()


def db_get_user(chat_id, first_name=None):
    # достаём юзера, если нет создаём
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT chat_id, first_name, tomatoes_today, tomatoes_total,
                        last_date, streak, last_pomodoro_date, xp, achievements, awaiting_task
                 FROM users WHERE chat_id=?''', (chat_id,))
    row = c.fetchone()
    today = time.strftime('%Y-%m-%d')

    if row is None:
        c.execute('''INSERT INTO users
                     (chat_id, first_name, tomatoes_today, tomatoes_total, last_date,
                      streak, last_pomodoro_date, xp, achievements, awaiting_task)
                     VALUES (?, ?, 0, 0, ?, 0, NULL, 0, '', 0)''',
                  (chat_id, first_name or 'друг', today))
        conn.commit()
        conn.close()
        return {'chat_id': chat_id, 'first_name': first_name or 'друг',
                'tomatoes_today': 0, 'tomatoes_total': 0, 'last_date': today,
                'streak': 0, 'last_pomodoro_date': None, 'xp': 0,
                'achievements': '', 'awaiting_task': 0}

    # если наступил новый день, сбрасываем счётчик за сегодня
    if row[4] != today:
        c.execute('UPDATE users SET tomatoes_today=0, last_date=? WHERE chat_id=?',
                  (today, chat_id))
        conn.commit()
        row = (row[0], row[1], 0, row[3], today, row[5], row[6], row[7], row[8], row[9])

    conn.close()
    return {'chat_id': row[0], 'first_name': row[1],
            'tomatoes_today': row[2], 'tomatoes_total': row[3], 'last_date': row[4],
            'streak': row[5] or 0, 'last_pomodoro_date': row[6],
            'xp': row[7] or 0, 'achievements': row[8] or '',
            'awaiting_task': row[9] or 0}


def db_add_tomato(chat_id):
    # +1 помидорка, +10 xp
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''UPDATE users
                 SET tomatoes_today = tomatoes_today + 1,
                     tomatoes_total = tomatoes_total + 1,
                     xp = xp + 10
                 WHERE chat_id=?''', (chat_id,))
    conn.commit()
    conn.close()


def update_streak(chat_id):
    # считаем серию дней подряд
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT streak, last_pomodoro_date FROM users WHERE chat_id=?', (chat_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return 0
    streak, last_date = row
    today = time.strftime('%Y-%m-%d')
    yesterday = time.strftime('%Y-%m-%d', time.localtime(time.time() - 86400))

    if last_date == today:
        pass
    elif last_date == yesterday:
        streak = (streak or 0) + 1
    else:
        streak = 1

    c.execute('UPDATE users SET streak=?, last_pomodoro_date=? WHERE chat_id=?',
              (streak, today, chat_id))
    conn.commit()
    conn.close()
    return streak


def check_streak_break(chat_id):
    # если пропустил больше дня, серия сгорела
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT streak, last_pomodoro_date FROM users WHERE chat_id=?', (chat_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    streak, last_date = row
    today = time.strftime('%Y-%m-%d')
    yesterday = time.strftime('%Y-%m-%d', time.localtime(time.time() - 86400))
    if last_date and last_date != today and last_date != yesterday:
        c.execute('UPDATE users SET streak=0 WHERE chat_id=?', (chat_id,))
        conn.commit()
    conn.close()


def get_level(xp):
    # уровень по xp
    current = LEVELS[0][1]
    for threshold, name in LEVELS:
        if xp >= threshold:
            current = name
    return current


def check_achievements(chat_id, user):
    # проверяем все достижения и выдаём новые
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT achievements FROM users WHERE chat_id=?', (chat_id,))
    row = c.fetchone()
    unlocked = set((row[0] or '').split(',')) if row and row[0] else set()
    unlocked.discard('')

    checks = {
        'first_pomodoro': user['tomatoes_total'] >= 1,
        'ten_day':        user['tomatoes_today'] >= 10,
        'hundred_total':  user['tomatoes_total'] >= 100,
        'streak_5':       user['streak'] >= 5,
        'night_owl':      int(time.strftime('%H')) >= 22,
    }

    new_ones = []
    for key, ok in checks.items():
        if ok and key not in unlocked:
            unlocked.add(key)
            new_ones.append(ACHIEVEMENTS[key])

    if new_ones:
        c.execute('UPDATE users SET achievements=? WHERE chat_id=?',
                  (','.join(unlocked), chat_id))
        conn.commit()
    conn.close()

    for ach in new_ones:
        send_message(
            chat_id,
            f'🏆 <b>Новое достижение!</b>\n\n{ach["icon"]} <b>{ach["name"]}</b>',
            None
        )


def send_message(chat_id, text, keyboard=None):
    # базовый sendMessage с html
    url = f'{API}/sendMessage'
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard, ensure_ascii=False)
    try:
        r = requests.post(url, data=payload, timeout=10)
        if not r.ok:
            log(f'sendMessage failed: {r.text}', 'Ошибка')
        return r.json().get('result', {}).get('message_id')
    except Exception as e:
        log(f'sendMessage exception: {e}', 'Ошибка')
        return None


def edit_message(chat_id, message_id, text, keyboard=None):
    # редактируем сообщение (пригодится для прогресс-бара)
    url = f'{API}/editMessageText'
    payload = {'chat_id': chat_id, 'message_id': message_id,
               'text': text, 'parse_mode': 'HTML'}
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard, ensure_ascii=False)
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        log(f'editMessage exception: {e}', 'Ошибка')


def answer_callback(callback_id, text=None):
    # убираем "часики" у кнопки
    url = f'{API}/answerCallbackQuery'
    payload = {'callback_query_id': callback_id}
    if text:
        payload['text'] = text
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        log(f'answerCallback exception: {e}', 'Ошибка')


def set_reaction(chat_id, message_id, emoji='🍅'):
    # ставим реакцию на сообщение (работает не везде)
    url = f'{API}/setMessageReaction'
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'reaction': json.dumps([{'type': 'emoji', 'emoji': emoji}], ensure_ascii=False)
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        if not r.ok:
            log(f'setReaction failed: {r.text}', 'Ошибка')
    except Exception as e:
        log(f'setReaction exception: {e}', 'Ошибка')


def send_reply_keyboard(chat_id):
    # нижнее постоянное меню
    url = f'{API}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': 'Постоянное меню активировано 👇',
        'reply_markup': json.dumps({
            'keyboard': [
                [{'text': '▶️ Старт'}, {'text': '⏸ Пауза'}, {'text': '⏹ Стоп'}],
                [{'text': '🍅 Статистика'}, {'text': '📖 История'}],
                [{'text': '⚙️ Настройки'}],
            ],
            'resize_keyboard': True
        }, ensure_ascii=False)
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        log(f'reply_keyboard exception: {e}', 'Ошибка')


def kb_main(user=None):
    # основная inline-клавиатура со счётчиками
    tomatoes = user['tomatoes_today'] if user else 0
    streak = user['streak'] if user else 0
    streak_icon = '🔥 ' if streak >= 4 else ''

    return {
        'inline_keyboard': [
            [{'text': '▶️ Старт', 'callback_data': 'work'},
             {'text': '⏸ Пауза', 'callback_data': 'pause'},
             {'text': '⏹ Стоп', 'callback_data': 'stop'}],
            [{'text': f'🍅 {tomatoes}', 'callback_data': 'stats'},
             {'text': f'{streak_icon}серия: {streak}', 'callback_data': 'stats'}],
            [{'text': '❓ Что такое Pomodoro?', 'callback_data': 'about'}],
            [{'text': '📖 История', 'callback_data': 'history'},
             {'text': '⚙️ Настройки', 'callback_data': 'settings'}],
        ]
    }


def kb_back():
    # кнопка "назад в меню"
    return {
        'inline_keyboard': [
            [{'text': '⬅️ В меню', 'callback_data': 'menu'}],
        ]
    }


def start_timer(chat_id, minutes, mode):
    # запускаем таймер через threading.timer
    seconds = minutes * 60
    end_time = time.time() + seconds

    def fire():
        # срабатывает когда время вышло
        ACTIVE_TIMERS.pop(chat_id, None)
        try:
            user = db_get_user(chat_id)

            if mode == 'work':
                # засчитываем помидорку, обновляем серию, проверяем ачивки
                db_add_tomato(chat_id)
                update_streak(chat_id)
                user = db_get_user(chat_id)
                check_achievements(chat_id, user)

                if user['tomatoes_today'] % 4 == 0 and user['tomatoes_today'] > 0:
                    break_text = '🛋 Ты сделал 4 помидорки! Пора на длинный перерыв.'
                else:
                    break_text = f'☕ {random.choice(BREAK_TIPS)}'

                send_message(
                    chat_id,
                    f'⏰ <b>Работа завершена!</b>\n\n'
                    f'Сегодня: <b>{user["tomatoes_today"]} 🍅</b>\n'
                    f'Серия: <b>{user["streak"]} 🔥</b>\n'
                    f'XP: <b>{user["xp"]}</b> ({get_level(user["xp"])})\n\n'
                    f'{break_text}',
                    kb_main(user)
                )
            elif mode == 'short_break':
                send_message(chat_id,
                    '⏰ <b>Перерыв закончился!</b>\n\nГотов к следующей помидорке?',
                    kb_main(user))
            elif mode == 'long_break':
                send_message(chat_id,
                    '⏰ <b>Длинный перерыв закончился!</b>\n\nВозвращаемся к работе?',
                    kb_main(user))
        except Exception as e:
            log(f'timer fire error: {e}', 'Ошибка')

    t = threading.Timer(seconds, fire)
    t.daemon = True
    t.start()
    ACTIVE_TIMERS[chat_id] = {'timer': t, 'mode': mode, 'minutes': minutes,
                              'end_time': end_time}
    log(f'Таймер запущен: {chat_id}, {minutes} мин, режим {mode}', 'DEBUG')


def stop_timer(chat_id):
    # останавливаем и убираем таймер
    info = ACTIVE_TIMERS.pop(chat_id, None)
    if info:
        info['timer'].cancel()
        return info
    return None


def pause_timer(chat_id):
    # ставим на паузу и сохраняем остаток
    info = ACTIVE_TIMERS.pop(chat_id, None)
    if not info:
        return None
    info['timer'].cancel()
    remaining = max(0, int(info['end_time'] - time.time()))
    info['remaining'] = remaining
    return info, remaining


def handle_work(chat_id):
    # старт работы, спрашиваем задачу
    user = db_get_user(chat_id)
    if ACTIVE_TIMERS.get(chat_id):
        send_message(chat_id, '⚠️ Таймер уже запущен. Нажми Стоп, чтобы сбросить.', kb_main(user))
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET awaiting_task=1 WHERE chat_id=?', (chat_id,))
    conn.commit()
    conn.close()

    send_message(chat_id,
        '🍅 <b>Работаем 25 минут!</b>\n\n'
        'Напиши, над чем будешь работать (одним сообщением):',
        None)


def actually_start_work(chat_id, task):
    # запускаем таймер после того как написали задачу
    user = db_get_user(chat_id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO sessions (chat_id, task, started_at, duration)
                 VALUES (?, ?, ?, ?)''',
              (chat_id, task, time.strftime('%Y-%m-%d %H:%M:%S'), 25))
    conn.commit()
    conn.close()

    send_message(chat_id,
        f'✅ Записал: <b>{task}</b>\n\n⏱ Таймер пошёл - 25 минут!',
        kb_main(user))
    start_timer(chat_id, 25, 'work')


def handle_short_break(chat_id):
    if ACTIVE_TIMERS.get(chat_id):
        send_message(chat_id, '⚠️ Таймер уже запущен.', kb_main(db_get_user(chat_id)))
        return
    user = db_get_user(chat_id)
    send_message(chat_id,
        f'☕ <b>Перерыв 5 минут</b>\n\n{random.choice(BREAK_TIPS)}',
        kb_main(user))
    start_timer(chat_id, 5, 'short_break')


def handle_long_break(chat_id):
    if ACTIVE_TIMERS.get(chat_id):
        send_message(chat_id, '⚠️ Таймер уже запущен.', kb_main(db_get_user(chat_id)))
        return
    user = db_get_user(chat_id)
    send_message(chat_id,
        '🛋 <b>Длинный перерыв 15 минут</b>\n\nОтдохни как следует.',
        kb_main(user))
    start_timer(chat_id, 15, 'long_break')


def handle_pause(chat_id):
    result = pause_timer(chat_id)
    user = db_get_user(chat_id)
    if not result:
        send_message(chat_id, 'Нечего ставить на паузу.', kb_main(user))
        return
    info, remaining = result
    minutes = remaining // 60
    seconds = remaining % 60
    send_message(chat_id,
        f'⏸ <b>Пауза</b>\n\nОсталось: {minutes}:{seconds:02d}\n'
        f'Напиши /resume, чтобы продолжить, или нажми Старт заново.',
        kb_main(user))


def handle_stop(chat_id):
    info = stop_timer(chat_id)
    user = db_get_user(chat_id)
    if not info:
        send_message(chat_id, 'Нет активного таймера.', kb_main(user))
        return
    send_message(chat_id, '⏹ <b>Таймер остановлен.</b>', kb_main(user))


def handle_resume(chat_id):
    info = ACTIVE_TIMERS.get(chat_id)
    if info and info.get('remaining'):
        minutes = info['remaining'] // 60
        seconds = info['remaining'] % 60
        send_message(chat_id, f'▶️ Продолжаем. Осталось {minutes}:{seconds:02d}')
        start_timer(chat_id, max(1, info['remaining'] // 60), info['mode'])
    else:
        send_message(chat_id, 'Нечего продолжать.', kb_main(db_get_user(chat_id)))


def handle_stats(chat_id):
    user = db_get_user(chat_id)
    unlocked = [k for k in (user['achievements'] or '').split(',') if k]
    ach_lines = '\n'.join(f'  {ACHIEVEMENTS[k]["icon"]} {ACHIEVEMENTS[k]["name"]}'
                          for k in unlocked if k in ACHIEVEMENTS) or '  <i>пока нет</i>'

    text = (
        '🍅 <b>Мои помидорки</b>\n\n'
        f'Сегодня: <b>{user["tomatoes_today"]}</b>\n'
        f'Всего: <b>{user["tomatoes_total"]}</b>\n'
        f'Серия: <b>{user["streak"]} 🔥</b>\n'
        f'XP: <b>{user["xp"]}</b> — {get_level(user["xp"])}\n\n'
        f'<b>Достижения:</b>\n{ach_lines}'
    )
    send_message(chat_id, text, kb_back())


def handle_history(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT task, started_at, duration FROM sessions
                 WHERE chat_id=? ORDER BY id DESC LIMIT 10''', (chat_id,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        send_message(chat_id, 'Пока нет завершённых сессий.', kb_back())
        return

    lines = ['📖 <b>Последние сессии</b>\n']
    for task, started_at, duration in rows:
        lines.append(f'• {started_at} — <b>{task}</b> ({duration} мин)')
    send_message(chat_id, '\n'.join(lines), kb_back())


def handle_about(chat_id):
    text = (
        '❓ <b>Что такое Pomodoro?</b>\n\n'
        'Метод Pomodoro придумал Франческо Чирилло в конце 1980-х. '
        'Суть: работаешь <b>25 минут</b> без отвлечений, затем '
        '<b>5 минут</b> отдыхаешь. После четырёх циклов - длинный '
        'перерыв <b>15-30 минут</b>.\n\n'
        '<b>Зачем это нужно:</b>\n'
        '• Дисциплина - не залипаешь в задаче бесконечно.\n'
        '• Концентрация - короткие отрезки легче выдержать.\n'
        '• Отдых - мозг успевает восстановиться.\n'
        '• Прогресс - видно, сколько «помидорок» сделано.\n\n'
        '<i>Название «помидор» - потому что Чирилло использовал '
        'кухонный таймер в виде помидора.</i>'
    )
    send_message(chat_id, text, kb_back())


def handle_settings(chat_id):
    text = (
        '⚙️ <b>Настройки и подсказки</b>\n\n'
        '• <b>/start</b> - начать заново, показать меню\n'
        '• <b>/menu</b> - меню\n'
        '• <b>/stats</b> - статистика\n'
        '• <b>/history</b> - последние сессии\n'
        '• <b>/about</b> - что такое Pomodoro\n'
        '• <b>/resume</b> - продолжить после паузы\n'
        '• <b>/help</b> - эта справка\n\n'
        '<b>Рекомендации:</b>\n'
        '• Не пропускай перерывы - это часть метода.\n'
        '• Записывай задачи заранее.\n'
        '• Следи за серией 🔥 она мотивирует.\n\n'
        '<i>Если хочешь спросить что-то у ИИ — просто напиши сообщением.</i>'
    )
    send_message(chat_id, text, kb_back())


def handle_menu(chat_id):
    user = db_get_user(chat_id)
    send_message(chat_id, '🍅 <b>Pomodoro-бот</b>\n\nВыбери действие:', kb_main(user))


# WSGI приложение
def application(environ, start_response):
    try:
        path = environ.get('PATH_INFO', '').lower()
        method = environ.get('REQUEST_METHOD', 'GET')

        # healthcheck для render
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
            log(f'RAW: {text[:300]}', 'DEBUG')

            try:
                data = json.loads(text)
            except Exception as e:
                log(f'JSON parse error: {e}', 'Ошибка')
                start_response('200 OK', [('Content-Type', 'text/plain')])
                return [b'ok']

            # обработка обычных сообщений
            message = data.get('message')
            if message:
                chat_id = message['chat']['id']
                first_name = message['from'].get('first_name', 'друг')
                user_text = (message.get('text') or '').strip()

                db_get_user(chat_id, first_name)
                check_streak_break(chat_id)

                # reply кнопки снизу
                if user_text == '▶️ Старт':
                    handle_work(chat_id)
                    user_text = ''
                elif user_text == '⏸ Пауза':
                    handle_pause(chat_id)
                    user_text = ''
                elif user_text == '⏹ Стоп':
                    handle_stop(chat_id)
                    user_text = ''
                elif user_text == '🍅 Статистика':
                    handle_stats(chat_id)
                    user_text = ''
                elif user_text == '📖 История':
                    handle_history(chat_id)
                    user_text = ''
                elif user_text == '⚙️ Настройки':
                    handle_settings(chat_id)
                    user_text = ''

                # команды
                if user_text == '/start':
                    send_reply_keyboard(chat_id)
                    send_message(
                        chat_id,
                        f'Привет, {first_name}! 👋\n\n'
                        f'Я - Pomodoro-бот. Помогу работать по методу «помидора»: '
                        f'25 минут фокуса, 5 минут отдыха.\n\n'
                        f'Выбери действие в меню ниже 👇\n'
                        f'А если хочешь спросить что-то у ИИ — просто напиши сообщением.',
                        kb_main(db_get_user(chat_id))
                    )
                elif user_text == '/menu':
                    handle_menu(chat_id)
                elif user_text == '/about':
                    handle_about(chat_id)
                elif user_text == '/stats':
                    handle_stats(chat_id)
                elif user_text == '/history':
                    handle_history(chat_id)
                elif user_text == '/help':
                    handle_settings(chat_id)
                elif user_text == '/resume':
                    handle_resume(chat_id)

                # задача или вопрос ии
                elif user_text and not user_text.startswith('/'):
                    user = db_get_user(chat_id)
                    if user['awaiting_task']:
                        # юзер ответил на "над чем работаешь?"
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute('UPDATE users SET awaiting_task=0 WHERE chat_id=?', (chat_id,))
                        conn.commit()
                        conn.close()
                        actually_start_work(chat_id, user_text)
                    else:
                        # обычный вопрос, отдаём ии
                        send_message(chat_id, '🤔 Думаю...', None)
                        ai_answer = ask_ai(chat_id, user_text)
                        if ai_answer:
                            send_message(chat_id, ai_answer, kb_main(user))
                        else:
                            send_message(chat_id,
                                'Не могу сейчас ответить. Попробуй команды или кнопки.',
                                kb_main(user))

            # обработка кнопок
            callback = data.get('callback_query')
            if callback:
                callback_id = callback['id']
                chat_id = callback['message']['chat']['id']
                message_id = callback['message']['message_id']
                action = callback.get('data', '')

                answer_callback(callback_id)

                if action == 'work':
                    handle_work(chat_id)
                elif action == 'short_break':
                    handle_short_break(chat_id)
                elif action == 'long_break':
                    handle_long_break(chat_id)
                elif action == 'pause':
                    handle_pause(chat_id)
                elif action == 'stop':
                    handle_stop(chat_id)
                elif action == 'stats':
                    handle_stats(chat_id)
                elif action == 'history':
                    handle_history(chat_id)
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


# создаём таблицы при старте
db_init()
