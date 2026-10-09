"""Just enough chess to replay an opening and draw where it ends.

`build_chess.py` needs the position after a line of moves in standard algebraic
notation, and nothing else: no move generation for its own sake, no game end,
no clocks. So this plays SAN moves onto a board and fails loudly on any move it
cannot place, which is the property that matters — a misread move would draw a
plausible wrong board, and nobody would notice.

Kept here rather than taken from python-chess so the builders stay standard
library only, like the engine. It was checked against python-chess once, on
every line of the Lichess opening list (3,865 positions, all equal); see
`datagen/README.md`. A legality check is done only where SAN needs one: when
two pieces of a kind can reach the square and the move does not say which,
the pinned one is not it.
"""
from __future__ import annotations

import re

FILES = "abcdefgh"
START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"

KNIGHT = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
KING = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
ROOK = [(1, 0), (-1, 0), (0, 1), (0, -1)]
BISHOP = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

PIECE_RE = re.compile(r"^([NBRQK])([a-h])?([1-8])?x?([a-h][1-8])$")
PAWN_RE = re.compile(r"^([a-h])(?:x([a-h][1-8])|([1-8]))(?:=?([NBRQ]))?$")

Square = tuple[int, int]  # (file 0-7, rank 0-7)


def square(name: str) -> Square:
    return FILES.index(name[0]), int(name[1]) - 1


def square_name(sq: Square) -> str:
    return f"{FILES[sq[0]]}{sq[1] + 1}"


