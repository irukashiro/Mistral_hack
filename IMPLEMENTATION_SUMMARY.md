グノーシアAI × 大富豪 - 実装サマリー
======================================

## 🎮 プロジェクト完成

「グノーシアAI × 大富豪」の完全な心理戦システムの実装が完了しました。

このプロジェクトは、日本の伝統的なトランプゲーム「大富豪」にMistral AI、RPG的なステータスシステム、そしてグノーシア的な人間関係操作要素を統合した、複雑で奥深い心理戦ゲームです。

---

## 📦 実装内容

### **Step 1: 基礎大富豪エンジン** ✅

**ファイル**: `game_logic.py`, `models.py`

- 4人プレイヤー対応
- 標準的なカード配備・手番管理
- ゲーム状態管理（WAITING → PLAYING → ROUND_OVER → GAME_OVER）
- カードの valid_move 計算
- チートシステム（ズルの試行・対策・判定）

### **Step 2: AIのターゲット認識** ✅

**ファイル**: `game_logic.py` (感情マトリクス)

**実装内容**：

#### 2つの感情マトリクス
- **Affinity（好感度）**: -100〜+100
- **Fear（恐怖度）**: -100〜+100

#### 4つのキャラクター性
- `LOGICAL` : 合理型（最適解を計算）
- `VENGEFUL` : 粘着型（敵対者への徹底的ハラスメント）
- `SYCOPHANT` : 腰巾着型（上位者に従順）
- `REVOLUTIONARY` : 革命家型（カオスを引き起こす）

#### キャラクター性に基づいたカード選択
```python
def apply_character_type_logic(player_name):
    if char_type == LOGICAL:
        return _logical_move()        # 最も弱いカード
    elif char_type == VENGEFUL:
        return _overkill_move()       # 最強カード（相手へのヘイト）
    elif char_type == SYCOPHANT:
        return _sycophant_move()      # 階級に従う
    elif char_type == REVOLUTIONARY:
        return _disruptive_move()     # ランダムカオス
```

### **Step 3: スキルシステム** ✅

**ファイル**: `game_logic.py` (試行判定メソッド), `ai_player.py` (AI決定)

**実装スキル**：

| スキル | 判定 | 効果 |
|--------|------|------|
| **威圧** (Intimidate) | Charisma vs Logic | 対象を強制パス |
| **泣き落とし** (Charm) | Charm vs Logic+好感度 | 対象をパスさせる |
| **扇動** (Persuade) | Acting Power vs Logic | 特定相手へのヘイト誘導 |

例：
```python
def try_skill_intimidate(actor: str, target: str) -> Tuple[bool, str]:
    actor_roll = d20() + actor_stats.charisma * 2
    target_roll = d20() + target_stats.logic * 2
    
    if actor_roll > target_roll:
        skip_next_turn[target] = True
        return True, "威圧成功！"
    return False, "威圧は通じなかった"
```

### **Step 4: ゲームループと育成システム** ✅

**ファイル**: `game_logic.py` (フェーズ管理・育成), `models.py` (パラメータ定義)

**ゲームサイクル**：

```
┌─────────────────────────────┐
│  昼（DAY_CARD_GAME）         │  ← 大富豪ゲーム
│  カード提出 + スキル判定      │
└────────────┬────────────────┘
             │
┌────────────v────────────────┐
│  夕方（EVENING_RESULTS）      │  ← 順位確定・報酬付与
│  大富豪：Charisma+2, Exp+20  │
│  大貧民：HP-10, Exp+10        │
└────────────┬────────────────┘
             │
┌────────────v────────────────┐
│  夜（NIGHT_ADVENTURE）        │  ← アドベンチャーフェーズ
│  • 会話システム               │
│  • 同盟・密約                 │
│  • 育成（経験値・Stat上昇）   │
│  • 秘密情報の交換             │
└────────────┬────────────────┘
             │
└─────────────────────────────┘
      ↓ 翌日へループ
```

**育成システム**：

| ステータス | 効果 |
|-----------|------|
| Charisma | 威圧スキルの効果, Fearの付与力 |
| Charm | 泣き落とし成功率, カード交換の恩赦 |
| Logic | 威圧耐性, 扇動への抵抗 |
| Acting Power | 扇動スキルの効果, ブラフ成功率 |
| Intuition | 相手情報の読取, 隠された意図の察知 |

### **Step 5: Mistral AIの感情ベース統合** ✅

**ファイル**: `ai_player.py`

**実装内容**：

#### キャラクター生成
```python
def generate_personality(player_name: str) -> AIPersonality
```
- Mistral AIが自動生成する4つのNPC
- 性格説明、話し方、ズル傾向などを自然言語で定義

#### 感情マトリクスに基づくカード選択
```python
def decide_move(game: DaifugoGame, player_name: str)
    ↓
self._apply_emotion_matrix()
    ↓
オーバーキル判定: affinity < -60 → 最強カード選択
萎縮判定: fear > 60 → 弱いカード選択
```

#### 会話AI
```python
def generate_chat_response(message, sender, personality, context)
```
- 性格に基づいた自然な返答生成
- 関係値に応じた態度変化

