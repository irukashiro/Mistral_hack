"""
大富豪ゲームのデータモデル定義
"""

from dataclasses import dataclass
from enum import Enum
from typing import List
import random


class Suit(Enum):
    """カードのスート"""
    SPADE = "♠"
    HEART = "♥"
    DIAMOND = "♦"
    CLUB = "♣"


class Card:
    """トランプカード"""
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
    """ズル試行の記録"""
    attacker: str
    target: str
    cheat_prompt: str
    counter_prompt: str = ""
    cheat_bonus: int = 0
    counter_bonus: int = 0
    cheat_roll: int = 0
    counter_roll: int = 0
    success: bool = False
    effect_type: str = ""   # "peek" | "swap" | "skip" | "extra_cards"
    caught: bool = False


@dataclass
class AIPersonality:
    """AIプレイヤーのキャラクター設定"""
    player_name: str
    character_name: str        # キャラ名（例: "謎の田中"）
    personality_desc: str      # 性格説明（日本語2〜3文）
    speech_style: str          # 話し方（丁寧語/友達口調/謎めいた等）
    cheat_tendency: float      # ズル傾向 0.0〜1.0
    cooperation_tendency: float
    honesty: float             # 正直度（低いほど情報を偽る）
    aggression: float
    backstory: str             # 一言プロフィール

class CharacterType(Enum):
    """NPCの性格タイプ（プレイスタイル）"""
    LOGICAL = "logical"        # 合理型：私情を挟まず効率重視
    VENGEFUL = "vengeful"      # 粘着型：嫌いな相手へのヘイト優先
    SYCOPHANT = "sycophant"    # 腰巾着型：上位者に従順、下位者を叩く
    REVOLUTIONARY = "revolutionary"  # 革命家型：秩序を乱すことを好む


class GamePhase(Enum):
    """ゲームサイクルのフェーズ"""
    DAY_CARD_GAME = "day_card_game"      # 昼：大富豪カードゲーム
    EVENING_RESULTS = "evening_results"  # 夕方：順位発表・階級決定
    NIGHT_ADVENTURE = "night_adventure"  # 夜：工作フェーズ・会話


class SkillType(Enum):
    """スキル種別"""
    INTIMIDATE = "intimidate"      # 威圧：相手を強制パス
    CHARM = "charm"                # 泣き落とし：好感度ボーナス
    PERSUADE = "persuade"          # 扇動：ヘイト誘導
    BLUFF = "bluff"                # ブラフ：カードの強さを偽る
    OBSERVE = "observe"            # 観察：相手の情報を得る


@dataclass
class PlayerStats:
    """プレイヤーのステータス（RPG的属性）"""
    charisma: int = 1              # カリスマ：威圧・扇動の効果
    charm: int = 1                 # かわいげ：泣き落としの効果
    logic: int = 1                 # ロジック：威圧に対する耐性
    acting_power: int = 1          # 演技力：ブラフの効果
    intuition: int = 1             # 直感：相手の情報読取
    max_hp: int = 100
    hp: int = 100
    level: int = 1
    experience: int = 0


@dataclass
class Skill:
    """スキル定義"""
    name: str
    skill_type: SkillType
    power: int                      # スキルの基本威力
    requirement: Dict[str, int]     # \"charisma\": 3 などのステータス要件
    cooldown: int = 0               # ターン数のクールダウン


@dataclass
class Episode:
    """アドベンチャーイベント"""
    title: str
    description: str
    required_rank: str              # "daifugo" | "normal" | "hinmin"
    npc_names: List[str]            # 登場NPCリスト
    choices: List[Dict[str, str]]   # {\"text\": \"選択肢\", \"effect\": \"効果\"} のリスト
    reward_exp: int = 10
    reward_money: int = 0


class RelationshipLevel(Enum):
    """関係度のレベル（表示用）"""
    ENEMY = "enemy"           # 敵対関係（-100〜-60）
    HOSTILE = "hostile"       # 不信（-59〜-30）
    NEUTRAL = "neutral"       # 中立（-29〜29）
    FRIENDLY = "friendly"     # 友好（30〜59）
    ALLY = "ally"             # 同盟・信頼（60〜100）