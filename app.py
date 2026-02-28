"""
大富豪ゲーム - Streamlit UI（2カラム + インタラクションパネル）
"""

import streamlit as st
from game_logic import DaifugoGame, GameState, Card, CheatAttempt
from ai_player import MistralAIPlayer, make_random_move
import os
import time as time_module
import random
from dotenv import load_dotenv

load_dotenv()

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

st.title("🎴 大富豪 - Mistral AI版")
st.markdown("---")

# -----------------------------------------------------------------------
# セッション状態の初期化
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
for _key, _val in _SS_DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val


# -----------------------------------------------------------------------
# 初期化
# -----------------------------------------------------------------------

def initialize_game(num_players: int, use_ai: bool):
    """ゲームを初期化"""
    game = DaifugoGame(num_players=num_players)
    game.start_game()
    st.session_state.game = game
    st.session_state.game_log = []
    st.session_state.card_select_key = 0
    st.session_state.cheat_phase_peek_target = None
    st.session_state.cheat_phase_peek_time = None
    st.session_state.cheat_result_display = None
    st.session_state.selected_chat_target = None
    st.session_state.player_notes = {}
    st.session_state.chat_input_key = 0
    st.session_state.action_results = []
    st.session_state.ai_personalities = {}

    if use_ai:
        try:
            ai = MistralAIPlayer()
            st.session_state.ai_player = ai
            # AI個性を生成（Player 2以降）
            for player in game.players[1:]:
                with st.spinner(f"{player}の個性を生成中..."):
                    personality = ai.generate_personality(player)
                    game.personalities[player] = personality
                    st.session_state.ai_personalities[player] = personality
        except ValueError as e:
            st.error(f"AI初期化エラー: {e}")
            st.session_state.ai_player = None
    else:
        st.session_state.ai_player = None


# -----------------------------------------------------------------------
# ゲームステータス
# -----------------------------------------------------------------------

def render_game_status():
    game = st.session_state.game
    info = game.get_game_info()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("現在のプレイヤー", info['current_player'])
    with col2:
        st.metric("ゲーム状態", info['game_state'].value)
    with col3:
        if info['last_played']:
            st.metric("場のカード", ", ".join(str(c) for c in info['last_played']))
        else:
            st.metric("場のカード", "なし（自由に出せる）")

    st.markdown("---")
    st.subheader("プレイヤー情報")
    player_data = []
    for player in game.players:
        card_count = info['player_card_count'][player]
        is_current = "👈 現在" if player == info['current_player'] else ""
        rank_str = ""
        if player in info['ranking']:
            rank_str = f"第{info['ranking'].index(player) + 1}位"
        caught = "🚨 バレ" if player in info.get('caught_players', []) else ""
        ally = game.alliances.get(player)
        ally_str = f"🤝{ally}" if ally else ""
        p = game.personalities.get(player)
        char_name = p.character_name if p else player
        player_data.append({
            "プレイヤー": f"{player}（{char_name}） {is_current}",
            "手札枚数": card_count,
            "順位": rank_str,
            "状態": f"{caught} {ally_str}".strip()
        })
    st.dataframe(player_data, use_container_width=True)


# -----------------------------------------------------------------------
# チートフェーズ
# -----------------------------------------------------------------------

