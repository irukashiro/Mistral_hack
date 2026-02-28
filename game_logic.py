"""
大富豪ゲームのルールと基本的なゲームロジック
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple
import random


@dataclass
class AIPersonality:
    player_name: str
    character_name: str        # キャラ名（例: "謎の田中"）
    personality_desc: str      # 性格説明（日本語2〜3文）
    speech_style: str          # 話し方（丁寧語/友達口調/謎めいた等）
    cheat_tendency: float      # ズル傾向 0.0〜1.0
    cooperation_tendency: float
    honesty: float             # 正直度（低いほど情報を偽る）
    aggression: float
    backstory: str             # 一言プロフィール

class Suit(Enum):
    """カードのスート"""
    SPADE = "♠"
    HEART = "♥"
    DIAMOND = "♦"
    CLUB = "♣"

class Card:
    """カードクラス"""
    RANK_ORDER = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']

    def __init__(self, suit: Suit, rank: str):
        self.suit = suit
        self.rank = rank

    def __repr__(self) -> str:
        return f"{self.suit.value}{self.rank}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Card):
            return False
        return self.suit == other.suit and self.rank == other.rank

    def __hash__(self) -> int:
        return hash((self.suit, self.rank))

    def get_rank_value(self) -> int:
        """ランクの数値を返す（大きいほど強い）"""
        return self.RANK_ORDER.index(self.rank)

class GameState(Enum):
    """ゲームの状態"""
    WAITING_FOR_START = "waiting"
    PLAYING = "playing"
    CHEAT_PHASE = "cheat_phase"
    ROUND_OVER = "round_over"
    GAME_OVER = "game_over"


@dataclass
class CheatAttempt:
    attacker: str
    target: str
    cheat_prompt: str
    counter_prompt: str = ""
    cheat_bonus: int = 0
    counter_bonus: int = 0
    cheat_roll: int = 0
    counter_roll: int = 0
    success: bool = False
    effect_type: str = ""   # "peek"|"swap"|"skip"|"extra_cards"
    caught: bool = False


class DaifugoGame:
    """大富豪ゲーム"""

    def __init__(self, num_players: int = 4):
        self.num_players = num_players
        self.players = [f"Player {i + 1}" for i in range(num_players)]
        self.player_hands: Dict[str, List[Card]] = {}
        self.discard_pile: List[Card] = []
        self.deck: List[Card] = []
        self.current_player_idx = 0
        self.game_state = GameState.WAITING_FOR_START
        self.ranks = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
        self.last_played_cards: List[Card] = []
        self.last_played_by = None
        self.pass_count = 0
        self.ranking = []  # ゲーム終了時の順位
        self.cheat_attempts: List[CheatAttempt] = []
        self.cheat_queue: List[str] = []
        self.skip_next_turn: Dict[str, bool] = {}
        self.caught_players: List[str] = []
        # 関係値/同盟/会話システム
        self.relationships: Dict[str, Dict[str, int]] = {}
        self.alliances: Dict[str, Optional[str]] = {}
        self.conversation_history: Dict[str, List[Dict]] = {}
        self.info_revealed: Dict[str, List[str]] = {}
        self.personalities: Dict[str, 'AIPersonality'] = {}
        self.action_effects: Dict[str, Dict] = {}

    def initialize_deck(self) -> None:
        """デッキを初期化する"""
        self.deck = []
        for suit in Suit:
            for rank in self.ranks:
                self.deck.append(Card(suit, rank))
        random.shuffle(self.deck)

    def deal_cards(self) -> None:
        """全プレイヤーにカードを配る"""
        self.initialize_deck()
        self.player_hands = {player: [] for player in self.players}

        for i, player in enumerate(self.players):
            # 各プレイヤーに均等にカードを配る
            cards_per_player = len(self.deck) // self.num_players
            self.player_hands[player] = self.deck[i * cards_per_player:(i + 1) * cards_per_player]
            self.player_hands[player].sort(key=lambda c: c.get_rank_value())

    def start_game(self) -> None:
        """ゲームを開始する"""
        self.deal_cards()
        # 3のスペードを持っているプレイヤーから開始
        for i, player in enumerate(self.players):
            for card in self.player_hands[player]:
                if card.suit == Suit.SPADE and card.rank == '3':
                    self.current_player_idx = i
                    break
        self.game_state = GameState.PLAYING
        self.discard_pile = []
        self.last_played_cards = []
        self.pass_count = 0
        self.caught_players = []
        self.skip_next_turn = {}
        self.cheat_attempts = []
        self.cheat_queue = []
        self.action_effects = {}
        self._init_relationships()

    def get_current_player(self) -> str:
        """現在のプレイヤーを取得"""
        return self.players[self.current_player_idx]

    def get_valid_moves(self, player: str) -> List[List[Card]]:
        """プレイヤーの有効なカード出し（複数枚対応）を取得"""
        hand = self.player_hands[player]
        valid_moves = []

        # パスは常に可能
        valid_moves.append([])

        # 最初のプレイ
        if not self.last_played_cards:
            # 単枚
            for card in hand:
                valid_moves.append([card])
            # 複数枚同じランク
            for rank in self.ranks:
                cards_with_rank = [c for c in hand if c.rank == rank]
                if len(cards_with_rank) >= 2:
                    valid_moves.append(cards_with_rank[:2])
                    if len(cards_with_rank) >= 3:
                        valid_moves.append(cards_with_rank[:3])
                    if len(cards_with_rank) >= 4:
                        valid_moves.append(cards_with_rank[:4])
            return valid_moves

        # 前回のカードを上回るカードが必要
        last_card = self.last_played_cards[0]
        last_rank_value = last_card.get_rank_value()

        # 同じ枚数のカードをプレイ
        if len(self.last_played_cards) == 1:
            # 単枚の場合
            for card in hand:
                if card.get_rank_value() > last_rank_value:
                    valid_moves.append([card])
        else:
            # 複数枚の場合は同じランクで上回るランク
            for rank in self.ranks:
                rank_value = Card.RANK_ORDER.index(rank)
                if rank_value > last_rank_value:
                    cards_with_rank = [c for c in hand if c.rank == rank]
                    if len(cards_with_rank) >= len(self.last_played_cards):
                        valid_moves.append(cards_with_rank[:len(self.last_played_cards)])

        return valid_moves

    def get_active_player_count(self) -> int:
        """上がっていない・捕まっていないプレイヤーの数を返す"""
        return sum(1 for p in self.players
                   if p not in self.ranking and p not in self.caught_players)

    def is_valid_move(self, cards: List[Card]) -> bool:
        """カードの出し方が有効かチェック（特定のカードインスタンスに依存しない）"""
        if not cards:
            return True  # パスは常に有効

        # 全カードが同じランクか確認
        if len(set(c.rank for c in cards)) != 1:
            return False

        # 最初のプレイ（場が空）
        if not self.last_played_cards:
            return True

        # 同じ枚数か
        if len(cards) != len(self.last_played_cards):
            return False

        # 前のカードより強いか
        return cards[0].get_rank_value() > self.last_played_cards[0].get_rank_value()

    def play_cards(self, player: str, cards: List[Card]) -> bool:
        """カードをプレイする"""
        hand = self.player_hands[player]

        # パスの場合
        if not cards:
            self.pass_count += 1
            if self.pass_count >= self.get_active_player_count() - 1:
                # 残りアクティブプレイヤー全員がパスしたので場をリセット
                self.last_played_cards = []
                self.last_played_by = None
                self.pass_count = 0
                self._start_cheat_phase()
                return True
            self._next_player()
            return True

        # 有効なカードかチェック
        for card in cards:
            if card not in hand:
                return False

        # カードを手から削除
        for card in cards:
            hand.remove(card)

        # 場にカードを出す
        self.discard_pile.extend(cards)
        self.last_played_cards = cards
        self.last_played_by = player
        self.pass_count = 0

        # プレイヤーが上がったかチェック
        if len(hand) == 0:
            self.ranking.append(player)
            finished_count = len(set(self.ranking + self.caught_players))
            if finished_count == self.num_players - 1:
                remaining = next((p for p in self.players
                                  if p not in self.ranking and p not in self.caught_players), None)
                if remaining:
                    self.ranking.append(remaining)
                self.game_state = GameState.GAME_OVER
                return True

        self._next_player()
        return True

    def _start_cheat_phase(self) -> None:
        """ズルフェーズを開始する"""
        active = [p for p in self.players
                  if p not in self.ranking and p not in self.caught_players]
        if len(active) < 2:
            self._next_player()
            return
        self.action_effects = {}  # 新ラウンドのアクション効果をリセット
        self.cheat_queue = list(active)
        self.game_state = GameState.CHEAT_PHASE

    def apply_cheat_effect(self, attacker: str, target: str, effect_type: str) -> str:
        """ズル効果を適用する"""
        # 同盟相手への攻撃: 関係値-20（裏切り）& 同盟解消
        if self.alliances.get(attacker) == target:
            self.update_relationship(attacker, target, -20)
            self.break_alliance(attacker, target)
        if effect_type == "peek":
            return f"{attacker}が{target}の手札を覗いた"
        elif effect_type == "swap":
            if self.player_hands[attacker] and self.player_hands[target]:
                a_card = random.choice(self.player_hands[attacker])
                t_card = random.choice(self.player_hands[target])
                self.player_hands[attacker].remove(a_card)
                self.player_hands[target].remove(t_card)
                self.player_hands[attacker].append(t_card)
                self.player_hands[target].append(a_card)
                return f"{attacker}と{target}のカードを1枚交換した"
            return "交換するカードがなかった"
        elif effect_type == "skip":
            self.skip_next_turn[target] = True
            return f"{target}の次のターンをスキップ"
        elif effect_type == "extra_cards":
            if len(self.discard_pile) >= 2:
                cards_to_add = self.discard_pile[-2:]
                self.discard_pile = self.discard_pile[:-2]
                self.player_hands[target].extend(cards_to_add)
                return f"{target}に2枚カードを追加"
            elif self.discard_pile:
                card = self.discard_pile.pop()
                self.player_hands[target].append(card)
                return f"{target}に1枚カードを追加"
            return f"{target}にカードを追加できなかった（場なし）"
        return ""

    def catch_cheater(self, player: str) -> None:
        """ズルがバレたプレイヤーを処理する"""
        if player not in self.caught_players:
            self.caught_players.append(player)
        if player not in self.ranking:
            self.ranking.append(player)
        active = [p for p in self.players
                  if p not in self.ranking and p not in self.caught_players]
        if len(active) <= 1:
            if active:
                self.ranking.insert(0, active[0])
            self.game_state = GameState.GAME_OVER

    def update_relationship(self, player_a: str, player_b: str, delta: int) -> None:
        """関係値を変更（-100〜+100にクランプ）"""
        if player_a not in self.relationships:
            self.relationships[player_a] = {}
        if player_b not in self.relationships:
            self.relationships[player_b] = {}
        current_ab = self.relationships[player_a].get(player_b, 0)
        new_val = max(-100, min(100, current_ab + delta))
        self.relationships[player_a][player_b] = new_val
        self.relationships[player_b][player_a] = new_val

    def propose_alliance(self, proposer: str, target: str) -> bool:
        """同盟を結ぶ（双方）"""
        # 既存の同盟を解消してから新たに結ぶ
        old_proposer_ally = self.alliances.get(proposer)
        if old_proposer_ally and old_proposer_ally != target:
            self.break_alliance(proposer, old_proposer_ally)
        old_target_ally = self.alliances.get(target)
        if old_target_ally and old_target_ally != proposer:
            self.break_alliance(target, old_target_ally)
        self.alliances[proposer] = target
        self.alliances[target] = proposer
        return True

    def break_alliance(self, player_a: str, player_b: str) -> None:
        """同盟解消"""
        if self.alliances.get(player_a) == player_b:
            self.alliances[player_a] = None
        if self.alliances.get(player_b) == player_a:
            self.alliances[player_b] = None

    def add_conversation(self, player_a: str, player_b: str, sender: str,
                         message: str, msg_type: str = "chat") -> None:
        """会話履歴に追加"""
        key = f"{min(player_a, player_b)}_{max(player_a, player_b)}"
        if key not in self.conversation_history:
            self.conversation_history[key] = []
        self.conversation_history[key].append({
            "sender": sender,
            "message": message,
            "type": msg_type
        })

    def get_relationship_bonus(self, player_a: str, player_b: str) -> int:
        """関係値によるズルボーナスを返す（+1/-1 等）"""
        rel = self.relationships.get(player_a, {}).get(player_b, 0)
        if rel >= 60:
            return 1   # 友好的な相手へはボーナス
        elif rel <= -60:
            return -1  # 敵対的な相手にはペナルティ
        return 0

    def get_conversation(self, player_a: str, player_b: str) -> List[Dict]:
        """2人の会話履歴を取得"""
        key = f"{min(player_a, player_b)}_{max(player_a, player_b)}"
        return self.conversation_history.get(key, [])

    def _init_relationships(self) -> None:
        """全プレイヤーペアの関係値を0で初期化"""
        for player in self.players:
            self.relationships[player] = {}
            self.alliances[player] = None
            self.info_revealed[player] = []
            for other in self.players:
                if other != player:
                    self.relationships[player][other] = 0

    def _next_player(self) -> None:
        """次のプレイヤーに移る"""
        while True:
            self.current_player_idx = (self.current_player_idx + 1) % self.num_players
            current = self.get_current_player()
            if current in self.ranking or current in self.caught_players:
                continue
            if self.skip_next_turn.pop(current, False):
                continue
            break

    def get_game_info(self) -> Dict:
        """ゲーム情報を取得"""
        return {
            'current_player': self.get_current_player(),
            'player_card_count': {p: len(self.player_hands[p]) for p in self.players},
            'last_played': self.last_played_cards,
            'last_played_by': self.last_played_by,
            'discard_count': len(self.discard_pile),
            'ranking': self.ranking,
            'caught_players': self.caught_players,
            'game_state': self.game_state
        }
