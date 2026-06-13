import sys
import time
import chess
import chess.polyglot

BOOK_PATH = "book.bin"

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

# --- ТАБЛИЦЫ ОЦЕНКИ ПОЗИЦИЙ ---

PAWN_EVAL_WHITE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0
]

KNIGHT_EVAL_WHITE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50
]

BISHOP_EVAL_WHITE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20
]

ROOK_EVAL_WHITE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, 10, 10, 10, 10, 5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    0, 0, 0, 5, 5, 0, 0, 0
]

QUEEN_EVAL_WHITE = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20
]

KING_EVAL_WHITE_MIDDLEGAME = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20
]

# В эндшпиле король должен идти в центр
KING_EVAL_WHITE_ENDGAME = [
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10, 0, 0, -10, -20, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50
]


class SearchTimeout(Exception):
    pass


# Константы для типов записей в Таблице Транспозиций
TT_EXACT = 0
TT_LOWERBOUND = 1
TT_UPPERBOUND = 2

transposition_table = {}
MAX_TT_SIZE = 1000000

search_start_time = 0
time_limit_for_move = 0
nodes_count = 0


def check_time():
    if time.time() - search_start_time > time_limit_for_move:
        raise SearchTimeout()


def order_moves(board, moves=None, tt_move=None):
    """Сортировка ходов с улучшенным MVV-LVA"""
    iterable_moves = moves if moves is not None else board.legal_moves

    def move_score(move):
        # Хеш-ход из TT всегда имеет наивысший приоритет
        if tt_move and move == tt_move:
            return 10000

        score = 0
        if board.color_at(move.to_square) == (not board.turn):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)

            # Улучшенный MVV-LVA: учитываем ценность атакующей фигуры
            if victim and attacker:
                # Меньшая цифра attacker.piece_type - более ценная фигура
                # Делим на 10, чтобы ценность жертвы всегда была важнее
                score += 100 + victim.piece_type - (attacker.piece_type / 10.0)

        if move.promotion:
            score += 50

        return score

    return sorted(iterable_moves, key=move_score, reverse=True)


def is_endgame(board):
    """Простая проверка на эндшпиль: отсутствие ферзей или мало материала"""
    has_queens = len(board.pieces(chess.QUEEN, chess.WHITE)) > 0 or len(board.pieces(chess.QUEEN, chess.BLACK)) > 0
    if not has_queens:
        return True

    # Если ферзи есть, но фигур мало
    minor_pieces = len(board.pieces(chess.KNIGHT, chess.WHITE)) + len(board.pieces(chess.BISHOP, chess.WHITE)) + \
                   len(board.pieces(chess.KNIGHT, chess.BLACK)) + len(board.pieces(chess.BISHOP, chess.BLACK))
    rooks = len(board.pieces(chess.ROOK, chess.WHITE)) + len(board.pieces(chess.ROOK, chess.BLACK))

    return minor_pieces + rooks <= 3


def quiescence_search(board, alpha, beta, maximizing_player):
    """Поиск затишья с корректной обработкой шахов"""
    global nodes_count
    nodes_count += 1
    check_time()

    in_check = board.is_check()

    # Если мы НЕ под шахом, делаем отсечение по stand-pat
    if not in_check:
        stand_pat = evaluate_board(board)
        if maximizing_player:
            if stand_pat >= beta:
                return beta
            if alpha < stand_pat:
                alpha = stand_pat
        else:
            if stand_pat <= alpha:
                return alpha
            if beta > stand_pat:
                beta = stand_pat

    # Если под шахом - генерируем все легальные уклонения, иначе - только взятия
    if in_check:
        moves_to_search = list(board.legal_moves)
    else:
        moves_to_search = list(board.generate_legal_captures())

    moves_to_search = order_moves(board, moves_to_search)

    if maximizing_player:
        for move in moves_to_search:
            board.push(move)
            score = quiescence_search(board, alpha, beta, False)
            board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha
    else:
        for move in moves_to_search:
            board.push(move)
            score = quiescence_search(board, alpha, beta, True)
            board.pop()

            if score <= alpha:
                return alpha
            if score < beta:
                beta = score
        return beta