def _render_cheat_result(result: dict):
    attempt = result["attempt"]
    with st.expander("📊 前回のズル判定結果", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("ズル側", f"{result['cheat_total']}点",
                      delta=f"ロール {attempt.cheat_roll} + ボーナス {attempt.cheat_bonus}")
        with col2:
            st.metric("対策側", f"{result['counter_total']}点",
                      delta=f"ロール {attempt.counter_roll} + ボーナス {attempt.counter_bonus}")
        if attempt.success:
            st.success(f"✅ ズル成功！{attempt.attacker} が {attempt.target} に **{attempt.effect_type}** を実行")
        else:
            st.error(f"🚨 バレた！{attempt.attacker} は最下位に転落...")
        if result.get("reasoning"):
            st.caption(f"Mistral判定: {result['reasoning']}")
        st.text(f"ズル: 「{attempt.cheat_prompt}」")
        st.text(f"対策: 「{attempt.counter_prompt}」")


def _execute_cheat(game: DaifugoGame, attacker: str, target: str, cheat_prompt: str):
    if not game.cheat_queue or game.cheat_queue[0] != attacker:
        return

    counter_prompt = "カードをしっかり守る"
    if st.session_state.ai_player:
        with st.spinner(f"{target}が対策を考えています..."):
            counter_prompt = st.session_state.ai_player.generate_counter_measure(
                game, target, cheat_prompt)

    eval_result = {"cheat_bonus": 1, "counter_bonus": 1, "effect_type": "peek", "reasoning": ""}
    if st.session_state.ai_player:
        with st.spinner("Mistralが判定中..."):
            eval_result = st.session_state.ai_player.evaluate_cheat_contest(
                cheat_prompt, counter_prompt, game.get_game_info())

    # 関係値ボーナスを加算
    rel_bonus = game.get_relationship_bonus(attacker, target)
    cheat_bonus = eval_result.get("cheat_bonus", 0) + rel_bonus

    cheat_roll = random.randint(1, 6) + random.randint(1, 6)
    counter_roll = random.randint(1, 6) + random.randint(1, 6)
    cheat_total = cheat_roll + cheat_bonus
    counter_total = counter_roll + eval_result.get("counter_bonus", 0)
    success = cheat_total > counter_total
    effect_type = eval_result.get("effect_type", "peek")

    attempt = CheatAttempt(
        attacker=attacker,
        target=target,
        cheat_prompt=cheat_prompt,
        counter_prompt=counter_prompt,
        cheat_bonus=cheat_bonus,
        counter_bonus=eval_result.get("counter_bonus", 0),
        cheat_roll=cheat_roll,
        counter_roll=counter_roll,
        success=success,
        effect_type=effect_type,
        caught=not success
    )
    game.cheat_attempts.append(attempt)

    if success:
        game.apply_cheat_effect(attacker, target, effect_type)
        if effect_type == "peek":
            st.session_state.cheat_phase_peek_target = target
            st.session_state.cheat_phase_peek_time = time_module.time()
        # ズル成功: 関係値悪化
        game.update_relationship(attacker, target, -10)
    else:
        game.catch_cheater(attacker)

    if success:
        st.session_state.game_log.append(
            f"🃏 {attacker}がズル成功！({effect_type}) vs {target} [{cheat_total}vs{counter_total}]")
    else:
        st.session_state.game_log.append(
            f"🚨 {attacker}がズルを見破られた！最下位に [{cheat_total}vs{counter_total}]")

    if game.cheat_queue and game.cheat_queue[0] == attacker:
        game.cheat_queue.pop(0)

    st.session_state.cheat_result_display = {
        "attempt": attempt,
        "cheat_total": cheat_total,
        "counter_total": counter_total,
        "reasoning": eval_result.get("reasoning", "")
    }
    st.rerun()


def _process_ai_cheat_phase(game: DaifugoGame, ai_player_name: str):
    if not st.session_state.ai_player:
        game.cheat_queue.pop(0)
        st.session_state.game_log.append(f"{ai_player_name}: ズルをスキップ（AI未設定）")
        st.rerun()
        return

    cheat_info = st.session_state.ai_player.decide_cheat_attempt(game, ai_player_name)
    if cheat_info:
        st.info(f"🤖 {ai_player_name} がズルを試みています...")
        _execute_cheat(game, ai_player_name, cheat_info["target"], cheat_info["prompt"])
    else:
        game.cheat_queue.pop(0)
        st.session_state.game_log.append(f"{ai_player_name}: ズルを見送った")
        st.rerun()


def render_cheat_phase():
    game = st.session_state.game

    if not game.cheat_queue:
        game.game_state = GameState.PLAYING
        game._next_player()
        st.rerun()
        return

    st.subheader("🃏 ズルフェーズ")
    st.caption("場がリセットされました。ズルのチャンスです！")

    if st.session_state.cheat_result_display:
        _render_cheat_result(st.session_state.cheat_result_display)
        st.session_state.cheat_result_display = None

    current = game.cheat_queue[0]

    if current in game.caught_players or current in game.ranking:
        game.cheat_queue.pop(0)
        st.rerun()
        return

    st.info(f"**{current}** のズルチャンス（キュー残: {len(game.cheat_queue)}人）")

    if current == "Player 1":
        active_others = [p for p in game.players
                         if p != current
                         and p not in game.ranking
                         and p not in game.caught_players]
        if not active_others:
            game.cheat_queue.pop(0)
            st.session_state.game_log.append(f"{current}: ズル対象がいないためスキップ")
            st.rerun()
            return

        st.write("ズル作戦を選んでください:")
        col1, col2 = st.columns(2)
        with col1:
            method = st.selectbox("手口", [
                "手札を盗み見る", "手札を入れ替える",
                "行動を妨害する", "余分なカードを押し付ける"
            ], key="cheat_method")
            approach = st.selectbox("アプローチ", [
                "素早い動きで", "言葉で惑わして", "隙をついて", "表情で騙して"
            ], key="cheat_approach")
        with col2:
            confidence = st.selectbox("自信レベル", [
                "完璧な計画で", "運を頼りに", "慎重に", "大胆に"
            ], key="cheat_confidence")
            target = st.selectbox("ターゲット", active_others, key="cheat_target")

        cheat_prompt = f"{confidence}、{approach}、{target}の{method}"
        st.caption(f"ズルプロンプト: 「{cheat_prompt}」")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🎲 ズルを実行！", use_container_width=True):
                _execute_cheat(game, current, target, cheat_prompt)
        with col_b:
            if st.button("😇 見送る", use_container_width=True):
                game.cheat_queue.pop(0)
                st.session_state.game_log.append(f"{current}: ズルを見送った")
                st.rerun()
    else:
        _process_ai_cheat_phase(game, current)


# -----------------------------------------------------------------------
# 手札 & アクション
# -----------------------------------------------------------------------

def render_player_hand_and_action():
    game = st.session_state.game
    human_player = "Player 1"
    current_player = game.get_current_player()

    peek_target = st.session_state.cheat_phase_peek_target
    peek_time = st.session_state.cheat_phase_peek_time
    if peek_target and peek_time and (time_module.time() - peek_time) < 3.0:
        st.info(f"👀 **{peek_target}の手札を覗いています！**")
        peek_hand = game.player_hands.get(peek_target, [])
        if peek_hand:
            sorted_peek = sorted(peek_hand, key=lambda c: c.get_rank_value())
            st.markdown(f"**{peek_target}の手札**: {', '.join(str(c) for c in sorted_peek)}")
    elif peek_target:
        st.session_state.cheat_phase_peek_target = None
        st.session_state.cheat_phase_peek_time = None

    hand = game.player_hands[human_player]
    st.subheader(f"{human_player}の手札")

    if not hand:
        st.success("上がり！手札がありません 🎉")
        return

    sorted_hand = sorted(hand, key=lambda c: c.get_rank_value())
    card_cols = st.columns(min(13, len(sorted_hand)))
    for idx, card in enumerate(sorted_hand):
        suit = card.suit.value
        color = "red" if suit in ("♥", "♦") else "black"
        with card_cols[idx % 13]:
            st.markdown(
                f"<div class='card-display' style='text-align:center; color:{color};'>{card}</div>",
                unsafe_allow_html=True
            )

    st.markdown("")

    if current_player != human_player:
        st.info(f"⏳ {current_player} のターンです...")
        return

    card_options = [str(card) for card in sorted_hand]
    selected_strs = st.multiselect(
        "出すカードを選択（複数枚同ランクも可）",
        card_options,
        key=f"card_select_{st.session_state.card_select_key}"
    )
    selected_cards = [card for card in sorted_hand if str(card) in selected_strs]

    if selected_cards:
        if game.is_valid_move(selected_cards):
            st.success(f"✅ 有効な手: {', '.join(selected_strs)}")
        else:
            st.warning("⚠️ この組み合わせは無効です（同ランク・枚数・強さを確認）")

    col1, col2 = st.columns(2)
    with col1:
        play_disabled = not selected_cards or not game.is_valid_move(selected_cards)
        if st.button("🎯 カードを出す", disabled=play_disabled, use_container_width=True):
            game.play_cards(human_player, selected_cards)
            move_str = ", ".join(str(c) for c in selected_cards)
            st.session_state.game_log.append(f"{human_player}: {move_str} を出した")
            st.session_state.card_select_key += 1
            st.rerun()
    with col2:
        if st.button("🚫 パス", use_container_width=True):
            game.play_cards(human_player, [])
            st.session_state.game_log.append(f"{human_player}: パス")
            st.session_state.card_select_key += 1
            st.rerun()


# -----------------------------------------------------------------------
# AI ターン
# -----------------------------------------------------------------------

def play_ai_turn():
    game = st.session_state.game
    current_player = game.get_current_player()

    if current_player == "Player 1":
        return

    valid_moves = game.get_valid_moves(current_player)

    if st.session_state.ai_player:
        try:
            selected_move = st.session_state.ai_player.decide_move(
                game, current_player, valid_moves)
        except Exception as e:
            st.warning(f"AI決定エラー: {e}")
            selected_move = make_random_move(valid_moves)
    else:
        selected_move = make_random_move(valid_moves)

    game.play_cards(current_player, selected_move)

    if selected_move:
        move_str = ", ".join(str(c) for c in selected_move)
        st.session_state.game_log.append(f"{current_player}: {move_str} を出した")
    else:
        st.session_state.game_log.append(f"{current_player}: パス")

    # AI自発アクション（20%確率）
    if st.session_state.ai_player and game.game_state == GameState.PLAYING:
        _try_ai_spontaneous_action(game, current_player)


def _try_ai_spontaneous_action(game: DaifugoGame, ai_player_name: str):
    """AIが自発的にアクション（チャット等）を起こす"""
    action = st.session_state.ai_player.decide_action(game, ai_player_name)
    if not action:
        return

    target = action["target"]
    msg = action["message"]
    action_type = action["type"]

    personality = game.personalities.get(ai_player_name)
    char_name = personality.character_name if personality else ai_player_name

    if action_type == "chat":
        game.add_conversation(ai_player_name, target, ai_player_name, msg, "chat")
        game.update_relationship(ai_player_name, target, 1)
        st.session_state.action_results.append(
            f"💬 {char_name}が{target}に話しかけた: 「{msg}」")
        st.session_state.game_log.append(
            f"💬 {char_name}→{target}: 「{msg}」")
    elif action_type == "cooperate":
        # 協力提案
        rel = game.relationships.get(ai_player_name, {}).get(target, 0)
        p = game.personalities.get(ai_player_name)
        accept_prob = (p.cooperation_tendency if p else 0.5) * (rel + 100) / 200
        if random.random() < accept_prob:
            game.propose_alliance(ai_player_name, target)
            game.update_relationship(ai_player_name, target, 20)
            game.add_conversation(ai_player_name, target, ai_player_name, msg, "cooperate")
            st.session_state.action_results.append(
                f"🤝 {char_name}と{target}が同盟を結んだ！")
            st.session_state.game_log.append(f"🤝 同盟成立: {char_name} & {target}")
        else:
            game.update_relationship(ai_player_name, target, -5)
            st.session_state.action_results.append(
                f"🙅 {char_name}の同盟提案を{target}が断った")
    elif action_type == "accuse":
        game.update_relationship(ai_player_name, target, -10)
        game.add_conversation(ai_player_name, target, ai_player_name, msg, "accuse")
        st.session_state.action_results.append(
            f"⚔️ {char_name}が{target}を非難: 「{msg}」")
        st.session_state.game_log.append(f"⚔️ {char_name}→{target}: 「{msg}」")


# -----------------------------------------------------------------------
# 右パネルのインタラクション関数
# -----------------------------------------------------------------------

def _get_relationship_label(val: int) -> str:
    if val >= 60:
        return "同盟"
    elif val >= 30:
        return "友好"
    elif val >= -29:
        return "中立"
    elif val >= -59:
        return "警戒"
    return "敵対"


def render_relationship_meter(value: int):
    """-100〜+100を5段階のハートで表示"""
    clamped = max(-100, min(100, value))
    # -100〜+100 を 0〜5に変換
    filled = round((clamped + 100) / 40)  # 0〜5
    hearts = "♥" * filled + "♡" * (5 - filled)
    label = _get_relationship_label(clamped)
    color = "#e74c3c" if clamped < 0 else "#2ecc71" if clamped > 30 else "#f39c12"
    st.markdown(
        f"<span class='rel-meter' style='color:{color};'>{hearts}</span> "
        f"<span style='color:#aaa;font-size:0.85em;'>{clamped:+d} {label}</span>",
        unsafe_allow_html=True
    )


def render_chat_history(player_a: str, player_b: str):
    """WhatsAppスタイルの会話ログ"""
    game = st.session_state.game
    history = game.get_conversation(player_a, player_b)
    if not history:
        st.caption("まだ会話がありません")
        return

    chat_html = ""
    for msg in history[-12:]:  # 直近12件
        sender = msg["sender"]
        text = msg["message"]
        if sender == player_a:
            chat_html += (
                f"<div class='chat-sender' style='text-align:right;'>{sender}</div>"
                f"<div style='text-align:right;'><span class='chat-bubble-player'>{text}</span></div>"
            )
        else:
            p = game.personalities.get(sender)
            char_name = p.character_name if p else sender
            chat_html += (
                f"<div class='chat-sender'>{char_name}</div>"
                f"<div><span class='chat-bubble-ai'>{text}</span></div>"
            )
    st.markdown(chat_html, unsafe_allow_html=True)


def handle_chat_action(target: str, message: str):
    """チャット送信処理"""
    if not message.strip():
        return
    game = st.session_state.game
    human = "Player 1"
    game.add_conversation(human, target, human, message, "chat")

    # AI応答生成
    if st.session_state.ai_player:
        personality = game.personalities.get(target)
        if personality:
            rel = game.relationships.get(human, {}).get(target, 0)
            with st.spinner(f"{target}が返答中..."):
                reply = st.session_state.ai_player.generate_chat_response(
                    message, human, personality, {"relationship": rel})
            game.add_conversation(human, target, target, reply, "chat")
            # 関係値微調整
            game.update_relationship(human, target, 2)
    st.session_state.chat_input_key += 1
    st.rerun()


def handle_observe(target: str):
    """観察アクション"""
    game = st.session_state.game
    human = "Player 1"

    if st.session_state.ai_player:
        personality = game.personalities.get(target)
        if personality:
            with st.spinner(f"{target}を観察中..."):
                hint = st.session_state.ai_player.generate_observation(
                    target, personality, game.get_game_info())
            game.info_revealed[human].append(hint)
            st.session_state.action_results.append(f"👀 観察結果（{target}）: {hint}")
            # プライバシー侵害: 関係値-5
            game.update_relationship(human, target, -5)
            game.add_conversation(human, target, human, "（こっそり観察）", "observe")
    else:
        card_count = len(game.player_hands.get(target, []))
        hint = f"{target}は{card_count}枚の手札を持っている。"
        game.info_revealed[human].append(hint)
        st.session_state.action_results.append(f"👀 観察結果（{target}）: {hint}")
    st.rerun()


def handle_cooperate(target: str):
    """協力/同盟提案"""
    game = st.session_state.game
    human = "Player 1"
    personality = game.personalities.get(target)

    rel = game.relationships.get(human, {}).get(target, 0)
    coop = personality.cooperation_tendency if personality else 0.5
    accept_prob = coop * (rel + 100) / 200

    game.add_conversation(human, target, human, "一緒に戦わない？同盟を組もう！", "cooperate")

    if random.random() < accept_prob:
        game.propose_alliance(human, target)
        game.update_relationship(human, target, 20)
        # AI返答
        if st.session_state.ai_player and personality:
            with st.spinner(f"{target}が返答中..."):
                reply = st.session_state.ai_player.generate_chat_response(
                    "同盟を組もう！", human, personality, {"relationship": rel + 20})
            game.add_conversation(human, target, target, reply, "cooperate")
        st.session_state.action_results.append(f"🤝 {target}と同盟を結んだ！関係値+20")
        st.session_state.game_log.append(f"🤝 同盟成立: Player 1 & {target}")
    else:
        game.update_relationship(human, target, -5)
        if st.session_state.ai_player and personality:
            with st.spinner(f"{target}が返答中..."):
                reply = st.session_state.ai_player.generate_chat_response(
                    "同盟を組もう！", human, personality, {"relationship": rel})
            game.add_conversation(human, target, target, reply, "cooperate")
        st.session_state.action_results.append(f"🙅 {target}に同盟を断られた。関係値-5")
    st.rerun()


def handle_accuse(target: str):
    """告発アクション"""
    game = st.session_state.game
    human = "Player 1"
    personality = game.personalities.get(target)

    game.add_conversation(human, target, human, "ズルしてるよね？", "accuse")
    game.update_relationship(human, target, -10)

    caught = target in game.caught_players
    if caught:
        st.session_state.action_results.append(
            f"🎯 {target}はズルをしていた！証拠がある。関係値-20")
        game.update_relationship(human, target, -10)  # 合計-20
        hint = f"{target}はズルをしていることが確認された"
        game.info_revealed[human].append(hint)
    else:
        st.session_state.action_results.append(f"❓ {target}のズルは確認できなかった。関係値-10")

    if st.session_state.ai_player and personality:
        # honestyに応じた返答
        honesty_note = "正直に答えてください。" if personality.honesty > 0.5 else "否定してください。"
        msg = f"ズルしてるよね？{honesty_note}"
        with st.spinner(f"{target}が返答中..."):
            reply = st.session_state.ai_player.generate_chat_response(
                msg, human, personality,
                {"relationship": game.relationships.get(human, {}).get(target, 0)})
        game.add_conversation(human, target, target, reply, "accuse")
    st.rerun()


def handle_break_alliance(target: str):
    """同盟破棄"""
    game = st.session_state.game
    human = "Player 1"
    game.break_alliance(human, target)
    game.update_relationship(human, target, -20)
    game.add_conversation(human, target, human, "同盟を解消する！", "break_alliance")
    st.session_state.action_results.append(f"💔 {target}との同盟を破棄した。関係値-20")
    st.session_state.game_log.append(f"💔 同盟解消: Player 1 & {target}")
    st.rerun()


# -----------------------------------------------------------------------
# 右パネル描画
# -----------------------------------------------------------------------

def render_right_panel():
    game = st.session_state.game
    human = "Player 1"

    # ----------- アクション結果フラッシュ -----------
    if st.session_state.action_results:
        for res in st.session_state.action_results[-3:]:
            st.info(res)
        st.session_state.action_results = []

    # ----------- 対話相手選択 -----------
    other_players = [p for p in game.players if p != human]
    if not other_players:
        st.write("対話相手がいません")
        return

    default_target = st.session_state.selected_chat_target
    if default_target not in other_players:
        default_target = other_players[0]

    target = st.selectbox(
        "対話相手",
        other_players,
        index=other_players.index(default_target),
        key="chat_target_select",
        format_func=lambda p: (
            f"{p}（{game.personalities[p].character_name}）"
            if p in game.personalities else p
        )
    )
    st.session_state.selected_chat_target = target

    # ----------- 個性表示 -----------
    p = game.personalities.get(target)
    if p:
        st.caption(f"**{p.character_name}** — {p.backstory}")

    # ----------- 関係値 -----------
    rel_val = game.relationships.get(human, {}).get(target, 0)
    render_relationship_meter(rel_val)

    # 同盟表示
    ally = game.alliances.get(human)
    if ally == target:
        st.success("🤝 同盟中")
    elif ally:
        st.caption(f"現在の同盟: {ally}")

    st.markdown("---")

    # ----------- 会話ログ -----------
    st.markdown("**💬 会話ログ**")
    render_chat_history(human, target)

    st.markdown("")

    # ----------- テキスト入力 -----------
    user_input = st.text_input(
        "メッセージを入力",
        key=f"chat_input_{st.session_state.chat_input_key}",
        placeholder="自由に話しかけよう...",
        label_visibility="collapsed"
    )
    if st.button("送信 →", use_container_width=True):
        if user_input.strip():
            handle_chat_action(target, user_input)

    # ----------- 定型文アクション -----------
    st.markdown("**アクション:**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👀 観察する", use_container_width=True):
            handle_observe(target)
        if st.button("🎯 ズルしてるよね", use_container_width=True):
            handle_accuse(target)
    with col2:
        if st.button("🤝 同盟を組もう", use_container_width=True):
            handle_cooperate(target)
        if game.alliances.get(human) == target:
            if st.button("⚔️ 同盟を破棄", use_container_width=True):
                handle_break_alliance(target)
        else:
            if st.button("❓ 何考えてるの？", use_container_width=True):
                handle_chat_action(target, "ねえ、今何考えてるの？")

    # ----------- 情報メモ -----------
    with st.expander("📋 ゲームログ"):
        if st.session_state.game_log:
            for log in reversed(st.session_state.game_log[-15:]):
                st.text(log)
        else:
            st.caption("ログはありません")

    with st.expander("📝 判明した情報"):
        revealed = game.info_revealed.get(human, [])
        if revealed:
            for info in reversed(revealed[-8:]):
                st.caption(f"• {info}")
        else:
            st.caption("まだ情報はありません")

    with st.expander("📓 個人メモ"):
        note = st.text_area(
            "自由メモ",
            value=st.session_state.player_notes.get("Player 1", ""),
            key="player_note_area",
            label_visibility="collapsed",
            height=80
        )
        st.session_state.player_notes["Player 1"] = note


# -----------------------------------------------------------------------
# メイン
# -----------------------------------------------------------------------

def main():
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
        - ズル成功→ゲーム効果発動
        - ズルバレ→最下位確定
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

    if st.session_state.game is None:
        st.info("ゲームを開始するには、サイドバーで設定をしてください。")
        return

    game = st.session_state.game

    # 2カラムレイアウト
    left_col, right_col = st.columns([7, 3])

    with left_col:
        render_game_status()

        if game.game_state == GameState.CHEAT_PHASE:
            render_cheat_phase()
        elif game.game_state == GameState.PLAYING:
            render_player_hand_and_action()
            current_player = game.get_current_player()
            if current_player != "Player 1":
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
                st.write(f"{medals[idx] if idx < len(medals) else '　'} 第{idx + 1}位: {player}{caught_mark}")

    with right_col:
        render_right_panel()


if __name__ == "__main__":
    main()
