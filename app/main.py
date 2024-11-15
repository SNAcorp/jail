from fastapi import FastAPI, Request, Form, Cookie, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer
from typing import Dict, Optional
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Защищенные данные для админа
security = HTTPBasic()
admin_email = "stepanov.iop@gmail.com"
admin_password = "12345"
secret_key = "SECRET_KEY"
serializer = URLSafeSerializer(secret_key)

# Список студентов
STUDENTS = [
    "Алексеев Николай Евгеньевич",
    "Алтынников Илья Алексеевич",
    "Богомазов Павел Андреевич",
    "Горюнова Анастасия Павловна",
    "Грейнер Владислав Леонидович",
    "Ефимов Константин Евгеньевич",
    "Залыгин Александр Алексеевич",
    "Казанбаев Кирилл Эльмартович",
    "Коранов Данила Станиславович",
    "Котельников Максим Александрович",
    "Паклин Владислав Алексеевич",
    "Пилявин Артём Михайлович",
    "Попов Кирилл Дмитриевич",
    "Рассказчиков Алексей Павлович",
    "Рудова Светлана Александровна",
    "Сайб Матвей Витальевич",
    "Седова Анна Петровна",
    "Сердюк Алексей Олегович",
    "Степанов Никита Александрович",
    "Шаманаев Кирилл Дмитриевич",
    "Щекина Елена Евгеньевна",
    "Акимов Игорь Дмитриевич",
    "Воловиков Георгий Александрович",
    "Воронько Никита Максимович",
    "Горбачевский Даниил Анатольевич",
    "Горев Артём Дмитриевич",
    "Ершов Дмитрий Владимирович",
    "Корнилов Максим Романович",
    "Кравцова Юлия Евгеньевна",
    "Кузнецов Егор Сергеевич",
    "Левитан Всеволод Романович",
    "Наговицын Максим Дмитриевич",
    "Носаченко Альберт Альбертович",
    "Рогожников Максим Геннадьевич",
    "Степанов Ярослав Олегович",
    "Феоктистов Михаил Алексеевич",
    "Ходорова Мария Петровна",
    "Шпак Александр Юрьевич",
    "Лутковская Екатерина Александровна"
]


class GameState(BaseModel):
    player1: str
    player2: str
    player1_choice: Optional[str] = None
    player2_choice: Optional[str] = None
    timestamp: datetime


# Хранилище данных
active_games: Dict[str, GameState] = {}
completed_games: list = []
available_players = set(STUDENTS)
waiting_players = set()

def calculate_sentence(player_choice: str, opponent_choice: str) -> int:
    if player_choice == "cooperate" and opponent_choice == "cooperate":
        return 1
    elif player_choice == "betray" and opponent_choice == "cooperate":
        return 0
    elif player_choice == "cooperate" and opponent_choice == "betray":
        return 3
    else:  # оба предали
        return 2


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    player = request.cookies.get("player")
    if player:
        player = serializer.loads(player)
        # Проверяем, есть ли активная игра для этого игрока
        game = next((g for g in active_games.values()
                     if g.player1 == player or g.player2 == player), None)
        if game:
            if ((game.player1 == player and game.player1_choice) or
                    (game.player2 == player and game.player2_choice)):
                return templates.TemplateResponse("waiting.html", {
                    "request": request,
                    "opponent": game.player2 if game.player1 == player else game.player1
                })
            return templates.TemplateResponse("choice.html", {
                "request": request,
                "opponent": game.player2 if game.player1 == player else game.player1
            })
        return templates.TemplateResponse("select_opponent.html", {
            "request": request,
            "available_players": list(available_players - {player})
        })
    return templates.TemplateResponse("select_player.html", {
        "request": request,
        "players": STUDENTS
    })


@app.post("/select_player")
async def select_player(request: Request, player: str = Form(...)):
    if player not in STUDENTS:
        raise HTTPException(status_code=400, detail="Invalid player")
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        key="player",
        value=serializer.dumps(player),
        max_age=86400
    )
    available_players.add(player)
    return response


