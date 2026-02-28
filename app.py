"""
大富豪ゲーム - エントリポイント
"""

import streamlit as st
import os
from dotenv import load_dotenv

from game_logic import DaifugoGame, GameState
from ai_player import MistralAIPlayer
from ui.game import render_game_status, render_player_hand_and_action, play_ai_turn
from ui.cheat import render_cheat_phase
from ui.interaction import render_right_panel

load_dotenv()

# -----------------------------------------------------------------------
# ページ設定 & CSS
# -----------------------------------------------------------------------

st.set_page_config(
    page_title="大富豪 - Mistral AI ゲーム",
    page_icon="🎴",
    layout="wide"
)

st.markdown("""
<style>
.stButton > button {
    min-height: 44px;
    touch-action: manipulation;
    font-size: clamp(0.8rem, 2vw, 1rem);
}
.card-display {
    font-size: clamp(1rem, 3vw, 1.4em);
}
.chat-bubble-player {
    background: #1a73e8;
    color: white;
    border-radius: 12px 12px 2px 12px;
    padding: 6px 12px;
    margin: 4px 0 4px 40px;
    display: inline-block;
    max-width: 90%;
    word-break: break-word;
}
.chat-bubble-ai {
    background: #333;
    color: #f0f0f0;
    border-radius: 12px 12px 12px 2px;
    padding: 6px 12px;
    margin: 4px 40px 4px 0;
    display: inline-block;
    max-width: 90%;
    word-break: break-word;
}
.chat-sender {
    font-size: 0.72em;
    color: #aaa;
    margin-bottom: 1px;
}
.rel-meter {
    font-size: 1.2em;
    letter-spacing: 2px;
}
@media (max-width: 768px) {
    .main .block-container { padding: 0.5rem; }
    .stMetric { padding: 0.25rem; }
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------
# セッション状態のデフォルト値
# -----------------------------------------------------------------------

_SS_DEFAULTS = {
    'game': None,
    'ai_player': None,
    'game_log': [],
    'card_select_key': 0,
    'cheat_phase_peek_target': None,
    'cheat_phase_peek_time': None,
    'cheat_result_display': None,
    'selected_chat_target': None,
    'player_notes': {},
    'chat_input_key': 0,
    'action_results': [],
    'ai_personalities': {},
}

for _key, _default in _SS_DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _default

# -----------------------------------------------------------------------
# ゲーム初期化
# -----------------------------------------------------------------------

def initialize_game(num_players: int, use_ai: bool):
    game = DaifugoGame(num_players=num_players)
    game.start_game()

    # セッションをリセット
    for key, val in _SS_DEFAULTS.items():
        st.session_state[key] = val
    st.session_state.game = game

    if use_ai:
        try:
            ai = MistralAIPlayer()
            st.session_state.ai_player = ai
            for player in game.players[1:]:
                with st.spinner(f"{player}の個性を生成中..."):
                    personality = ai.generate_personality(player)
                    game.personalities[player] = personality
                    st.session_state.ai_personalities[player] = personality
        except ValueError as e:
            st.error(f"AI初期化エラー: {e}")

# -----------------------------------------------------------------------
# サイドバー
# -----------------------------------------------------------------------

def render_sidebar():
    with st.sidebar:
        st.header("⚙️ ゲーム設定")

        if st.session_state.game is None:
            num_players = st.slider("プレイヤー数", 2, 4, 4)
            use_ai = st.checkbox("Mistral AI プレイヤーを使用", value=True)

            if use_ai:
                api_key_input = st.text_input(
                    "Mistral API キー（未設定の場合は .env から読み込み）",
                    type="password"
                )
                if api_key_input:
                    os.environ["MISTRAL_API_KEY"] = api_key_input

            if st.button("🎮 ゲームを開始", use_container_width=True):
                initialize_game(num_players, use_ai)
                st.rerun()
        else:
            if st.button("🔄 新しいゲームを開始", use_container_width=True):
                for key, val in _SS_DEFAULTS.items():
                    st.session_state[key] = val
                st.rerun()
            if st.button("❌ ゲームを終了", use_container_width=True):
                st.session_state.game = None
                st.session_state.game_log = []
                st.rerun()

        st.markdown("---")
        st.subheader("📖 ルール")
        st.write("""
        - ♠3を持つプレイヤーが先手
        - 場より強いカードを出す
        - 同ランク複数枚（ペア等）も可
        - 出せない・出したくない場合はパス
        - 全員パスで **ズルフェーズ** 開始
        - ズル成功→効果発動 / ズルバレ→最下位
        - 手札がなくなったら上がり

        **ランク順（弱→強）:**
        3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A < 2
        """)
        st.markdown("---")
        st.subheader("💡 関係値")
        st.write("""
        | 値 | 状態 |
        |---|---|
        | +60〜+100 | 🤝 同盟 |
        | +30〜+59 | 😊 友好 |
        | -29〜+29 | 😐 中立 |
        | -30〜-59 | 😒 警戒 |
        | -60〜-100 | 😡 敵対 |
        """)

# -----------------------------------------------------------------------
# メイン
# -----------------------------------------------------------------------

def main():
    st.title("🎴 大富豪 - Mistral AI版")
    st.markdown("---")

    render_sidebar()

    if st.session_state.game is None:
        st.info("ゲームを開始するには、サイドバーで設定をしてください。")
        return

    game: DaifugoGame = st.session_state.game

    left_col, right_col = st.columns([7, 3])

    with left_col:
        render_game_status()

        if game.game_state == GameState.CHEAT_PHASE:
            render_cheat_phase()
        elif game.game_state == GameState.PLAYING:
            render_player_hand_and_action()
            if game.get_current_player() != "Player 1":
                play_ai_turn()
                st.rerun()
        elif game.game_state != GameState.GAME_OVER:
            render_player_hand_and_action()

        if game.game_state == GameState.GAME_OVER:
            st.markdown("---")
            st.success("🎉 ゲーム終了！")
            st.subheader("最終順位")
            medals = ["🥇", "🥈", "🥉", "4️⃣"]
            for idx, player in enumerate(game.ranking):
                caught_mark = " 🚨（ズルバレ）" if player in game.caught_players else ""
                st.write(f"{medals[idx] if idx < len(medals) else '　'} 第{idx+1}位: {player}{caught_mark}")

    with right_col:
        render_right_panel()


if __name__ == "__main__":
    main()
