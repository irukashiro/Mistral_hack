"""
大富豪ゲーム - Streamlit UI
"""

import streamlit as st
from game_logic import DaifugoGame, GameState, Card
from ai_player import MistralAIPlayer, make_random_move
from typing import Optional
import os
from dotenv import load_dotenv

# 環境変数を読み込む
load_dotenv()

# ページ設定
st.set_page_config(
    page_title="大富豪 - Mistral AI ゲーム",
    page_icon="🎴",
    layout="wide"
)

st.title("🎴 大富豪 - Mistral AI版")
st.markdown("---")

# セッション状態の初期化
if 'game' not in st.session_state:
    st.session_state.game = None
if 'ai_player' not in st.session_state:
    st.session_state.ai_player = None
if 'game_log' not in st.session_state:
    st.session_state.game_log = []

def initialize_game(num_players: int, use_ai: bool):
    """ゲームを初期化"""
    st.session_state.game = DaifugoGame(num_players=num_players)
    st.session_state.game.start_game()
    st.session_state.game_log = []
    
    if use_ai:
        try:
            st.session_state.ai_player = MistralAIPlayer()
        except ValueError as e:
            st.error(f"AI初期化エラー: {e}")
            st.session_state.ai_player = None

def get_player_hand_display(cards: list[Card]) -> str:
    """手札をテーブル形式で表示"""
    if not cards:
        return "（カードなし）"
    
    sorted_cards = sorted(cards, key=lambda c: c.get_rank_value())
    return " ".join(str(card) for card in sorted_cards)

def render_game_status():
    """ゲームの状態を表示"""
    if st.session_state.game is None:
        return
    
    game = st.session_state.game
    info = game.get_game_info()
    
    # 現在の情報
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("現在のプレイヤー", info['current_player'])
    
    with col2:
        st.metric("ゲーム状態", info['game_state'].value)
    
    with col3:
        if info['last_played']:
            st.metric("最後に出されたカード", ", ".join(str(c) for c in info['last_played']))
        else:
            st.metric("最後に出されたカード", "なし")
    
    st.markdown("---")
    
    # プレイヤーの情報テーブル
    st.subheader("プレイヤー情報")
    
    player_data = []
    for player in game.players:
        card_count = info['player_card_count'][player]
        is_current = "👈 現在" if player == info['current_player'] else ""
        rank = ""
        if player in info['ranking']:
            rank = f"第{info['ranking'].index(player) + 1}位"
        
        player_data.append({
            "プレイヤー": f"{player} {is_current}",
            "手札枚数": card_count,
            "順位": rank
        })
    
    st.dataframe(player_data, use_container_width=True)

def render_player_hand():
    """プレイヤーの手札を表示"""
    if st.session_state.game is None:
        return
    
    # "Player 1" が人間プレイヤー
    human_player = "Player 1"
    hand = st.session_state.game.player_hands[human_player]
    
    st.subheader(f"{human_player}の手札")
    
    if hand:
        sorted_hand = sorted(hand, key=lambda c: c.get_rank_value())
        # カードグリッドで表示
        cols = st.columns(min(6, len(sorted_hand)))
        for idx, card in enumerate(sorted_hand):
            with cols[idx % 6]:
                st.button(
                    str(card),
                    key=f"card_{idx}",
                    on_click=lambda c=card: select_card(c, sorted_hand)
                )
    else:
        st.info("カードはありません（上がった！）")

def play_ai_turn():
    """AIのターンをプレイ"""
    if st.session_state.game is None:
        return
    
    game = st.session_state.game
    current_player = game.get_current_player()
    
    # AIプレイヤーかチェック
    if current_player == "Player 1":
        return
    
    valid_moves = game.get_valid_moves(current_player)
    
    # AIが手を決定
    if st.session_state.ai_player:
        try:
            selected_move = st.session_state.ai_player.decide_move(
                game, current_player, valid_moves
            )
        except Exception as e:
            st.warning(f"AI決定エラー: {e}")
            selected_move = make_random_move(valid_moves)
    else:
        selected_move = make_random_move(valid_moves)
    
    # カードをプレイ
    game.play_cards(current_player, selected_move)
    
    # ログに追加
    if selected_move:
        move_str = ", ".join(str(c) for c in selected_move)
        st.session_state.game_log.append(f"{current_player}: {move_str} を出した")
    else:
        st.session_state.game_log.append(f"{current_player}: パス")

