"""
ゲームUI: ステータス表示 / 手札 & アクション / AIターン
"""

import streamlit as st
import time as time_module
import random

from game_logic import DaifugoGame, GameState


def render_game_status():
    """ゲーム状態・プレイヤー情報テーブルを描画"""
    game: DaifugoGame = st.session_state.game
    info = game.get_game_info()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("現在のプレイヤー", info['current_player'])
    with col2:
        st.metric("ゲーム状態", info['game_state'].value)
    with col3:
        field = ", ".join(str(c) for c in info['last_played']) if info['last_played'] else "なし（自由に出せる）"
        st.metric("場のカード", field)

    st.markdown("---")
    st.subheader("プレイヤー情報")

    rows = []
    for player in game.players:
        p = game.personalities.get(player)
        char_name = p.character_name if p else player
        is_current = "👈 現在" if player == info['current_player'] else ""
        rank_str = f"第{info['ranking'].index(player) + 1}位" if player in info['ranking'] else ""
        caught_str = "🚨 バレ" if player in info.get('caught_players', []) else ""
        ally = game.alliances.get(player)
        ally_str = f"🤝 {ally}" if ally else ""
        rows.append({
            "プレイヤー": f"{player}（{char_name}） {is_current}",
            "手札枚数": info['player_card_count'][player],
            "順位": rank_str,
            "状態": f"{caught_str} {ally_str}".strip()
        })
    st.dataframe(rows, use_container_width=True)


def render_player_hand_and_action():
    """手札表示 + カードプレイUI（Player 1用）"""
    game: DaifugoGame = st.session_state.game
    human = "Player 1"
    current_player = game.get_current_player()

    # peek（覗き見）の一時表示
    peek_target = st.session_state.cheat_phase_peek_target
    peek_time = st.session_state.cheat_phase_peek_time
    if peek_target and peek_time and (time_module.time() - peek_time) < 3.0:
        st.info(f"👀 **{peek_target}の手札を覗いています！**")
        peek_hand = sorted(game.player_hands.get(peek_target, []),
                           key=lambda c: c.get_rank_value())
        if peek_hand:
            st.markdown(f"**{peek_target}の手札**: {', '.join(str(c) for c in peek_hand)}")
    elif peek_target:
        st.session_state.cheat_phase_peek_target = None
        st.session_state.cheat_phase_peek_time = None

    hand = game.player_hands[human]
    st.subheader(f"{human}の手札")

    if not hand:
        st.success("上がり！手札がありません 🎉")
        return

    sorted_hand = sorted(hand, key=lambda c: c.get_rank_value())
    card_cols = st.columns(min(13, len(sorted_hand)))
    for idx, card in enumerate(sorted_hand):
        color = "red" if card.suit.value in ("♥", "♦") else "black"
        with card_cols[idx % 13]:
            st.markdown(
                f"<div class='card-display' style='text-align:center; color:{color};'>{card}</div>",
                unsafe_allow_html=True
            )

    st.markdown("")

    if current_player != human:
        st.info(f"⏳ {current_player} のターンです...")
        return

    selected_strs = st.multiselect(
        "出すカードを選択（複数枚同ランクも可）",
        [str(c) for c in sorted_hand],
        key=f"card_select_{st.session_state.card_select_key}"
    )
    selected_cards = [c for c in sorted_hand if str(c) in selected_strs]

    if selected_cards:
        if game.is_valid_move(selected_cards):
            st.success(f"✅ 有効な手: {', '.join(selected_strs)}")
        else:
            st.warning("⚠️ この組み合わせは無効です（同ランク・枚数・強さを確認）")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎯 カードを出す",
                     disabled=not selected_cards or not game.is_valid_move(selected_cards),
                     use_container_width=True):
            game.play_cards(human, selected_cards)
            st.session_state.game_log.append(
                f"{human}: {', '.join(str(c) for c in selected_cards)} を出した")
            st.session_state.card_select_key += 1
            st.rerun()
    with col2:
        if st.button("🚫 パス", use_container_width=True):
            game.play_cards(human, [])
            st.session_state.game_log.append(f"{human}: パス")
            st.session_state.card_select_key += 1
            st.rerun()


def play_ai_turn():
    """AIのターンを処理し、自発アクションを試みる"""
    from ai_player import MistralAIPlayer, make_random_move

    game: DaifugoGame = st.session_state.game
    current_player = game.get_current_player()
    if current_player == "Player 1":
        return

    valid_moves = game.get_valid_moves(current_player)

    if st.session_state.ai_player:
        try:
            move = st.session_state.ai_player.decide_move(game, current_player, valid_moves)
        except Exception as e:
            st.warning(f"AI決定エラー: {e}")
            move = make_random_move(valid_moves)
    else:
        move = make_random_move(valid_moves)

    game.play_cards(current_player, move)
    if move:
        st.session_state.game_log.append(
            f"{current_player}: {', '.join(str(c) for c in move)} を出した")
    else:
        st.session_state.game_log.append(f"{current_player}: パス")

    # 自発アクション（20%確率）
    if st.session_state.ai_player and game.game_state == GameState.PLAYING:
        _try_ai_spontaneous_action(game, current_player)


def _try_ai_spontaneous_action(game: DaifugoGame, ai_player_name: str):
    """AIがチャット・同盟・告発などを自発的に起こす"""
    action = st.session_state.ai_player.decide_action(game, ai_player_name)
    if not action:
        return

    target = action["target"]
    msg = action["message"]
    action_type = action["type"]
    p = game.personalities.get(ai_player_name)
    char_name = p.character_name if p else ai_player_name

    if action_type == "chat":
        game.add_conversation(ai_player_name, target, ai_player_name, msg, "chat")
        game.update_relationship(ai_player_name, target, 1)
        st.session_state.action_results.append(
            f"💬 {char_name}が{target}に話しかけた: 「{msg}」")
        st.session_state.game_log.append(f"💬 {char_name}→{target}: 「{msg}」")

    elif action_type == "cooperate":
        personality = game.personalities.get(ai_player_name)
        rel = game.relationships.get(ai_player_name, {}).get(target, 0)
        accept_prob = (personality.cooperation_tendency if personality else 0.5) * (rel + 100) / 200
        if random.random() < accept_prob:
            game.propose_alliance(ai_player_name, target)
            game.update_relationship(ai_player_name, target, 20)
            game.add_conversation(ai_player_name, target, ai_player_name, msg, "cooperate")
            st.session_state.action_results.append(f"🤝 {char_name}と{target}が同盟を結んだ！")
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
