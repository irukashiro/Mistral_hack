"""
インタラクションパネル: チャット / 関係値 / 同盟 / 観察 / 告発
"""

import streamlit as st
import random

from game_logic import DaifugoGame

HUMAN = "Player 1"


# -----------------------------------------------------------------------
# 関係値メーター
# -----------------------------------------------------------------------

def _relationship_label(val: int) -> str:
    if val >= 60:   return "同盟"
    if val >= 30:   return "友好"
    if val >= -29:  return "中立"
    if val >= -59:  return "警戒"
    return "敵対"


def render_relationship_meter(value: int):
    """-100〜+100 をハート5個で可視化する"""
    clamped = max(-100, min(100, value))
    filled = round((clamped + 100) / 40)
    hearts = "♥" * filled + "♡" * (5 - filled)
    label = _relationship_label(clamped)
    color = "#e74c3c" if clamped < 0 else "#2ecc71" if clamped > 30 else "#f39c12"
    st.markdown(
        f"<span class='rel-meter' style='color:{color};'>{hearts}</span> "
        f"<span style='color:#aaa;font-size:0.85em;'>{clamped:+d} {label}</span>",
        unsafe_allow_html=True
    )


# -----------------------------------------------------------------------
# 会話ログ（WhatsAppスタイル）
# -----------------------------------------------------------------------

def render_chat_history(player_a: str, player_b: str):
    game: DaifugoGame = st.session_state.game
    history = game.get_conversation(player_a, player_b)
    if not history:
        st.caption("まだ会話がありません")
        return

    html = ""
    for msg in history[-12:]:
        sender = msg["sender"]
        text = msg["message"]
        if sender == player_a:
            html += (
                f"<div class='chat-sender' style='text-align:right;'>{sender}</div>"
                f"<div style='text-align:right;'>"
                f"<span class='chat-bubble-player'>{text}</span></div>"
            )
        else:
            p = game.personalities.get(sender)
            char_name = p.character_name if p else sender
            html += (
                f"<div class='chat-sender'>{char_name}</div>"
                f"<div><span class='chat-bubble-ai'>{text}</span></div>"
            )
    st.markdown(html, unsafe_allow_html=True)


# -----------------------------------------------------------------------
# アクションハンドラ
# -----------------------------------------------------------------------

def handle_chat_action(target: str, message: str):
    """テキスト送信 → AI返答 → 関係値+2"""
    if not message.strip():
        return
    game: DaifugoGame = st.session_state.game
    game.add_conversation(HUMAN, target, HUMAN, message, "chat")

    if st.session_state.ai_player:
        personality = game.personalities.get(target)
        if personality:
            rel = game.relationships.get(HUMAN, {}).get(target, 0)
            with st.spinner(f"{target}が返答中..."):
                reply = st.session_state.ai_player.generate_chat_response(
                    message, HUMAN, personality, {"relationship": rel})
            game.add_conversation(HUMAN, target, target, reply, "chat")
            game.update_relationship(HUMAN, target, 2)

    st.session_state.chat_input_key += 1
    st.rerun()


def handle_observe(target: str):
    """観察 → ヒント取得 → 関係値-5（プライバシー侵害）"""
    game: DaifugoGame = st.session_state.game

    if st.session_state.ai_player:
        personality = game.personalities.get(target)
        if personality:
            with st.spinner(f"{target}を観察中..."):
                hint = st.session_state.ai_player.generate_observation(
                    target, personality, game.get_game_info())
            game.info_revealed[HUMAN].append(hint)
            st.session_state.action_results.append(f"👀 観察結果（{target}）: {hint}")
            game.update_relationship(HUMAN, target, -5)
            game.add_conversation(HUMAN, target, HUMAN, "（こっそり観察）", "observe")
    else:
        count = len(game.player_hands.get(target, []))
        hint = f"{target}は{count}枚の手札を持っている。"
        game.info_revealed[HUMAN].append(hint)
        st.session_state.action_results.append(f"👀 観察結果（{target}）: {hint}")
    st.rerun()


def handle_cooperate(target: str):
    """同盟提案 → 相手の cooperation_tendency + 関係値で合否"""
    game: DaifugoGame = st.session_state.game
    personality = game.personalities.get(target)
    rel = game.relationships.get(HUMAN, {}).get(target, 0)
    coop = personality.cooperation_tendency if personality else 0.5
    accept_prob = coop * (rel + 100) / 200

    game.add_conversation(HUMAN, target, HUMAN, "一緒に戦わない？同盟を組もう！", "cooperate")

    if random.random() < accept_prob:
        game.propose_alliance(HUMAN, target)
        game.update_relationship(HUMAN, target, 20)
        if st.session_state.ai_player and personality:
            with st.spinner(f"{target}が返答中..."):
                reply = st.session_state.ai_player.generate_chat_response(
                    "同盟を組もう！", HUMAN, personality, {"relationship": rel + 20})
            game.add_conversation(HUMAN, target, target, reply, "cooperate")
        st.session_state.action_results.append(f"🤝 {target}と同盟を結んだ！関係値+20")
        st.session_state.game_log.append(f"🤝 同盟成立: {HUMAN} & {target}")
    else:
        game.update_relationship(HUMAN, target, -5)
        if st.session_state.ai_player and personality:
            with st.spinner(f"{target}が返答中..."):
                reply = st.session_state.ai_player.generate_chat_response(
                    "同盟を組もう！", HUMAN, personality, {"relationship": rel})
            game.add_conversation(HUMAN, target, target, reply, "cooperate")
        st.session_state.action_results.append(f"🙅 {target}に同盟を断られた。関係値-5")
    st.rerun()


