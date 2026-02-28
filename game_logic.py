"""
大富豪ゲームエンジン
"""

from typing import List, Dict, Optional, Tuple
import random

from models import (
    Card, Suit, GameState, CheatAttempt, AIPersonality,
    CharacterType, PlayerStats, GamePhase, SkillType, RelationshipLevel
)


class DaifugoGame:
    """大富豪ゲーム本体"""

    def __init__(self, num_players: int = 4):
        self.num_players = num_players
        self.players = [f"Player {i + 1}" for i in range(num_players)]
        self.ranks = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']

        # カード管理
        self.player_hands: Dict[str, List[Card]] = {}
        self.discard_pile: List[Card] = []
        self.deck: List[Card] = []

        # ゲーム進行
        self.current_player_idx = 0
        self.game_state = GameState.WAITING_FOR_START
        self.game_phase = GamePhase.DAY_CARD_GAME
        self.last_played_cards: List[Card] = []
        self.last_played_by: Optional[str] = None
        self.pass_count = 0
        self.ranking: List[str] = []

        # ズルシステム
        self.cheat_attempts: List[CheatAttempt] = []
        self.cheat_queue: List[str] = []
        self.skip_next_turn: Dict[str, bool] = {}
        self.caught_players: List[str] = []

        # 関係値・同盟・会話システム
        self.relationships: Dict[str, Dict[str, int]] = {}        # Affinity（好感度）
        self.fear_levels: Dict[str, Dict[str, int]] = {}          # Fear（恐怖度）
        self.alliances: Dict[str, Optional[str]] = {}
        self.conversation_history: Dict[str, List[Dict]] = {}
        self.info_revealed: Dict[str, List[str]] = {}
        self.personalities: Dict[str, AIPersonality] = {}
        self.character_types: Dict[str, CharacterType] = {}
        self.player_stats: Dict[str, PlayerStats] = {}
        self.action_effects: Dict[str, Dict] = {}
        
        # ゲームサイクル
        self.current_cycle = 0
        self.game_log: List[str] = []

    # -----------------------------------------------------------------------
    # ゲーム初期化
    # -----------------------------------------------------------------------

    def initialize_deck(self) -> None:
        self.deck = []
        for suit in Suit:
            for rank in self.ranks:
                self.deck.append(Card(suit, rank))
        random.shuffle(self.deck)

    def deal_cards(self) -> None:
        self.initialize_deck()
        self.player_hands = {player: [] for player in self.players}
        cards_per_player = len(self.deck) // self.num_players
        for i, player in enumerate(self.players):
            self.player_hands[player] = self.deck[i * cards_per_player:(i + 1) * cards_per_player]
            self.player_hands[player].sort(key=lambda c: c.get_rank_value())

    def start_game(self) -> None:
        self.deal_cards()
        # ♠3を持つプレイヤーから開始
        for i, player in enumerate(self.players):
            for card in self.player_hands[player]:
                if card.suit == Suit.SPADE and card.rank == '3':
                    self.current_player_idx = i
                    break
        self.game_state = GameState.PLAYING
        self.discard_pile = []
        self.last_played_cards = []
        self.pass_count = 0
        self.ranking = []
        self.caught_players = []
        self.skip_next_turn = {}
        self.cheat_attempts = []
        self.cheat_queue = []
        self.action_effects = {}
        self._init_relationships()

    # -----------------------------------------------------------------------
    # 手番管理
    # -----------------------------------------------------------------------

    def get_current_player(self) -> str:
        return self.players[self.current_player_idx]

    def get_active_player_count(self) -> int:
        """上がり・バレ済みを除くアクティブプレイヤー数"""
        return sum(1 for p in self.players
                   if p not in self.ranking and p not in self.caught_players)

    def _next_player(self) -> None:
        while True:
            self.current_player_idx = (self.current_player_idx + 1) % self.num_players
            current = self.get_current_player()
            if current in self.ranking or current in self.caught_players:
                continue
            if self.skip_next_turn.pop(current, False):
                continue
            break

    # -----------------------------------------------------------------------
    # カードプレイ
    # -----------------------------------------------------------------------

    def get_valid_moves(self, player: str) -> List[List[Card]]:
        """プレイヤーの有効な手のリストを返す（パスを先頭に含む）"""
        hand = self.player_hands[player]
        valid_moves: List[List[Card]] = [[]]  # パスは常に可能

        if not self.last_played_cards:
            # 場が空：単枚 + 複数同ランク
            for card in hand:
                valid_moves.append([card])
            for rank in self.ranks:
                same_rank = [c for c in hand if c.rank == rank]
                for n in range(2, min(5, len(same_rank) + 1)):
                    valid_moves.append(same_rank[:n])
            return valid_moves

        last_rank_value = self.last_played_cards[0].get_rank_value()
        num_last = len(self.last_played_cards)

        if num_last == 1:
            for card in hand:
                if card.get_rank_value() > last_rank_value:
                    valid_moves.append([card])
        else:
            for rank in self.ranks:
                rank_value = Card.RANK_ORDER.index(rank)
                if rank_value > last_rank_value:
                    same_rank = [c for c in hand if c.rank == rank]
                    if len(same_rank) >= num_last:
                        valid_moves.append(same_rank[:num_last])

        return valid_moves

    def is_valid_move(self, cards: List[Card]) -> bool:
        """カードの組み合わせが有効かチェック"""
        if not cards:
            return True  # パス
        if len(set(c.rank for c in cards)) != 1:
            return False  # 複数ランク混在
        if not self.last_played_cards:
            return True
        if len(cards) != len(self.last_played_cards):
            return False
        return cards[0].get_rank_value() > self.last_played_cards[0].get_rank_value()

    def play_cards(self, player: str, cards: List[Card]) -> bool:
        hand = self.player_hands[player]

        if not cards:
            # パス
            self.pass_count += 1
            if self.pass_count >= self.get_active_player_count() - 1:
                self.last_played_cards = []
                self.last_played_by = None
                self.pass_count = 0
                self._start_cheat_phase()
            else:
                self._next_player()
            return True

        for card in cards:
            if card not in hand:
                return False
        for card in cards:
            hand.remove(card)

        self.discard_pile.extend(cards)
        self.last_played_cards = cards
        self.last_played_by = player
        self.pass_count = 0

        if len(hand) == 0:
            self.ranking.append(player)
            finished = len(set(self.ranking + self.caught_players))
            if finished == self.num_players - 1:
                remaining = next((p for p in self.players
                                  if p not in self.ranking and p not in self.caught_players), None)
                if remaining:
                    self.ranking.append(remaining)
                self.game_state = GameState.GAME_OVER
                return True

        self._next_player()
        return True

    # -----------------------------------------------------------------------
    # ズルシステム
    # -----------------------------------------------------------------------

    def _start_cheat_phase(self) -> None:
        active = [p for p in self.players
                  if p not in self.ranking and p not in self.caught_players]
        if len(active) < 2:
            self._next_player()
            return
        self.action_effects = {}
        self.cheat_queue = list(active)
        self.game_state = GameState.CHEAT_PHASE

    def apply_cheat_effect(self, attacker: str, target: str, effect_type: str) -> str:
        """ズル効果を適用して説明文を返す"""
        # 同盟相手への攻撃は裏切り扱い
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
        """ズルがバレたプレイヤーを最下位に"""
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

    # -----------------------------------------------------------------------
    # 関係値・同盟・会話システム
    # -----------------------------------------------------------------------

    def update_relationship(self, player_a: str, player_b: str, delta: int) -> None:
        """関係値を変更（-100〜+100にクランプ、双方向）"""
        for a, b in [(player_a, player_b), (player_b, player_a)]:
            if a not in self.relationships:
                self.relationships[a] = {}
        current = self.relationships[player_a].get(player_b, 0)
        new_val = max(-100, min(100, current + delta))
        self.relationships[player_a][player_b] = new_val
        self.relationships[player_b][player_a] = new_val

    def propose_alliance(self, proposer: str, target: str) -> bool:
        """同盟を結ぶ（既存の同盟は解消してから）"""
        old_ally = self.alliances.get(proposer)
        if old_ally and old_ally != target:
            self.break_alliance(proposer, old_ally)
        old_ally = self.alliances.get(target)
        if old_ally and old_ally != proposer:
            self.break_alliance(target, old_ally)
        self.alliances[proposer] = target
        self.alliances[target] = proposer
        return True

    def break_alliance(self, player_a: str, player_b: str) -> None:
        if self.alliances.get(player_a) == player_b:
            self.alliances[player_a] = None
        if self.alliances.get(player_b) == player_a:
            self.alliances[player_b] = None

    def add_conversation(self, player_a: str, player_b: str, sender: str,
                         message: str, msg_type: str = "chat") -> None:
        key = f"{min(player_a, player_b)}_{max(player_a, player_b)}"
        if key not in self.conversation_history:
            self.conversation_history[key] = []
        self.conversation_history[key].append({
            "sender": sender,
            "message": message,
            "type": msg_type
        })

    def get_conversation(self, player_a: str, player_b: str) -> List[Dict]:
        key = f"{min(player_a, player_b)}_{max(player_a, player_b)}"
        return self.conversation_history.get(key, [])

    def get_relationship_bonus(self, player_a: str, player_b: str) -> int:
        """関係値に基づくズルボーナス（+1 / 0 / -1）"""
        rel = self.relationships.get(player_a, {}).get(player_b, 0)
        if rel >= 60:
            return 1
        elif rel <= -60:
            return -1
        return 0

    def _init_relationships(self) -> None:
        """ゲーム開始時に全ペアの関係値と恐怖度を初期化"""
        for player in self.players:
            self.relationships[player] = {
                other: 0 for other in self.players if other != player
            }
            self.fear_levels[player] = {
                other: 0 for other in self.players if other != player
            }
            self.alliances[player] = None
            self.info_revealed[player] = []
            
            # キャラクター性を初期化（ランダム割当またはカスタム設定可能）
            if player not in self.character_types:
                self.character_types[player] = random.choice(list(CharacterType))
            
            # ステータスを初期化
            if player not in self.player_stats:
                self.player_stats[player] = PlayerStats()

    # -----------------------------------------------------------------------
    # 情報取得
    # -----------------------------------------------------------------------

    def get_game_info(self) -> Dict:
        return {
            'current_player': self.get_current_player(),
            'player_card_count': {p: len(self.player_hands[p]) for p in self.players},
            'last_played': self.last_played_cards,
            'last_played_by': self.last_played_by,
            'discard_count': len(self.discard_pile),
            'ranking': self.ranking,
            'caught_players': self.caught_players,
            'game_state': self.game_state,
            'game_phase': self.game_phase
        }

    # -----------------------------------------------------------------------
    # 感情マトリクスと心理戦システム
    # -----------------------------------------------------------------------

    def update_fear_level(self, player_a: str, player_b: str, delta: int) -> None:
        """恐怖度を更新（-100〜+100にクランプ、双方向）"""
        for a, b in [(player_a, player_b), (player_b, player_a)]:
            if a not in self.fear_levels:
                self.fear_levels[a] = {}
        current = self.fear_levels[player_a].get(player_b, 0)
        new_val = max(-100, min(100, current + delta))
        self.fear_levels[player_a][player_b] = new_val
        self.fear_levels[player_b][player_a] = new_val

    def get_relationship_level(self, affinity: int) -> RelationshipLevel:
        """関係値をレベルに変換"""
        if affinity <= -60:
            return RelationshipLevel.ENEMY
        elif affinity <= -30:
            return RelationshipLevel.HOSTILE
        elif affinity <= 29:
            return RelationshipLevel.NEUTRAL
        elif affinity <= 59:
            return RelationshipLevel.FRIENDLY
        else:
            return RelationshipLevel.ALLY

    def get_fear_impact(self, feared_player: str, current_player: str) -> float:
        """恐怖度に基づく出力カード選択への影響度（0.5〜1.5）"""
        fear = self.fear_levels.get(current_player, {}).get(feared_player, 0)
        if fear > 60:
            return 0.5  #強気プレイが出せない
        elif fear < -60:
            return 1.5  # 大胆なプレイ
        return 1.0

    def apply_character_type_logic(self, player: str, valid_moves: List[List[Card]]) -> List[Card]:
        """
        キャラクター性に基づいてカード選択。
        各キャラクターが異なる意思決定をする。
        """
        char_type = self.character_types.get(player, CharacterType.LOGICAL)
        relationships = self.relationships.get(player, {})

        if char_type == CharacterType.LOGICAL:
            # 合理型：出来るだけ弱く、効率的に
            return self._logical_move(valid_moves)

        elif char_type == CharacterType.VENGEFUL:
            # 粘着型：嫌いな奴を潰す優先度が最高
            if self.last_played_by:
                hate_level = relationships.get(self.last_played_by, 0)
                if hate_level < -30:
                    # 嫌いな奴にオーバーキル
                    return self._overkill_move(valid_moves)
            return self._aggressive_move(valid_moves)

        elif char_type == CharacterType.SYCOPHANT:
            # 腰巾着型：上位者には逆らわない、下位者を叩く
            if self.last_played_by:
                return self._sycophant_move(player, valid_moves)
            return valid_moves[0]  # パス

        elif char_type == CharacterType.REVOLUTIONARY:
            # 革命家型：秩序を乱す
            return self._disruptive_move(valid_moves)

        return valid_moves[0]

    def _logical_move(self, valid_moves: List[List[Card]]) -> List[Card]:
        """合理型：最も弱いカードを選ぶ"""
        for move in valid_moves:
            if move:  # パスではない
                return move
        return valid_moves[0]

    def _overkill_move(self, valid_moves: List[List[Card]]) -> List[Card]:
        """粘着型オーバーキル：可能な限り最強カードを選ぶ"""
        for move in reversed(valid_moves):
            if move:
                return move
        return valid_moves[0]

    def _aggressive_move(self, valid_moves: List[List[Card]]) -> List[Card]:
        """攻撃的なプレイ"""
        if len(valid_moves) > 1:
            return valid_moves[-2]  # 2番目に強いカード
        return valid_moves[0]

    def _sycophant_move(self, player: str, valid_moves: List[List[Card]]) -> List[Card]:
        """腰巾着型：階級に従う"""
        # 現在のリーダー（場を支配している者）が誰かチェック
        leader = self.last_played_by
        if leader in self.ranking:
            # リーダーが既に上がっている = 新しいリーダーはいない
            return valid_moves[0]

        # リーダーより下位なら避ける
        leader_rank = len([p for p in self.ranking if p != leader])
        player_rank = len([p for p in self.ranking if p != player])

        if leader_rank < player_rank:
            # 下位なので止めない
            return valid_moves[0]
        else:
            # 上位に逆らうな
            return valid_moves[0]

    def _disruptive_move(self, valid_moves: List[List[Card]]) -> List[Card]:
        """革命家型：カオスを引き起こす"""
        # ランダムに動く
        return random.choice(valid_moves)

    def try_skill_intimidate(self, actor: str, target: str) -> Tuple[bool, str]:
        """
        威圧スキル：ターゲットを強制パス
        actor のカリスマ vs target のロジックで判定
        """
        actor_stats = self.player_stats.get(actor, PlayerStats())
        target_stats = self.player_stats.get(target, PlayerStats())
        
        actor_roll = random.randint(1, 20) + actor_stats.charisma * 2
        target_roll = random.randint(1, 20) + target_stats.logic * 2

        success = actor_roll > target_roll
        if success:
            self.skip_next_turn[target] = True
            msg = f"{actor}の威圧により{target}は次のターンをスキップ！"
        else:
            msg = f"{actor}の威圧は{target}に通じなかった"
        
        return success, msg

    def try_skill_charm(self, actor: str, target: str) -> Tuple[bool, str]:
        """
        泣き落としスキル：相手にパスさせる
        actor のかわいげ vs target の好感度で判定
        """
        actor_stats = self.player_stats.get(actor, PlayerStats())
        affinity = self.relationships.get(actor, {}).get(target, 0)
        
        actor_roll = random.randint(1, 20) + actor_stats.charm * 2
        target_roll = random.randint(1, 20) + max(0, affinity // 10)

        success = actor_roll > target_roll
        if success:
            msg = f"{actor}の泣き落としにより{target}はパスした"
        else:
            msg = f"{actor}の泣き落としは{target}に効かなかった"

        return success, msg

    def try_skill_persuade(self, actor: str, target: str, scapegoat: str) -> Tuple[bool, str]:
        """
        扇動スキル：ヘイトを誘導
        actor の演技力 vs target のロジックで判定
        """
        actor_stats = self.player_stats.get(actor, PlayerStats())
        target_stats = self.player_stats.get(target, PlayerStats())
        
        actor_roll = random.randint(1, 20) + actor_stats.acting_power * 2
        target_roll = random.randint(1, 20) + target_stats.logic * 2

        success = actor_roll > target_roll
        if success:
            # scapegoatへの関係値を悪化
            self.update_relationship(target, scapegoat, -15)
            msg = f"{actor}の扇動により{target}は{scapegoat}へのヘイトが上昇した"
        else:
            msg = f"{actor}の扇動は{target}には通じなかった"

        return success, msg

    def get_hierarchy_rank(self, player: str) -> int:
        """
        現在のプレイヤーの階級ランク（昇順）
        0 = 大富豪、num_players-1 = 大貧民
        """
        if player in self.ranking:
            return len(self.ranking) - 1 - self.ranking.index(player)
        # ゲーム中のプレイヤーはカード枚数で推定
        card_count = len(self.player_hands.get(player, []))
        all_counts = sorted(
            [len(self.player_hands.get(p, [])) for p in self.players],
            reverse=True
        )
        return all_counts.index(card_count) if card_count in all_counts else 0

    def log_action(self, action: str) -> None:
        """ゲームログに記録"""
        self.game_log.append(action)
    # -----------------------------------------------------------------------
    # ゲームループ（昼夜サイクル）
    # -----------------------------------------------------------------------

    def advance_game_phase(self) -> None:
        """ゲームフェーズを進行させる"""
        if self.game_phase == GamePhase.DAY_CARD_GAME:
            self.game_phase = GamePhase.EVENING_RESULTS
            self._process_evening_phase()
        elif self.game_phase == GamePhase.EVENING_RESULTS:
            self.game_phase = GamePhase.NIGHT_ADVENTURE
        elif self.game_phase == GamePhase.NIGHT_ADVENTURE:
            # ゲームループの開始（翌日へ）
            self.current_cycle += 1
            self.ranking = []  # リセット
            self.game_phase = GamePhase.DAY_CARD_GAME
            self.deal_cards()
            self._init_relationships()

    def _process_evening_phase(self) -> None:
        """
        夕方フェーズ：順位確定、ステータス付与、ペナルティ適用
        大富豪：ステータスバフ
        大貧民：HP減少などのペナルティ
        """
        if not self.ranking:
            return

        # 大富豪：最高カード、最高ステータス
        daifugo = self.ranking[0]
        self.log_action(f"🤴 {daifugo}が大富豪に昇格! ステータスバフを得た")
        stats = self.player_stats.get(daifugo, PlayerStats())
        stats.charisma += 2
        stats.experience += 20

        # 大貧民：ペナルティ
        if len(self.ranking) > 1:
            hinmin = self.ranking[-1]
            self.log_action(f"😢 {hinmin}が大貧民に転落. HPが低下")
            hinmin_stats = self.player_stats.get(hinmin, PlayerStats())
            hinmin_stats.hp -= 10
            hinmin_stats.experience += 10

        # 中位：普通の経験値
        for rank, player in enumerate(self.ranking[1:-1], 2):
            player_stats = self.player_stats.get(player, PlayerStats())
            player_stats.experience += 15

    def grant_evening_rewards(self) -> Dict[str, Dict]:
        """夕方に各プレイヤーに報酬を付与（経験値・HP回復など）"""
        rewards = {}
        for player in self.players:
            reward = {"exp": 5, "hp_recovery": 2, "money": 10}

            # 順位による追加報酬
            if player in self.ranking:
                rank = self.ranking.index(player)
                if rank == 0:  # 大富豪
                    reward["exp"] += 25
                    reward["charisma_bonus"] = 1
                elif rank == len(self.ranking) - 1:  # 大貧民
                    reward["exp"] += 5
                    reward["penalty"] = -5
                else:  # 中位
                    reward["exp"] += 15

            rewards[player] = reward
        return rewards

    # -----------------------------------------------------------------------
    # 育成システム
    # -----------------------------------------------------------------------

    def gain_experience(self, player: str, amount: int) -> Tuple[bool, int]:
        """
        プレイヤーに経験値を付与。レベルアップ時はTrue を返す。
        
        Returns:
            (レベルアップしたか, 次のレベル)
        """
        stats = self.player_stats.get(player, PlayerStats())
        stats.experience += amount
        old_level = stats.level
        
        # 経験値テーブル（単純な累積式）
        exp_required = old_level * 50
        if stats.experience >= exp_required:
            stats.level += 1
            stats.experience -= exp_required
            return True, stats.level
        return False, old_level

    def level_up(self, player: str) -> None:
        """プレイヤーをレベルアップさせ、ステータスを上昇させる"""
        stats = self.player_stats.get(player, PlayerStats())
        stats.level += 1
        stats.max_hp += 10
        stats.hp = stats.max_hp
        
        # ランダムにステータスボーナス
        stat_choices = ["charisma", "charm", "logic", "acting_power", "intuition"]
        for _ in range(2):
            stat_to_boost = random.choice(stat_choices)
            setattr(stats, stat_to_boost, getattr(stats, stat_to_boost) + 1)
        
        self.log_action(f"{player} がレベル {stats.level}にアップ!")

    def heal_player(self, player: str, amount: int = None) -> None:
        """プレイヤーのHPを回復"""
        stats = self.player_stats.get(player, PlayerStats())
        if amount is None:
            amount = stats.max_hp
        stats.hp = min(stats.max_hp, stats.hp + amount)

    def damage_player(self, player: str, amount: int) -> None:
        """プレイヤーにダメージを与える"""
        stats = self.player_stats.get(player, PlayerStats())
        stats.hp = max(0, stats.hp - amount)
        if stats.hp <= 0:
            self.log_action(f"💥 {player}は力尽きた...")

    # -----------------------------------------------------------------------
    # 夜（アドベンチャー）フェーズ
    # -----------------------------------------------------------------------

    def night_phase_talk_to_npc(self, player: str, target_npc: str, message: str) -> str:
        """
        夜フェーズ：NPCと会話
        好感度の変動、密約、情報交換などが起きる。
        """
        current_rel = self.relationships.get(player, {}).get(target_npc, 0)

        # Mistral AIで応答を生成（ai_player.pyから）
        # ここは簡易版（実装では ai_player.py の generate_chat_response を呼ぶ）
        
        response = f"{target_npc}: {message}には返答しません（詳細は会話フェーズで）"

        # 好感度変動（簡易ロジック）
        if "同盟" in message or "協力" in message:
            self.update_relationship(player, target_npc, 10)
        elif "妨害" in message or "攻撃" in message:
            self.update_relationship(player, target_npc, -10)

        self.add_conversation(player, target_npc, player, message, "talk")
        return response

    def night_phase_propose_alliance(self, proposer: str, target: str, reason: str) -> bool:
        """夜フェーズ：同盟を提案"""
        # 提案相手の好感度が高いほど成功しやすい
        affinity = self.relationships.get(proposer, {}).get(target, 0)
        success_chance = max(0.0, min(1.0, (affinity + 50) / 100))

        if random.random() < success_chance:
            self.propose_alliance(proposer, target)
            self.log_action(f"🔗 {proposer}と{target}が同盟を結んだ")
            self.add_conversation(proposer, target, proposer, f"同盟しませんか？ {reason}", "alliance")
            return True
        else:
            self.log_action(f"❌ {proposer}の同盟提案を{target}が拒否した")
            return False

    def night_phase_betray_alliance(self, player: str, ally: str, new_ally: str) -> None:
        """夜フェーズ：同盟相手を裏切る"""
        self.break_alliance(player, ally)
        self.update_relationship(player, ally, -30)  # 大幅な信頼低下
        self.log_action(f"💔 {player}が{ally}を裏切り、{new_ally}と新たな同盟を結んだ")
        self.add_conversation(player, ally, player, f"お別れだ。{new_ally}と組むことにしたんだ。", "betray")

    def get_card_exchange_result(self, winner: str, loser: str) -> Tuple[List[Card], List[Card]]:
        """
        カード交換計算（大富豪フェーズ）
        winner が最強カード2枚をもらい、loser に返すカードを決定。
        好感度や Charm に基づいて、返却カードが変わる。
        """
        winner_stats = self.player_stats.get(winner, PlayerStats())
        loser_stats = self.player_stats.get(loser, PlayerStats())
        affinity = self.relationships.get(winner, {}).get(loser, 0)

        winner_hand = self.player_hands.get(winner, [])
        loser_hand = self.player_hands.get(loser, [])

        if not loser_hand:
            return [], []

        # 大富豪が loser の最強2枚を回収
        sorted_hand = sorted(loser_hand, key=lambda c: c.get_rank_value(), reverse=True)
        cards_to_give = sorted_hand[:2]

        # 返却カード決定
        if affinity > 40 and loser_stats.charm > 2:
            # loser が「かわいげ」高い & 好感度高い = 大富豪が強力カード返す（恩赦）
            return_cards = sorted(winner_hand, key=lambda c: c.get_rank_value(), reverse=True)[:2]
        else:
            # 通常：弱いカード返す
            return_cards = sorted(winner_hand, key=lambda c: c.get_rank_value())[:2]

        return cards_to_give, return_cards

    def apply_hierarchy_change(self) -> None:
        """階級変化に伴うRPG的ステータス変動"""
        for player in self.players:
            rank = self.get_hierarchy_rank(player)
            stats = self.player_stats.get(player, PlayerStats())

            # 階級が高いほど Charisma ボーナス
            stats.charisma = 1 + rank

    # -----------------------------------------------------------------------
    # ゲーム状態の整合チェック
    # -----------------------------------------------------------------------

    def check_game_end_condition(self) -> bool:
        """ゲーム終了条件をチェック"""
        # 誰かのHP が 0 以下か
        for player in self.players:
            stats = self.player_stats.get(player, PlayerStats())
            if stats.hp <= 0:
                self.log_action(f"💀 {player}は力尽きた")
                return True

        # サイクルが一定数を超えたか
        if self.current_cycle >= 5:
            self.log_action(f"📊 {self.current_cycle}サイクルが終了しました")
            return True

        return False

    def get_final_ranking(self) -> List[Tuple[str, int]]:
        """最終順位（ゲーム終了後）"""
        final_ranking = []
        for player in self.players:
            stats = self.player_stats.get(player, PlayerStats())
            wins = len([r for r in self.ranking if r == player])
            final_ranking.append((player, stats.level, stats.experience, wins))

        return sorted(final_ranking, key=lambda x: (x[1], x[2], x[3], ), reverse=True)