@app.post("/select_opponent")
async def select_opponent(request: Request, opponent: str = Form(...)):
    player = serializer.loads(request.cookies.get("player"))
    if opponent not in available_players or opponent == player:
        raise HTTPException(status_code=400, detail="Invalid opponent")

    game_id = f"{player}-{opponent}"
    active_games[game_id] = GameState(
        player1=player,
        player2=opponent,
        timestamp=datetime.now()
    )
    available_players.remove(player)
    available_players.remove(opponent)

    return RedirectResponse("/", status_code=303)


@app.post("/make_choice")
async def make_choice(request: Request, choice: str = Form(...)):
    # Проверяем валидность выбора
    if choice not in ["betray", "cooperate"]:
        raise HTTPException(status_code=400, detail="Invalid choice")

    # Получаем текущего игрока
    try:
        player = serializer.loads(request.cookies.get("player"))
    except:
        raise HTTPException(status_code=400, detail="Invalid player cookie")

    # Находим активную игру для текущего игрока
    game = next((g for g in active_games.values()
                 if g.player1 == player or g.player2 == player), None)

    if not game:
        raise HTTPException(status_code=400, detail="No active game")

    # Проверяем, не сделал ли игрок уже выбор
    if ((game.player1 == player and game.player1_choice) or
            (game.player2 == player and game.player2_choice)):
        raise HTTPException(status_code=400, detail="Choice already made")

    # Записываем выбор игрока
    if player == game.player1:
        game.player1_choice = choice
    else:
        game.player2_choice = choice

    # Если оба игрока сделали выбор, обрабатываем результаты
    if game.player1_choice and game.player2_choice:
        # Вычисляем сроки заключения
        player1_sentence = calculate_sentence(game.player1_choice, game.player2_choice)
        player2_sentence = calculate_sentence(game.player2_choice, game.player1_choice)

        # Создаём запись о завершённой игре
        completed_game = {
            "game_id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "player1": game.player1,
            "player2": game.player2,
            "player1_choice": game.player1_choice,
            "player2_choice": game.player2_choice,
            "player1_sentence": player1_sentence,
            "player2_sentence": player2_sentence,
            "timestamp": game.timestamp,
            "completion_time": datetime.now()
        }

        completed_games.append(completed_game)

        # Удаляем игру из активных
        game_id = next(k for k, v in active_games.items() if v == game)
        del active_games[game_id]

        # Возвращаем игроков в пул доступных
        available_players.add(game.player1)
        available_players.add(game.player2)

        # Перенаправляем на страницу результатов
        return RedirectResponse(
            f"/results/{completed_game['game_id']}",
            status_code=303
        )

    # Если ждём выбора второго игрока, перенаправляем на страницу ожидания
    return RedirectResponse("/", status_code=303)


def calculate_sentence(player_choice: str, opponent_choice: str) -> int:
    """
    Вычисляет срок заключения для игрока на основе выборов обоих игроков

    Args:
        player_choice (str): выбор игрока ("betray" или "cooperate")
        opponent_choice (str): выбор оппонента ("betray" или "cooperate")

    Returns:
        int: срок заключения в годах
    """
    if player_choice == "cooperate" and opponent_choice == "cooperate":
        return 1  # Оба молчат
    elif player_choice == "betray" and opponent_choice == "cooperate":
        return 0  # Игрок предал, оппонент молчит
    elif player_choice == "cooperate" and opponent_choice == "betray":
        return 3  # Игрок молчит, оппонент предал
    else:  # Оба предали
        return 2


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != admin_email or credentials.password != admin_password:
        raise HTTPException(status_code=401, detail="Неправильные учетные данные")

    # Анализ результатов
    total_games = len(completed_games)
    both_betrayed = sum(1 for g in completed_games
                        if g["player1_choice"] == "betray" and g["player2_choice"] == "betray")
    both_cooperated = sum(1 for g in completed_games
                          if g["player1_choice"] == "cooperate" and g["player2_choice"] == "cooperate")
    one_betrayed = total_games - both_betrayed - both_cooperated

    stats = {
        "total_games": total_games,
        "both_betrayed": both_betrayed,
        "both_cooperated": both_cooperated,
        "one_betrayed": one_betrayed,
        "both_betrayed_percent": (both_betrayed / total_games * 100) if total_games > 0 else 0,
        "both_cooperated_percent": (both_cooperated / total_games * 100) if total_games > 0 else 0,
        "one_betrayed_percent": (one_betrayed / total_games * 100) if total_games > 0 else 0,
        "games": completed_games
    }

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "stats": stats
    })