def select_card(card: Card, hand: list[Card]):
    """カードを選択"""
    if 'selected_cards' not in st.session_state:
        st.session_state.selected_cards = []
    
    if card not in st.session_state.selected_cards:
        st.session_state.selected_cards.append(card)

def render_player_action():
    """プレイヤーのアクション（カード選択）"""
    if st.session_state.game is None:
        return
    
    game = st.session_state.game
    human_player = "Player 1"
    current_player = game.get_current_player()
    
    # プレイヤーのターンかチェック
    if current_player != human_player:
        return
    
    st.subheader("アクション")
    
    valid_moves = game.get_valid_moves(human_player)
    
    # 選択されたカード
    if 'selected_cards' not in st.session_state:
        st.session_state.selected_cards = []
    
    selected_str = ", ".join(str(c) for c in st.session_state.selected_cards)
    st.write(f"選択中: {selected_str if selected_str else 'なし'}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🎯 カードを出す"):
            # 選択したカードが有効か確認
            if st.session_state.selected_cards in valid_moves:
                game.play_cards(human_player, st.session_state.selected_cards)
                move_str = ", ".join(str(c) for c in st.session_state.selected_cards)
                st.session_state.game_log.append(f"{human_player}: {move_str} を出した")
                st.session_state.selected_cards = []
                st.rerun()
            else:
                st.error("無効な選択です")
    
    with col2:
        if st.button("🚫 パス"):
            game.play_cards(human_player, [])
            st.session_state.game_log.append(f"{human_player}: パス")
            st.session_state.selected_cards = []
            st.rerun()
    
    with col3:
        if st.button("🔄 選択をリセット"):
            st.session_state.selected_cards = []
            st.rerun()

def render_game_log():
    """ゲームログを表示"""
    if not st.session_state.game_log:
        return
    
    with st.expander("📜 ゲームログ", expanded=True):
        for log in reversed(st.session_state.game_log[-10:]):  # 最後の10個を表示
            st.text(log)

def main():
    """メイン処理"""
    
    # サイドバーで設定
    with st.sidebar:
        st.header("⚙️ ゲーム設定")
        
        if st.session_state.game is None:
            num_players = st.slider("プレイヤー数", 2, 4, 4)
            use_ai = st.checkbox("AI プレイヤーを使用", value=True)
            
            if st.button("🎮 ゲームを開始", use_container_width=True):
                initialize_game(num_players, use_ai)
                st.rerun()
        else:
            if st.button("🔄 新しいゲームを開始", use_container_width=True):
                st.session_state.game = None
                st.session_state.ai_player = None
                st.session_state.game_log = []
                st.rerun()
            
            if st.button("❌ ゲームを終了", use_container_width=True):
                st.session_state.game = None
                st.session_state.game_log = []
                st.rerun()
        
        st.markdown("---")
        st.subheader("📖 ルール")
        st.write("""
        - 3から開始する
        - 前のカードより強いカードを出す
        - 複数枚のカード（ペア、トリプル）も可能
        - パスできる
        - 全員がパスすると場がリセット
        - 手札がなくなったら上がり
        """)
    
    # メインコンテンツ
    if st.session_state.game is None:
        st.info("ゲームを開始するには、サイドバーで設定をしてください。")
    else:
        game = st.session_state.game
        
        # ゲームの状態を表示
        render_game_status()
        
        # プレイヤーの手札を表示
        if game.game_state != GameState.GAME_OVER:
            render_player_hand()
            render_player_action()
        
        # AIのターン（自動）
        if game.game_state == GameState.PLAYING:
            current_player = game.get_current_player()
            if current_player != "Player 1":
                # AIのターン
                play_ai_turn()
                st.rerun()
        
        # ゲームログ
        render_game_log()
        
        # ゲーム終了
        if game.game_state == GameState.GAME_OVER:
            st.markdown("---")
            st.success("🎉 ゲーム終了！")
            st.subheader("最終順位")
            for idx, player in enumerate(game.ranking):
                medal = ["🥇", "🥈", "🥉", "4️⃣"][idx]
                st.write(f"{medal} 第{idx + 1}位: {player}")

if __name__ == "__main__":
    main()
