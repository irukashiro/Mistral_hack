"""
大富豪ゲームのルールと基本的なゲームロジック
"""

from enum import Enum
from typing import List, Dict, Optional, Tuple
import random

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
        return self.rank == other.rank
    
    def get_rank_value(self) -> int:
        """ランクの数値を返す（大きいほど強い）"""
        return self.RANK_ORDER.index(self.rank)

class GameState(Enum):
    """ゲームの状態"""
    WAITING_FOR_START = "waiting"
    PLAYING = "playing"
    ROUND_OVER = "round_over"
    GAME_OVER = "game_over"

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
    
    def play_cards(self, player: str, cards: List[Card]) -> bool:
        """カードをプレイする"""
        hand = self.player_hands[player]
        
        # パスの場合
        if not cards:
            self.pass_count += 1
            if self.pass_count >= self.num_players - 1:
                # 誰も出せないので場をリセット
                self.last_played_cards = []
                self.pass_count = 0
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
            if len(self.ranking) == self.num_players - 1:
                # 最後の1人がゲーム終了
                remaining_player = None
                for p in self.players:
                    if p not in self.ranking:
                        remaining_player = p
                        break
                self.ranking.append(remaining_player)
                self.game_state = GameState.GAME_OVER
                return True
        
        self._next_player()
        return True
    
    def _next_player(self) -> None:
        """次のプレイヤーに移る"""
        # ゲーム終了済みのプレイヤーをスキップ
        while True:
            self.current_player_idx = (self.current_player_idx + 1) % self.num_players
            if self.get_current_player() not in self.ranking:
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
            'game_state': self.game_state
        }