@app.get("/results/{game_id}", response_class=HTMLResponse)
async def show_results(request: Request, game_id: str):
    try:
        player = serializer.loads(request.cookies.get("player"))
    except:
        return RedirectResponse("/", status_code=303)

    # Ищем игру в завершенных по game_id
    game = next((g for g in completed_games if g["game_id"] == game_id), None)
    if not game:
        return RedirectResponse("/", status_code=303)

    # Проверяем, что текущий игрок участвовал в игре
    if player != game["player1"] and player != game["player2"]:
        return RedirectResponse("/", status_code=303)

    is_player1 = game["player1"] == player

    return templates.TemplateResponse("results.html", {
        "request": request,
        "your_choice": game["player1_choice"] if is_player1 else game["player2_choice"],
        "opponent_choice": game["player2_choice"] if is_player1 else game["player1_choice"],
        "your_sentence": game["player1_sentence"] if is_player1 else game["player2_sentence"],
        "opponent_sentence": game["player2_sentence"] if is_player1 else game["player1_sentence"],
        "opponent_name": game["player2"] if is_player1 else game["player1"],
        "total_sentence": game["player1_sentence"] + game["player2_sentence"]
    })


from fastapi.responses import JSONResponse


@app.get("/check_status")
async def check_status(request: Request):
    try:
        player = serializer.loads(request.cookies.get("player"))

        # Проверяем, есть ли игра в завершенных
        completed_game = next(
            (game for game in completed_games
             if game["player1"] == player or game["player2"] == player),
            None
        )

        if completed_game:
            return JSONResponse({
                "game_completed": True,
                "game_id": completed_game["game_id"]
            })

        # Проверяем активную игру
        active_game = next(
            (game for game in active_games.values()
             if game.player1 == player or game.player2 == player),
            None
        )

        # Если игра существует и оба сделали выбор
        if active_game and active_game.player1_choice and active_game.player2_choice:
            # Рассчитываем результаты
            player1_sentence = calculate_sentence(
                active_game.player1_choice,
                active_game.player2_choice
            )
            player2_sentence = calculate_sentence(
                active_game.player2_choice,
                active_game.player1_choice
            )

            # Создаём запись о завершённой игре
            game_id = datetime.now().strftime("%Y%m%d%H%M%S")
            new_completed_game = {
                "game_id": game_id,
                "player1": active_game.player1,
                "player2": active_game.player2,
                "player1_choice": active_game.player1_choice,
                "player2_choice": active_game.player2_choice,
                "player1_sentence": player1_sentence,
                "player2_sentence": player2_sentence,
                "timestamp": active_game.timestamp,
                "completion_time": datetime.now()
            }

            completed_games.append(new_completed_game)

            # Удаляем из активных игр
            game_key = next(k for k, v in active_games.items() if v == active_game)
            del active_games[game_key]

            # Возвращаем игроков в пул доступных
            available_players.add(active_game.player1)
            available_players.add(active_game.player2)

            return JSONResponse({
                "game_completed": True,
                "game_id": game_id
            })

        return JSONResponse({
            "game_completed": False
        })

    except Exception as e:
        return JSONResponse({
            "game_completed": False,
            "error": str(e)
        })