"""
Mistral AIを使った大富豪のAIプレイヤー
"""

import json
import random
import re
from typing import List, Optional, Dict
from game_logic import Card, DaifugoGame, AIPersonality
import os
from mistralai import Mistral

# フォールバック用のデフォルト個性定義
_DEFAULT_PERSONALITIES = [
    {
        "character_name": "謎の田中",
        "personality_desc": "何を考えているか分からない謎めいたプレイヤー。笑顔の裏に策略を隠す。いつも一歩引いて状況を観察している。",
        "speech_style": "謎めいた口調。意味深な一言が多い。",
        "cheat_tendency": 0.6,
        "cooperation_tendency": 0.3,
        "honesty": 0.2,
        "aggression": 0.5,
        "backstory": "元ポーカープレイヤー。表情から何も読み取れない。"
    },
    {
        "character_name": "陽気な佐藤",
        "personality_desc": "明るくてフレンドリーな性格。友達を作るのが得意だが、いざとなれば容赦ない。",
        "speech_style": "友達口調。「〜じゃん」「〜だよね！」が口癖。",
        "cheat_tendency": 0.3,
        "cooperation_tendency": 0.8,
        "honesty": 0.7,
        "aggression": 0.3,
        "backstory": "カードゲーム大会の常連。友達100人作るのが夢。"
    },
    {
        "character_name": "冷静な鈴木",
        "personality_desc": "論理的で計算高い分析型プレイヤー。感情を表に出さず、確率で全てを判断する。",
        "speech_style": "丁寧語。「〜と判断します」「確率的に〜」が口癖。",
        "cheat_tendency": 0.4,
        "cooperation_tendency": 0.5,
        "honesty": 0.6,
        "aggression": 0.6,
        "backstory": "数学科卒。全ての手を計算してから動く。"
    },
]


