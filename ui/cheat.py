"""
ズルフェーズUI: チート実行 / 結果表示 / AIズル処理
"""

import streamlit as st
import random
import time as time_module

from models import CheatAttempt
from game_logic import DaifugoGame, GameState


def render_cheat_result(result: dict):
    """ズル対決の結果を表示する"""
    attempt: CheatAttempt = result["attempt"]
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


def execute_cheat(game: DaifugoGame, attacker: str, target: str, cheat_prompt: str):
    """ズルを実行し、結果を記録してリロードする"""
    if not game.cheat_queue or game.cheat_queue[0] != attacker:
        return

    # 1. 対策生成
    counter_prompt = "カードをしっかり守る"
    if st.session_state.ai_player:
        with st.spinner(f"{target}が対策を考えています..."):
            counter_prompt = st.session_state.ai_player.generate_counter_measure(
                game, target, cheat_prompt)

    # 2. Mistral評価
    eval_result = {"cheat_bonus": 1, "counter_bonus": 1, "effect_type": "peek", "reasoning": ""}
    if st.session_state.ai_player:
        with st.spinner("Mistralが判定中..."):
            eval_result = st.session_state.ai_player.evaluate_cheat_contest(
                cheat_prompt, counter_prompt, game.get_game_info())

    # 3. 関係値ボーナス加算
    rel_bonus = game.get_relationship_bonus(attacker, target)
    cheat_bonus = eval_result.get("cheat_bonus", 0) + rel_bonus

    # 4. 2D6 ロール
    cheat_roll = random.randint(1, 6) + random.randint(1, 6)
    counter_roll = random.randint(1, 6) + random.randint(1, 6)
    cheat_total = cheat_roll + cheat_bonus
    counter_total = counter_roll + eval_result.get("counter_bonus", 0)
    success = cheat_total > counter_total
    effect_type = eval_result.get("effect_type", "peek")

    # 5. 記録
    attempt = CheatAttempt(
        attacker=attacker, target=target,
        cheat_prompt=cheat_prompt, counter_prompt=counter_prompt,
        cheat_bonus=cheat_bonus, counter_bonus=eval_result.get("counter_bonus", 0),
        cheat_roll=cheat_roll, counter_roll=counter_roll,
        success=success, effect_type=effect_type, caught=not success
    )
    game.cheat_attempts.append(attempt)

    # 6. 効果適用
    if success:
        game.apply_cheat_effect(attacker, target, effect_type)
        if effect_type == "peek":
            st.session_state.cheat_phase_peek_target = target
            st.session_state.cheat_phase_peek_time = time_module.time()
        game.update_relationship(attacker, target, -10)
    else:
        game.catch_cheater(attacker)

    # 7. ログ
    if success:
        st.session_state.game_log.append(
            f"🃏 {attacker}がズル成功！({effect_type}) vs {target} [{cheat_total}vs{counter_total}]")
    else:
        st.session_state.game_log.append(
            f"🚨 {attacker}がズルを見破られた！最下位に [{cheat_total}vs{counter_total}]")

    # 8. キューから削除
    if game.cheat_queue and game.cheat_queue[0] == attacker:
        game.cheat_queue.pop(0)

    st.session_state.cheat_result_display = {
        "attempt": attempt,
        "cheat_total": cheat_total,
        "counter_total": counter_total,
        "reasoning": eval_result.get("reasoning", "")
    }
    st.rerun()


def _process_ai_cheat(game: DaifugoGame, ai_player_name: str):
    """AIプレイヤーのズルターンを処理する"""
    if not st.session_state.ai_player:
        game.cheat_queue.pop(0)
        st.session_state.game_log.append(f"{ai_player_name}: ズルをスキップ（AI未設定）")
        st.rerun()
        return

    cheat_info = st.session_state.ai_player.decide_cheat_attempt(game, ai_player_name)
    if cheat_info:
        st.info(f"🤖 {ai_player_name} がズルを試みています...")
        execute_cheat(game, ai_player_name, cheat_info["target"], cheat_info["prompt"])
    else:
        game.cheat_queue.pop(0)
        st.session_state.game_log.append(f"{ai_player_name}: ズルを見送った")
        st.rerun()


def render_cheat_phase():
    """ズルフェーズ全体を描画する"""
    game: DaifugoGame = st.session_state.game

    if not game.cheat_queue:
        game.game_state = GameState.PLAYING
        game._next_player()
        st.rerun()
        return

    st.subheader("🃏 ズルフェーズ")
    st.caption("場がリセットされました。ズルのチャンスです！")

    if st.session_state.cheat_result_display:
        render_cheat_result(st.session_state.cheat_result_display)
        st.session_state.cheat_result_display = None

    current = game.cheat_queue[0]

    if current in game.caught_players or current in game.ranking:
        game.cheat_queue.pop(0)
        st.rerun()
        return

    st.info(f"**{current}** のズルチャンス（キュー残: {len(game.cheat_queue)}人）")

    if current != "Player 1":
        _process_ai_cheat(game, current)
        return

    # Player 1（人間）のUI
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
            execute_cheat(game, current, target, cheat_prompt)
    with col_b:
        if st.button("😇 見送る", use_container_width=True):
            game.cheat_queue.pop(0)
            st.session_state.game_log.append(f"{current}: ズルを見送った")
            st.rerun()