class Position:
    """A board, the side to move, castling rights and the en passant square.

    Pieces are FEN letters, upper case for White.
    """

    def __init__(self) -> None:
        self.board: dict[Square, str] = {}
        for r, row in enumerate(reversed(START.split("/"))):
            f = 0
            for ch in row:
                if ch.isdigit():
                    f += int(ch)
                else:
                    self.board[(f, r)] = ch
                    f += 1
        self.white = True
        self.castling = set("KQkq")
        self.ep: Square | None = None
        self.last: tuple[Square, Square] | None = None

    def _mine(self, piece: str | None) -> bool:
        return piece is not None and piece.isupper() == self.white

    def _reaches(self, frm: Square, to: Square, kind: str) -> bool:
        """Whether a piece of `kind` on `frm` attacks `to` on this board."""
        df, dr = to[0] - frm[0], to[1] - frm[1]
        if kind == "N":
            return (df, dr) in KNIGHT
        if kind == "K":
            return (df, dr) in KING and (df, dr) != (0, 0)
        dirs = {"R": ROOK, "B": BISHOP, "Q": ROOK + BISHOP}[kind]
        for sf, sr in dirs:
            f, r = frm[0] + sf, frm[1] + sr
            while 0 <= f < 8 and 0 <= r < 8:
                if (f, r) == to:
                    return True
                if (f, r) in self.board:
                    break
                f, r = f + sf, r + sr
        return False

    def _attacked(self, sq: Square, by_white: bool) -> bool:
        for frm, p in self.board.items():
            if p.isupper() != by_white:
                continue
            kind = p.upper()
            if kind == "P":
                step = 1 if by_white else -1
                if sq[1] - frm[1] == step and abs(sq[0] - frm[0]) == 1:
                    return True
            elif self._reaches(frm, sq, kind):
                return True
        return False

    def _leaves_king_safe(self, frm: Square, to: Square) -> bool:
        saved = dict(self.board)
        self.board[to] = self.board.pop(frm)
        king = next(s for s, p in self.board.items() if p == ("K" if self.white else "k"))
        safe = not self._attacked(king, not self.white)
        self.board = saved
        return safe

    def push(self, san: str) -> None:
        """Play one SAN move. Raises ValueError on a move it cannot place."""
        move = san.rstrip("+#!?")
        ep_next: Square | None = None
        rank0 = 0 if self.white else 7
        if move in ("O-O", "O-O-O"):
            side = "K" if move == "O-O" else "Q"
            right = side if self.white else side.lower()
            if right not in self.castling:
                raise ValueError(f"{san}: castling right gone")
            kf, rf, kt, rt = (4, 7, 6, 5) if side == "K" else (4, 0, 2, 3)
            if any((f, rank0) in self.board for f in range(min(kf, rf) + 1, max(kf, rf))):
                raise ValueError(f"{san}: pieces between king and rook")
            if any(self._attacked((f, rank0), not self.white) for f in range(min(kf, kt), max(kf, kt) + 1)):
                raise ValueError(f"{san}: king in or through check")
            king, rook = self.board.pop((kf, rank0)), self.board.pop((rf, rank0))
            if king.upper() != "K" or rook.upper() != "R":
                raise ValueError(f"{san}: king and rook not home")
            self.board[(kt, rank0)], self.board[(rt, rank0)] = king, rook
            frm, to = (kf, rank0), (kt, rank0)
        elif m := PAWN_RE.match(move):
            file_from, capture, push_rank, promo = m.groups()
            pawn = "P" if self.white else "p"
            step = 1 if self.white else -1
            if capture:
                to = square(capture)
                frm = (FILES.index(file_from), to[1] - step)
                if self.board.get(frm) != pawn:
                    raise ValueError(f"{san}: no pawn on {square_name(frm)}")
                if to == self.ep:
                    self.board.pop((to[0], to[1] - step))
                elif not (to in self.board and not self._mine(self.board[to])):
                    raise ValueError(f"{san}: nothing to take")
            else:
                to = (FILES.index(file_from), int(push_rank) - 1)
                if to in self.board:
                    raise ValueError(f"{san}: square taken")
                one = (to[0], to[1] - step)
                if self.board.get(one) == pawn:
                    frm = one
                elif one not in self.board and self.board.get((to[0], to[1] - 2 * step)) == pawn \
                        and to[1] == (3 if self.white else 4):
                    frm = (to[0], to[1] - 2 * step)
                    ep_next = one
                else:
                    raise ValueError(f"{san}: no pawn can get there")
            self.board.pop(frm)
            last_rank = 7 if self.white else 0
            if to[1] == last_rank:
                if not promo:
                    raise ValueError(f"{san}: promotion without a piece")
                pawn = promo if self.white else promo.lower()
            self.board[to] = pawn
        elif m := PIECE_RE.match(move):
            kind, file_hint, rank_hint, target = m.groups()
            to = square(target)
            if self._mine(self.board.get(to)):
                raise ValueError(f"{san}: own piece on {target}")
            letter = kind if self.white else kind.lower()
            cands = [
                s for s, p in self.board.items()
                if p == letter and self._reaches(s, to, kind)
                and (file_hint is None or s[0] == FILES.index(file_hint))
                and (rank_hint is None or s[1] == int(rank_hint) - 1)
            ]
            if len(cands) > 1:
                cands = [s for s in cands if self._leaves_king_safe(s, to)]
            if len(cands) != 1:
                raise ValueError(f"{san}: {len(cands)} pieces can make it")
            frm = cands[0]
            self.board[to] = self.board.pop(frm)
        else:
            raise ValueError(f"{san}: not a move")

        # A king or rook leaving home, or a rook taken at home, ends a right.
        for sq, right in (((4, 0), "KQ"), ((0, 0), "Q"), ((7, 0), "K"),
                          ((4, 7), "kq"), ((0, 7), "q"), ((7, 7), "k")):
            if sq in (frm, to):
                self.castling -= set(right)
        self.ep = ep_next
        self.last = (frm, to)
        self.white = not self.white

    def placement(self) -> str:
        """The board part of a FEN."""
        rows = []
        for r in range(7, -1, -1):
            row, empty = "", 0
            for f in range(8):
                p = self.board.get((f, r))
                if p is None:
                    empty += 1
                    continue
                if empty:
                    row, empty = row + str(empty), 0
                row += p
            rows.append(row + (str(empty) if empty else ""))
        return "/".join(rows)


def moves_of(pgn: str) -> list[str]:
    """'1. e4 c5 2. Nf3' -> ['e4', 'c5', 'Nf3']."""
    return [t for t in pgn.split() if not re.fullmatch(r"\d+\.(\.\.)?", t)]


def play(moves: list[str]) -> Position:
    pos = Position()
    for i, san in enumerate(moves):
        try:
            pos.push(san)
        except ValueError as e:
            raise ValueError(f"move {i + 1} of {' '.join(moves)}: {e}") from None
    return pos
