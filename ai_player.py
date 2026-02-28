"""
Mistral AIを使った大富豪のAIプレイヤー
"""

from typing import List, Optional
from game_logic import Card, DaifugoGame
import os
from mistralai.client import MistralClient
from mistralai.models.chat_message import ChatMessage

class MistralAIPlayer:
    """Mistral AIを使ったプレイヤー"""
    
    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            api_key = os.getenv("MISTRAL_API_KEY")
        
        if not api_key:
            raise ValueError("MISTRAL_API_KEYが設定されていません")
        
        self.client = MistralClient(api_key=api_key)
        self.model = "mistral-small"
    
    def decide_move(self, 
                   game: DaifugoGame, 
                   player_name: str,
                   valid_moves: List[List[Card]]) -> List[Card]:
        """
        Mistral AIがカードの出し方を決定する
        
        Args:
            game: ゲーム状態
            player_name: プレイヤー名
            valid_moves: 可能な手のリスト
        
        Returns:
            出すカードのリスト
        """
        
        # ゲーム状況の説明を作成
        game_info = game.get_game_info()
        hand = game.player_hands[player_name]
        
        # プロンプトを構築
        prompt = self._build_prompt(
            player_name=player_name,
            hand=hand,
            valid_moves=valid_moves,
            game_info=game_info
        )
        
        # Mistral AIに問い合わせ
        try:
            message = ChatMessage(role="user", content=prompt)
            response = self.client.chat(
                model=self.model,
                messages=[message],
                temperature=0.7,
                max_tokens=200
            )
            
            ai_response = response.choices[0].message.content
            
            # レスポンスからカードを選択
            selected_move = self._parse_response(ai_response, valid_moves)
            return selected_move
        except Exception as e:
            print(f"AI Error: {e}")
            # エラーの場合は最初の有効な手を選ぶ
            return valid_moves[0] if valid_moves else []
    
    def _build_prompt(self, 
                     player_name: str,
                     hand: List[Card],
                     valid_moves: List[List[Card]],
                     game_info: dict) -> str:
        """AIへのプロンプトを構築"""
        
        hand_str = ", ".join(str(card) for card in hand)
        last_played_str = ", ".join(str(card) for card in game_info['last_played']) if game_info['last_played'] else "なし"
        
        # 有効な手の説明
        moves_description = "パス（無し）"
        if len(valid_moves) > 1:
            moves_description = "\n".join([
                f"{i}: {', '.join(str(c) for c in move) if move else 'パス'}"
                for i, move in enumerate(valid_moves[:5])  # 最初の5個まで
            ])
        
        prompt = f"""あなたは大富豪というトランプゲームをプレイしています。

現在のプレイヤー: {player_name}
あなたの手札: {hand_str}

ゲーム状況:
- 最後に出されたカード: {last_played_str}
- 最後に出したプレイヤー: {game_info['last_played_by']}
- 各プレイヤーの手札枚数: {', '.join(f"{p}: {count}枚" for p, count in game_info['player_card_count'].items())}
- 現在の順位: {', '.join(game_info['ranking'])}

可能な手（最初の5個）:
{moves_description}

大富豪のゲーム戦略を考えて、次に出すべきカードを決めてください。
以下の戦略を考慮してください：
1. 自分が上がることを優先する
2. 強いカード（2, A, K）は温存する
3. 他のプレイヤーの手札枚数を考慮する
4. リーダーを妨害することも考慮する

あなたの判断と選択肢番号（0-4）を述べてください。"""

        return prompt
    
    def _parse_response(self, response: str, valid_moves: List[List[Card]]) -> List[Card]:
        """AIのレスポンスから選択肢番号を抽出"""
        
        # 数字を探す（選択肢番号）
        import re
        numbers = re.findall(r'\d+', response)
        
        if numbers:
            try:
                idx = int(numbers[-1])  # 最後の数字を取得
                if 0 <= idx < len(valid_moves):
                    return valid_moves[idx]
            except (ValueError, IndexError):
                pass
        
        # 数字が見つからない場合は、"パス"や"出さない"の有無で判定
        if any(skip_word in response for skip_word in ["パス", "出さない", "パスします", "出させ"]):
            return valid_moves[0]  # パス
        
        # それでも判定できない場合は、最初の有効な手を選ぶ
        return valid_moves[0] if valid_moves else []


def make_random_move(valid_moves: List[List[Card]]) -> List[Card]:
    """ランダムに手を選ぶ（AIが使用不可の場合のフォールバック）"""
    import random
    return random.choice(valid_moves)