def evaluate_board(board):
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    endgame_phase = is_endgame(board)

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            value = PIECE_VALUES[piece.piece_type]
            position_bonus = 0

            file = chess.square_file(square)
            rank = chess.square_rank(square)

            if piece.color == chess.WHITE:
                sq_index = (7 - rank) * 8 + file
            else:
                sq_index = rank * 8 + file

            if piece.piece_type == chess.PAWN:
                position_bonus = PAWN_EVAL_WHITE[sq_index]
            elif piece.piece_type == chess.KNIGHT:
                position_bonus = KNIGHT_EVAL_WHITE[sq_index]
            elif piece.piece_type == chess.BISHOP:
                position_bonus = BISHOP_EVAL_WHITE[sq_index]
            elif piece.piece_type == chess.ROOK:
                position_bonus = ROOK_EVAL_WHITE[sq_index]
            elif piece.piece_type == chess.QUEEN:
                position_bonus = QUEEN_EVAL_WHITE[sq_index]
            elif piece.piece_type == chess.KING:
                if endgame_phase:
                    position_bonus = KING_EVAL_WHITE_ENDGAME[sq_index]
                else:
                    position_bonus = KING_EVAL_WHITE_MIDDLEGAME[sq_index]

            if piece.color == chess.WHITE:
                score += (value + position_bonus)
            else:
                score -= (value + position_bonus)
    return score


def minimax(board, depth, alpha, beta, maximizing_player, ply_from_root=0):
    global nodes_count, transposition_table
    nodes_count += 1
    check_time()

    if board.is_repetition(2) or board.can_claim_fifty_moves():
        return 0, None

    if board.is_checkmate():
        if board.turn == chess.WHITE:
            return -99999 + ply_from_root, None
        else:
            return 99999 - ply_from_root, None

    if board.is_game_over():
        return 0, None

    # --- РАБОТА С ТАБЛИЦЕЙ ТРАНСПОЗИЦИЙ ---
    zobrist_key = chess.polyglot.zobrist_hash(board)
    tt_entry = transposition_table.get(zobrist_key)
    tt_move = None

    if tt_entry:
        tt_move = tt_entry.get('move')
        if tt_entry['depth'] >= depth:
            tt_flag = tt_entry['flag']
            tt_score = tt_entry['score']

            # Восстанавливаем оценку мата для текущей глубины
            if tt_score > 90000:
                tt_score -= ply_from_root
            elif tt_score < -90000:
                tt_score += ply_from_root

            if tt_flag == TT_EXACT:
                return tt_score, tt_move
            elif tt_flag == TT_LOWERBOUND:
                alpha = max(alpha, tt_score)
            elif tt_flag == TT_UPPERBOUND:
                beta = min(beta, tt_score)

            if alpha >= beta:
                return tt_score, tt_move

    if depth == 0:
        q_score = quiescence_search(board, alpha, beta, maximizing_player)
        return q_score, None

    best_move = None
    ordered_moves = order_moves(board, tt_move=tt_move)
    orig_alpha = alpha

    if maximizing_player:
        max_eval = -float('inf')
        for move in ordered_moves:
            board.push(move)
            evaluation, _ = minimax(board, depth - 1, alpha, beta, False, ply_from_root + 1)
            board.pop()

            if evaluation > max_eval:
                max_eval = evaluation
                best_move = move
            alpha = max(alpha, evaluation)
            if beta <= alpha:
                break

        # Обновление TT с политикой замещения
        if tt_entry is None or depth >= tt_entry['depth']:
            flag = TT_EXACT
            if max_eval <= orig_alpha:
                flag = TT_UPPERBOUND
            elif max_eval >= beta:
                flag = TT_LOWERBOUND

            store_score = max_eval
            if max_eval > 90000:
                store_score += ply_from_root
            elif max_eval < -90000:
                store_score -= ply_from_root

            transposition_table[zobrist_key] = {
                'score': store_score, 'depth': depth, 'flag': flag, 'move': best_move
            }

        return max_eval, best_move
    else:
        min_eval = float('inf')
        for move in ordered_moves:
            board.push(move)
            evaluation, _ = minimax(board, depth - 1, alpha, beta, True, ply_from_root + 1)
            board.pop()

            if evaluation < min_eval:
                min_eval = evaluation
                best_move = move
            beta = min(beta, evaluation)
            if beta <= alpha:
                break

        # Обновление TT с политикой замещения
        if tt_entry is None or depth >= tt_entry['depth']:
            flag = TT_EXACT
            if min_eval <= alpha:
                flag = TT_UPPERBOUND
            elif min_eval >= beta:
                flag = TT_LOWERBOUND

            store_score = min_eval
            if min_eval > 90000:
                store_score += ply_from_root
            elif min_eval < -90000:
                store_score -= ply_from_root

            transposition_table[zobrist_key] = {
                'score': store_score, 'depth': depth, 'flag': flag, 'move': best_move
            }

        return min_eval, best_move