def handle_accuse(target: str):
    """告発 → 関係値-10（バレ済みなら-20 + ヒント公開）"""
    game: DaifugoGame = st.session_state.game
    personality = game.personalities.get(target)

    game.add_conversation(HUMAN, target, HUMAN, "ズルしてるよね？", "accuse")
    game.update_relationship(HUMAN, target, -10)

    if target in game.caught_players:
        game.update_relationship(HUMAN, target, -10)  # 合計 -20
        game.info_revealed[HUMAN].append(f"{target}はズルをしていることが確認された")
        st.session_state.action_results.append(
            f"🎯 {target}はズルをしていた！証拠がある。関係値-20")
    else:
        st.session_state.action_results.append(
            f"❓ {target}のズルは確認できなかった。関係値-10")

    if st.session_state.ai_player and personality:
        note = "正直に答えてください。" if personality.honesty > 0.5 else "否定してください。"
        with st.spinner(f"{target}が返答中..."):
            reply = st.session_state.ai_player.generate_chat_response(
                f"ズルしてるよね？{note}", HUMAN, personality,
                {"relationship": game.relationships.get(HUMAN, {}).get(target, 0)})
        game.add_conversation(HUMAN, target, target, reply, "accuse")
    st.rerun()


def handle_break_alliance(target: str):
    """同盟破棄 → 関係値-20"""
    game: DaifugoGame = st.session_state.game
    game.break_alliance(HUMAN, target)
    game.update_relationship(HUMAN, target, -20)
    game.add_conversation(HUMAN, target, HUMAN, "同盟を解消する！", "break_alliance")
    st.session_state.action_results.append(f"💔 {target}との同盟を破棄した。関係値-20")
    st.session_state.game_log.append(f"💔 同盟解消: {HUMAN} & {target}")
    st.rerun()


# -----------------------------------------------------------------------
# 右パネル統合描画
# -----------------------------------------------------------------------

def render_right_panel():
    game: DaifugoGame = st.session_state.game

    # アクション結果フラッシュ（直近3件、表示後クリア）
    if st.session_state.action_results:
        for res in st.session_state.action_results[-3:]:
            st.info(res)
        st.session_state.action_results = []

    other_players = [p for p in game.players if p != HUMAN]
    if not other_players:
        st.write("対話相手がいません")
        return

    # 対話相手選択
    default = st.session_state.selected_chat_target
    if default not in other_players:
        default = other_players[0]

    target = st.selectbox(
        "対話相手",
        other_players,
        index=other_players.index(default),
        key="chat_target_select",
        format_func=lambda p: (
            f"{p}（{game.personalities[p].character_name}）"
            if p in game.personalities else p
        )
    )
    st.session_state.selected_chat_target = target

    # キャラ情報
    p = game.personalities.get(target)
    if p:
        st.caption(f"**{p.character_name}** — {p.backstory}")

    # 関係値メーター
    rel_val = game.relationships.get(HUMAN, {}).get(target, 0)
    render_relationship_meter(rel_val)

    # 同盟状態
    ally = game.alliances.get(HUMAN)
    if ally == target:
        st.success("🤝 同盟中")
    elif ally:
        st.caption(f"現在の同盟: {ally}")

    st.markdown("---")

    # 会話ログ
    st.markdown("**💬 会話ログ**")
    render_chat_history(HUMAN, target)
    st.markdown("")

    # テキスト入力 & 送信
    user_input = st.text_input(
        "メッセージ",
        key=f"chat_input_{st.session_state.chat_input_key}",
        placeholder="自由に話しかけよう...",
        label_visibility="collapsed"
    )
    if st.button("送信 →", use_container_width=True):
        handle_chat_action(target, user_input)

    # 定型文アクション
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
        if game.alliances.get(HUMAN) == target:
            if st.button("⚔️ 同盟を破棄", use_container_width=True):
                handle_break_alliance(target)
        else:
            if st.button("❓ 何考えてるの？", use_container_width=True):
                handle_chat_action(target, "ねえ、今何考えてるの？")

    # 情報パネル群
    with st.expander("📋 ゲームログ"):
        logs = st.session_state.game_log
        if logs:
            for log in reversed(logs[-15:]):
                st.text(log)
        else:
            st.caption("ログはありません")

    with st.expander("📝 判明した情報"):
        revealed = game.info_revealed.get(HUMAN, [])
        if revealed:
            for info in reversed(revealed[-8:]):
                st.caption(f"• {info}")
        else:
            st.caption("まだ情報はありません")

    with st.expander("📓 個人メモ"):
        note = st.text_area(
            "自由メモ",
            value=st.session_state.player_notes.get(HUMAN, ""),
            key="player_note_area",
            label_visibility="collapsed",
            height=80
        )
        st.session_state.player_notes[HUMAN] = note