class MistralAIPlayer:
    """Mistral AIを使ったプレイヤー"""

    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            api_key = os.getenv("MISTRAL_API_KEY")

        if not api_key:
            raise ValueError("MISTRAL_API_KEYが設定されていません")

        self.client = Mistral(api_key=api_key)
        self.model = "mistral-small-latest"

    # -----------------------------------------------------------------------
    # 個性生成
    # -----------------------------------------------------------------------

    def generate_personality(self, player_name: str) -> AIPersonality:
        """Mistral に個性 JSON を生成させる。失敗時はフォールバック。"""
        try:
            prompt = f"""大富豪カードゲームのAIプレイヤー「{player_name}」のキャラクター設定を作ってください。

以下のJSONのみを返してください（他の文字は一切含めないこと）:
{{
  "character_name": "キャラ名（日本語2〜4文字）",
  "personality_desc": "性格説明（日本語2〜3文）",
  "speech_style": "話し方の特徴（丁寧語/友達口調/謎めいた等、日本語1文）",
  "cheat_tendency": 0.0から1.0の数値,
  "cooperation_tendency": 0.0から1.0の数値,
  "honesty": 0.0から1.0の数値,
  "aggression": 0.0から1.0の数値,
  "backstory": "一言プロフィール（日本語1文）"
}}"""
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=1.0,
                max_tokens=300
            )
            content = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return AIPersonality(
                    player_name=player_name,
                    character_name=data.get("character_name", player_name),
                    personality_desc=data.get("personality_desc", ""),
                    speech_style=data.get("speech_style", "普通の口調"),
                    cheat_tendency=float(data.get("cheat_tendency", 0.3)),
                    cooperation_tendency=float(data.get("cooperation_tendency", 0.5)),
                    honesty=float(data.get("honesty", 0.5)),
                    aggression=float(data.get("aggression", 0.5)),
                    backstory=data.get("backstory", "")
                )
        except Exception as e:
            print(f"generate_personality error: {e}")

        # フォールバック: インデックスでデフォルト個性を選択
        player_num = int(player_name.replace("Player ", "")) - 2  # Player 2 → 0
        defaults = _DEFAULT_PERSONALITIES
        d = defaults[player_num % len(defaults)]
        return AIPersonality(
            player_name=player_name,
            character_name=d["character_name"],
            personality_desc=d["personality_desc"],
            speech_style=d["speech_style"],
            cheat_tendency=d["cheat_tendency"],
            cooperation_tendency=d["cooperation_tendency"],
            honesty=d["honesty"],
            aggression=d["aggression"],
            backstory=d["backstory"]
        )

    # -----------------------------------------------------------------------
    # チャット応答生成
    # -----------------------------------------------------------------------

    def generate_chat_response(self, message: str, sender: str,
                               target_personality: AIPersonality,
                               context: dict) -> str:
        """AIキャラクターとしてチャットに返答する"""
        p = target_personality
        system_prompt = (
            f"あなたは大富豪ゲームをプレイしている「{p.character_name}」です。\n"
            f"性格: {p.personality_desc}\n"
            f"話し方: {p.speech_style}\n"
            f"プロフィール: {p.backstory}\n"
        )
        if p.honesty < 0.4:
            system_prompt += "あなたは戦略を隠す傾向があります。本音は明かさず、相手を惑わすような返答をしてください。\n"
        if p.cooperation_tendency > 0.7:
            system_prompt += "あなたは協力的な姿勢を見せやすいです。\n"

        relationship_val = context.get("relationship", 0)
        if relationship_val < -30:
            system_prompt += "この相手とは関係が悪いので、やや警戒した返答をしてください。\n"
        elif relationship_val > 30:
            system_prompt += "この相手とは仲が良いので、フレンドリーに返してください。\n"

        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{sender}より: {message}"}
                ],
                temperature=0.9,
                max_tokens=100
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"generate_chat_response error: {e}")
            return "...（無言）"

    # -----------------------------------------------------------------------
    # 観察ヒント生成
    # -----------------------------------------------------------------------

    def generate_observation(self, target: str, personality: AIPersonality,
                             game_info: dict) -> str:
        """observeアクションでターゲットに関するヒントを返す"""
        card_count = game_info.get("player_card_count", {}).get(target, "不明")

        # honesty が低い場合は嘘の情報を交えることがある
        is_honest = personality.honesty > 0.5 or random.random() < personality.honesty
        try:
            if is_honest:
                prompt = (
                    f"大富豪ゲームで{target}を観察しています。"
                    f"{target}は現在{card_count}枚の手札を持っています。"
                    f"{target}の個性: {personality.personality_desc}\n"
                    f"戦略的な観察ヒントを日本語1文（40字以内）で返してください。"
                )
            else:
                prompt = (
                    f"大富豪ゲームで{target}を観察したふりをしています。"
                    f"相手を惑わすような嘘のヒントを日本語1文（40字以内）で返してください。"
                )
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=80
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"generate_observation error: {e}")
            return f"{target}は{card_count}枚の手札を持っているようだ。"

    # -----------------------------------------------------------------------
    # AI自発アクション
    # -----------------------------------------------------------------------

    def decide_action(self, game: DaifugoGame, player_name: str) -> Optional[Dict]:
        """AIが自発的に行動するか決定する（20%確率）"""
        if random.random() > 0.20:
            return None

        active_others = [p for p in game.players
                         if p != player_name
                         and p not in game.ranking
                         and p not in game.caught_players]
        if not active_others:
            return None

        personality = game.personalities.get(player_name)
        if not personality:
            return None

        # 関係値に基づいてターゲットを選ぶ
        rels = game.relationships.get(player_name, {})
        sorted_others = sorted(active_others, key=lambda p: rels.get(p, 0))
        least_liked = sorted_others[0]
        most_liked = sorted_others[-1]

        rel_with_least = rels.get(least_liked, 0)
        rel_with_most = rels.get(most_liked, 0)

        # 敵対相手に accuse/threaten、友好相手に cooperate
        action_weights = {
            "chat": 0.5,
            "cooperate": max(0.1, personality.cooperation_tendency * (rel_with_most + 100) / 200),
            "accuse": max(0.05, personality.aggression * max(0, -rel_with_least) / 100),
        }
        total = sum(action_weights.values())
        r = random.random() * total
        cumulative = 0.0
        chosen_type = "chat"
        for action_type, weight in action_weights.items():
            cumulative += weight
            if r <= cumulative:
                chosen_type = action_type
                break

        if chosen_type == "cooperate":
            target = most_liked
        elif chosen_type == "accuse":
            target = least_liked
        else:
            target = random.choice(active_others)

        messages_by_type = {
            "chat": [
                "調子はどう？", "この勝負、楽しんでる？",
                "なかなかやるね。", "気を抜いてると負けるよ？"
            ],
            "cooperate": [
                "ねえ、一緒に戦わない？", "同盟を組もうよ！",
                "協力すれば二人とも得するよ。", "手を組まない？"
            ],
            "accuse": [
                "ズルしてない？怪しいな。", "なんか変なことしてない？",
                "さっきの手、おかしくなかった？", "気をつけてるよ、ちゃんと見てるから。"
            ],
        }
        message = random.choice(messages_by_type.get(chosen_type, ["..."]))

        return {
            "type": chosen_type,
            "target": target,
            "message": message
        }

    # -----------------------------------------------------------------------
    # カード選択
    # -----------------------------------------------------------------------

    def decide_move(self,
                    game: DaifugoGame,
                    player_name: str,
                    valid_moves: List[List[Card]]) -> List[Card]:
        """Mistral AIがカードの出し方を決定する"""
        game_info = game.get_game_info()
        hand = game.player_hands[player_name]

        # 関係値による追加ヒント
        alliance = game.alliances.get(player_name)
        rels = game.relationships.get(player_name, {})
        enemies = [p for p, v in rels.items() if v <= -60
                   and p not in game.ranking and p not in game.caught_players]

        relationship_hint = ""
        if alliance and alliance not in game.ranking and alliance not in game.caught_players:
            relationship_hint += f"\n- {alliance}と同盟中。{alliance}を有利にするプレイも考慮してください。"
        if enemies:
            relationship_hint += f"\n- {', '.join(enemies)}とは敵対関係。妨害を優先してください。"

        prompt = self._build_prompt(
            player_name=player_name,
            hand=hand,
            valid_moves=valid_moves,
            game_info=game_info,
            relationship_hint=relationship_hint
        )

        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200
            )
            ai_response = response.choices[0].message.content
            return self._parse_response(ai_response, valid_moves)
        except Exception as e:
            print(f"AI Error: {e}")
            return valid_moves[0] if valid_moves else []

    def _build_prompt(self,
                      player_name: str,
                      hand: List[Card],
                      valid_moves: List[List[Card]],
                      game_info: dict,
                      relationship_hint: str = "") -> str:
        """AIへのプロンプトを構築"""
        hand_str = ", ".join(str(card) for card in hand)
        last_played_str = (
            ", ".join(str(card) for card in game_info['last_played'])
            if game_info['last_played'] else "なし"
        )
        moves_description = "\n".join([
            f"{i}: {', '.join(str(c) for c in move) if move else 'パス'}"
            for i, move in enumerate(valid_moves[:5])
        ])

        prompt = f"""あなたは大富豪というトランプゲームをプレイしています。

現在のプレイヤー: {player_name}
あなたの手札: {hand_str}

ゲーム状況:
- 最後に出されたカード: {last_played_str}
- 最後に出したプレイヤー: {game_info['last_played_by']}
- 各プレイヤーの手札枚数: {', '.join(f"{p}: {count}枚" for p, count in game_info['player_card_count'].items())}
- 現在の順位: {', '.join(game_info['ranking']) if game_info['ranking'] else 'なし'}

可能な手（最初の5個）:
{moves_description}

大富豪のゲーム戦略を考えて、次に出すべきカードを決めてください。
以下の戦略を考慮してください：
1. 自分が上がることを優先する
2. 強いカード（2, A, K）は温存する
3. 他のプレイヤーの手札枚数を考慮する
4. リーダーを妨害することも考慮する{relationship_hint}

あなたの判断と選択肢番号（0-{min(4, len(valid_moves)-1)}）を述べてください。"""
        return prompt

    def _parse_response(self, response: str, valid_moves: List[List[Card]]) -> List[Card]:
        """AIのレスポンスから選択肢番号を抽出"""
        numbers = re.findall(r'\d+', response)
        if numbers:
            try:
                idx = int(numbers[-1])
                if 0 <= idx < len(valid_moves):
                    return valid_moves[idx]
            except (ValueError, IndexError):
                pass

        if any(skip_word in response for skip_word in ["パス", "出さない", "パスします"]):
            return valid_moves[0]

        return valid_moves[0] if valid_moves else []

    # -----------------------------------------------------------------------
    # ズルフェーズ
    # -----------------------------------------------------------------------

    def generate_counter_measure(self, game: DaifugoGame, target_player: str,
                                 cheat_prompt: str) -> str:
        """ズルへの対策プロンプトを生成する"""
        try:
            prompt = f"""大富豪ゲームでズルが試みられています。

ズルの内容: {cheat_prompt}
あなたは{target_player}として対策を取ります。

対策の一文を日本語で答えてください（20字以内）。"""
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=60
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return "カードをしっかり守る"

    def evaluate_cheat_contest(self, cheat_prompt: str, counter_prompt: str,
                               game_info: dict) -> dict:
        """ズル対決をMistralに評価させる"""
        default = {"cheat_bonus": 1, "counter_bonus": 1, "effect_type": "peek", "reasoning": "デフォルト判定"}
        try:
            prompt = f"""大富豪ゲームのズル対決を評価してください。

ズルプロンプト: {cheat_prompt}
対策プロンプト: {counter_prompt}

以下のJSONのみを返してください（他の文字を含めないこと）:
{{"cheat_bonus": 0から3の整数, "counter_bonus": 0から3の整数, "effect_type": "peek or swap or skip or extra_cards", "reasoning": "判定理由（日本語20字以内）"}}

effect_typeの選び方:
- 手札を見る・覗く → peek
- 手札を交換する・入れ替える → swap
- 妨害する・スキップ → skip
- カードを押し付ける・追加する → extra_cards"""
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=150
            )
            content = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result["cheat_bonus"] = max(0, min(3, int(result.get("cheat_bonus", 1))))
                result["counter_bonus"] = max(0, min(3, int(result.get("counter_bonus", 1))))
                if result.get("effect_type") not in ["peek", "swap", "skip", "extra_cards"]:
                    result["effect_type"] = "peek"
                if "reasoning" not in result:
                    result["reasoning"] = ""
                return result
        except Exception as e:
            print(f"Evaluate error: {e}")
        return default

    def decide_cheat_attempt(self, game: DaifugoGame, player_name: str) -> Optional[Dict]:
        """AIがズルを試みるかどうか決定する"""
        personality = game.personalities.get(player_name)
        cheat_prob = personality.cheat_tendency if personality else 0.3

        if random.random() > cheat_prob:
            return None

        active = [p for p in game.players
                  if p not in game.ranking and p not in game.caught_players and p != player_name]
        if not active:
            return None

        # 同盟相手は攻撃しない（確率大幅低下）
        ally = game.alliances.get(player_name)
        non_ally = [p for p in active if p != ally]

        # 関係値が低い相手を優先ターゲット
        rels = game.relationships.get(player_name, {})
        candidate_pool = non_ally if non_ally else active
        target = min(candidate_pool, key=lambda p: rels.get(p, 0))

        methods = [
            "手札を盗み見る",
            "手札を入れ替える",
            "行動を妨害する",
            "余分なカードを押し付ける"
        ]
        approaches = ["素早い動きで", "言葉で惑わして", "隙をついて", "表情で騙して"]
        confidences = ["完璧な計画で", "運を頼りに", "慎重に", "大胆に"]

        method = random.choice(methods)
        approach = random.choice(approaches)
        confidence = random.choice(confidences)
        cheat_prompt = f"{confidence}、{approach}、{target}の{method}"
        return {"target": target, "prompt": cheat_prompt}


def make_random_move(valid_moves: List[List[Card]]) -> List[Card]:
    """ランダムに手を選ぶ（AIが使用不可の場合のフォールバック）"""
    return random.choice(valid_moves)