def iterative_deepening_search(board, is_white):
    global search_start_time, time_limit_for_move, nodes_count, transposition_table

    # Предотвращение утечки памяти: если таблица переполнена, чистим
    if len(transposition_table) > MAX_TT_SIZE:
        transposition_table.clear()

    best_move = list(board.legal_moves)[0] if not board.is_game_over() else None
    nodes_count = 0

    try:
        for depth in range(1, 10):
            score, move = minimax(board, depth, -float('inf'), float('inf'), is_white, 0)
            if move:
                best_move = move
                elapsed_ms = int((time.time() - search_start_time) * 1000)
                if elapsed_ms == 0: elapsed_ms = 1

                uci_score = score if is_white else -score

                sys.stdout.write(f"info depth {depth} score cp {uci_score} nodes {nodes_count} time {elapsed_ms}\n")
                sys.stdout.flush()

            if time.time() - search_start_time > time_limit_for_move * 0.5:
                break
    except SearchTimeout:
        pass

    return best_move


def get_book_move(board):
    try:
        with chess.polyglot.open_reader(BOOK_PATH) as reader:
            entry = reader.find(board)
            return entry.move
    except (FileNotFoundError, IndexError):
        return None


def calculate_time_for_move(wtime, btime, is_white):
    time_left = wtime if is_white else btime
    if time_left is None:
        return 1.5
    return (time_left / 1000.0) * 0.04


def main():
    board = chess.Board()
    global search_start_time, time_limit_for_move, transposition_table

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            tokens = line.strip().split()
            if not tokens:
                continue

            command = tokens[0]

            if command == "uci":
                sys.stdout.write("id name PythonMegaBot_v7\n")
                sys.stdout.write("id author Admir\n")
                sys.stdout.write("uciok\n")
                sys.stdout.flush()

            elif command == "isready":
                sys.stdout.write("readyok\n")
                sys.stdout.flush()

            elif command == "ucinewgame":
                board = chess.Board()
                transposition_table.clear()

            elif command == "position":
                if "startpos" in tokens:
                    board = chess.Board()
                    if "moves" in tokens:
                        move_index = tokens.index("moves") + 1
                        for move_str in tokens[move_index:]:
                            board.push_uci(move_str)
                elif "fen" in tokens:
                    fen_index = tokens.index("fen") + 1
                    fen_parts = []
                    for t in tokens[fen_index:]:
                        if t == "moves":
                            break
                        fen_parts.append(t)
                    board = chess.Board(" ".join(fen_parts))
                    if "moves" in tokens:
                        move_index = tokens.index("moves") + 1
                        for move_str in tokens[move_index:]:
                            board.push_uci(move_str)

            elif command == "go":
                wtime = None
                btime = None

                if "wtime" in tokens:
                    wtime = int(tokens[tokens.index("wtime") + 1])
                if "btime" in tokens:
                    btime = int(tokens[tokens.index("btime") + 1])

                is_white = (board.turn == chess.WHITE)

                best_move = get_book_move(board)

                if best_move is None:
                    time_limit_for_move = calculate_time_for_move(wtime, btime, is_white)
                    search_start_time = time.time()

                    best_move = iterative_deepening_search(board, is_white)

                if best_move:
                    sys.stdout.write(f"bestmove {best_move.uci()}\n")
                else:
                    sys.stdout.write("bestmove 0000\n")
                sys.stdout.flush()

            elif command == "quit":
                break

        except Exception as e:
            sys.stderr.write(f"Error: {str(e)}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()