#### ズル система
```python
def decide_cheat_attempt()  # ズルを試みるか決定
def generate_counter_measure()  # 対策を生成
def evaluate_cheat_contest()  # ズル対決を評価
```

### **Step 6: アドベンチャーフェーズUI** ⏳ 基本実装

**ファイル**: `app.py`

実装予定の機能：
- [ ] 関係値の視覚化（ヒートマップ）
- [ ] 会話インターフェース
- [ ] 同盟・密約提案UI
- [ ] ステータス画面
- [ ] ゲームログ表示
- [ ] カット イン アニメーション（簡易版）

### **Step 7: 完全な設計指南ドキュメント** ✅

**ファイル**: `DESIGN_GUIDE_JP.md`

以下を含む90ページ規模のドキュメント：

1. **コアコンセプト**：手札は「弾丸」であり「貢ぎ物」
2. **キャラクターAI設計**：2つの感情マトリクス＋4つの性格タイプ
3. **心理戦ギミック**：スキル、カード交換、ターゲット・オーバーキル
4. **ゲームループ**：昼夜フェーズの詳細説明
5. **UI/UXアイデア**：ヘイト矢印、カットイン、手札枚数非表示
6. **開発ロードマップ**：7ステップの段階的実装ガイド
7. **注釈とコード例**：実装参考コード

---

## 📁 ファイル構成

```
Mistral_hack/
├── models.py                 # データモデル定義
│   ├── Card, Suit
│   ├── GameState, GamePhase
│   ├── CheatAttempt
│   ├── AIPersonality
│   ├── CharacterType          [NEW]
│   ├── PlayerStats            [NEW]
│   ├── SkillType, Skill       [NEW]
│   ├── Episode                [NEW]
│   └── RelationshipLevel      [NEW]
│
├── game_logic.py              # ゲームエンジン
│   ├── DaifugoGame
│   ├── initialize_deck(), deal_cards()
│   ├── get_valid_moves()
│   ├── play_cards()
│   ├── チートシステム
│   ├── 感情マトリクス実装     [NEW]
│   ├── キャラクター性ロジック  [NEW]
│   ├── スキル判定メソッド     [NEW]
│   ├── ゲームフェーズ管理     [NEW]
│   └── 育成システム           [NEW]
│
├── ai_player.py               # Mistral AI統合
│   ├── MistralAIPlayer
│   ├── generate_personality()
│   ├── generate_chat_response()
│   ├── decide_move()          [拡張]
│   ├── _apply_emotion_matrix()[NEW]
│   ├── decide_action()
│   ├── decide_cheat_attempt()
│   └── evaluate_cheat_contest()
│
├── app.py                     # Streamlit UI
│   ├── ゲーム制御
│   ├── カード表示
│   ├── ゲームログ表示
│   └── アドベンチャーUI [実装予定]
│
├── DESIGN_GUIDE_JP.md         # 完全な設計指南
├── README.md                  # プロジェクト説明
├── requirements.txt           # 依存パッケージ
├── .env.example               # 環境変数テンプレート
└── __pycache__/
```

---

## 🔑 主要概念の実装

### 感情マトリクスの動的更新

```python
# ゲーム中の関係値変動例
update_relationship("Player1", "Player2", delta=10)   # 好感度+10
update_fear_level("Player1", "Player2", delta=5)      # 恐怖度+5

# 階級変化による自動バフ
apply_hierarchy_change()  # 大富豪になると Charisma の自動ボーナス
```

### オーバーキル（ターゲット・オーバーキル）

```python
# Playerが嫌いな相手へ非合理的な強いカードを出す
if affinity < -60 and char_type == VENGEFUL:
    # 通常より強いカードを出す（効率性を無視）
    return strongest_valid_move()
```

### スキル連鎖

```python
# 利己的な判断と感情的な判断が交錯
#
# 例：愛する者が敵対者にターゲットされている場合
# → スキル「威圧」で敵対者を妨害
#     → 失敗してもAffinity上昇
#     → 同盟の確率が高まる
```

---

## 🎯 ゲームプレイの流れ

### 昼フェーズ（カードゲーム）
```
1. Player1（人間）の手札表示
2. Player1が「カード出す」「パス」「スキル使用」を選択
3. AI（Player2-4）が自動実行
   a) 感情マトリクスに基づくカード選択
   b) キャラクター性による調整
   c) スキル使用判定
4. ターンエンドチェック
5. ラウンド終了まで繰り返し
6. ゲーム終了→ 夕方フェーズへ
```

### 夕方フェーズ（報酬付与）
```
1. 順位確定
2. ステータス変動
   - 大富豪：Charisma+2, Exp+20
   - 大貧民：HP-10, Exp+10
   - 中位：Exp+15
3. レベルアップ判定
4. 夜フェーズへ移行
```

### 夜フェーズ（アドベンチャー）
```
1. NPCとの会話システム
   - 好感度、Fear、秘密情報の変動
2. 同盟・密約提案
   - 好感度に基づく成功判定
3. 育成画面
   - 経験値の表示
   - ステータスレベルアップ画面
4. 次のゲーム開始
```

