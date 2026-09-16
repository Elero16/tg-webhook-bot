# 🍅 Pomodoro-бот для Telegram

мой первый Telegram-бот, который помогает работать по методу Pomodoro: 25 минут фокуса, 5 минут отдыха. Написан на чистом Python (WSGI), без фреймворков, работает через webhook на Render.

## ✨ Возможности

- ⏱ Таймер 25/5/15 минут с реальным уведомлением по завершении
- ▶️ Inline- и reply-кнопки: Старт / Пауза / Стоп / Статистика / История
- 📝 Учёт задач - бот спрашивает, над чем работаешь
- 📖 Дневник сессий — команда `/history`
- 🍅 Счётчик помидорок за день и всего
- 🔥 Серии (streaks) - дни подряд с хотя бы одной помидоркой
- 🏆 5 достижений (первая помидорка, 10 за день, 100 всего, 5 дней подряд, ночная сова)
- ⚡ XP и уровни: Новичок - Фокусник - Мастер Pomodoro - Гуру продуктивности
- ☕ Умные советы на перерыве (разомнись, выпей воды, дыхание 4-7-8)

## 🚀 Деплой на Render

1. Форкните репозиторий или залейте код в свой GitHub.
2. Создайте **Web Service** на [render.com](https://render.com).
3. Настройки:
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:application --bind 0.0.0.0:$PORT`
4. **Environment Variables:** добавьте `BOT_TOKEN` = токен от [@BotFather](https://t.me/BotFather).
5. Задеплойте.

## 🔗 Регистрация webhook

После деплоя откройте в браузере:
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<ваш-сервис>.onrender.com/tg_bot

Проверка:
https://api.telegram.org/bot<TOKEN>/getWebhookInfo


## 📋 Команды бота

| Команда | Что делает |
|---|---|
| `/start` | Приветствие + меню |
| `/menu` | Показать меню |
| `/about` | Что такое Pomodoro |
| `/stats` | Статистика, XP, достижения |
| `/history` | Последние 10 сессий |
| `/help` | Справка по настройке |
| `/resume` | Продолжить после паузы |

## 📁 Структура
app.py # WSGI-приложение (вся логика)
requirements.txt # gunicorn, requests
Procfile # команда запуска
README.md # этот файл


## ⚠️ Ограничения Render Free

- Сервис **засыпает через 15 минут бездействия**. Первое сообщение идёт 30–50 секунд.
- `pomodoro.db` и `log.txt` **не сохраняются** между рестартами (ephemeral filesystem).
- Для надёжных уведомлений настройте пингер на `/healthcheck` (например, через [cron-job.org](https://cron-job.org)).

## 🛠 Стек

- Python 3.11+ (WSGI, стандартная библиотека)
- `requests` - для Bot API
- `sqlite3` - хранение пользователей и сессий
- `threading.Timer` - таймеры
- `gunicorn`  WSGI-сервер

## Апдейт на 16.09.26
Добавлен простой ИИ агент от OpenAI