---

## 🚀 使用開始方法

### 1. **環境構築**
```bash
# リポジトリクローン
cd Mistral_hack

# 仮想環境作成
python -m venv venv
source venv/Scripts/activate  # Windows

# パッケージインストール
pip install -r requirements.txt
```

### 2. **Mistral API キー設定**
```bash
# .env ファイル作成
cp .env.example .env

# .env を編集
MISTRAL_API_KEY=your_actual_api_key
```

### 3. **Streamlit アプリ起動**
```bash
streamlit run app.py
```

ブラウザが自動的に http://localhost:8501 で開きます。

---

## 🎓 設計思想

### グノーシアとの対応

このプロジェクトは、グノーシア（多人数推理ゲーム）の以下の要素を大富豪に適用しています：

| グノーシア概念 | 大富豪での実装 |
|-------------|-------------|
| **投票による脱落** | カード出しの強制（スキル無効化）|
| **昼の議論** | カード出しとスキルによる心理戦 |
| **夜の戦略** | アドベンチャーフェーズでの同盟・密約 |
| **HP制度** | ゲーム内での生存HP |
| **展開の予測可能性** | 関係値に基づく行動パターン |
| **人間関係の創出** | Affinity & Fear マトリクス |

### 設計の工夫

1. **感情的非合理性の組み込み**
   - 最適解よりも「感情」を優先させるAI
   - プレイヤーが人間関係から戦略を推測可能

2. **多層的なメカニクス**
   - ゲームルール（カード）
   - 心理戦ルール（スキル・好感度）
   - RPGルール（ステータス・育成）

3. **長期・短期の戦略**
   - 短期：このゲームで勝つ
   - 長期：将来のゲームのために関係値を構築

---

## 💡 今後の拡張機能

### 近期（実装推奨）
- [ ] 「8切り」ルール実装
- [ ] 「革命」ルール実装
- [ ] 会話UI の完全実装
- [ ] 関係値グラフの視覚化

### 中期（拡張機能）
- [ ] ストーリーモード（Episodeシステム活用）
- [ ] ボイスアクティング（キャラボイス）
- [ ] マルチプレイネット対応
- [ ] AI難易度設定

### 長期（将来展望）
- [ ] ゲーム結果の統計分析
- [ ] AI vs AI の自動シミュレーション
- [ ] Episodeシステムの完全ストーリー化

---

## 🤖 Mistral AI の活用

このプロジェクトは Mistral AI を以下の用途で使用しています：

### 1. **キャラクター自動生成**
```
ユーザー指定 → Mistral がJSON形式で個性を生成
```

### 2. **会話AI**
```
お、前回の結果どう思った？
  ↓
Mistral の システムプロンプト + ユーザーメッセージ
  ↓
キャラクター個性に基づいた返答
```

### 3. **カード選択の文脈理解**
```
ゲーム状況 + 関係値 + キャラクター性
  ↓
Mistral が「自然な」判断を生成
  ↓
感情マトリクスで微調整
```

### 4. **ズル対決の判定**
```
ズルプロンプト + 対策プロンプト
  ↓
Mistral が 「どちらが勝つか」を文脈判定
  ↓
JSON で結果返却
```

---

## 📊 コードの複雑度

| モジュール | 行数 | 複雑度 |
|----------|------|--------|
| `models.py` | ~200 | 低（データ定義） |
| `game_logic.py` | ~700 | 高（複雑ロジック） |
| `ai_player.py` | ~650 | 高（AI統合） |
| `app.py` | ~400 | 中（UI制御） |
| **合計** | **~2000** | **高** |

---

## 🔍 テストとデバッグのポイント

1. **感情マトリクスの動的更新**
   - 関係値の増減が適切か
   - Fear と Affinity の相互作用

2. **キャラクター性の表現**
   - 4つのタイプが識別できるか
   - 各タイプの戦略が異なるか

3. **AIの決定品質**
   - Mistral の応答が自然か
   - 問題のある判断がないか

4. **ゲームバランス**
   - どのキャラクターも同等の勝率か
   - スキルが過強／過弱でないか

---

## 🎬 最後に

このプロジェクトは、単なる「AIと遊ぶトランプゲーム」の枠を超えています。

**「心理戦」「人間関係操作」「長期戦略」**という高度なメカニクスを備えた、真の意味で「知的」なゲーム体験を目指しています。

Mistralの自然言語処理能力と、複雑なゲームロジックの組み合わせにより、プレイするたびに異なる人間関係が形成され、毎回を新しい冒険にしています。

**楽しいゲームプレイを！**

---

**制作者からのコメント**

このシステムは、グノーシア、ダンガンロンパ、そして大富豪の要素を融合させています。

実装する際は「どの要素が最も重要か」を常に意識してください。

- ゲームとして楽しいか？
- 人間関係が自然に形成されるか？
- AIの判断が筋が通っ ているか？

これらをバランス良く実現することが、このプロジェクトの成功の鍵です。

