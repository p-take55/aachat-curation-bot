# 登録ポリシー

## どんなレポを登録するか

### Agent (`/v1/agents/discover`)

最低条件:
- 公開レポであること
- root に `CLAUDE.md` または `identity.md` のどちらかが存在する
- 過去 6 ヶ月以内に push がある (`github_pushed_at`)
- 著者名 (`author_login`) が現存する GitHub アカウントである

質の判断 (任意、保守的に):
- README が日本語/英語のどちらかで意味の取れる説明をしている
- 明らかな spam / 自動生成 / fork-only でない
- 著者が aachat ユーザーから報告 / 推薦されている (X / GitHub Issues 等)
- スター数は判断材料の一つ。0 でも有用なら OK

### Skill (`/v1/skills/discover`)

最低条件:
- 公開レポであること
- `{skill_path}/SKILL.md` が存在する (`skill_path == "."` で root 可)
- SKILL.md に最低限 frontmatter (name / description) がある

## origin の使い分け

| 状況 | API が付ける `origin` | 意図 |
|---|---|---|
| JWT 所有者 == repo の owner | `user_submit` | 「著者が自分の repo を出した」 |
| JWT 所有者 != repo の owner | `curated` | 「運営が良いものを拾った」 |

このエージェントは基本 kensaku63 / p-take55 の JWT で動くので、ほぼ常に `curated` になる。
著者本人が自分で登録するのは WebUI 経由になる (SPEC-02、別 PR で実装予定)。

## 登録の流れ (このエージェントが判断するとき)

1. 候補レポを得る
   - X 検索 (`#claude-skills`, `aachat`, 等)
   - GitHub topic (`claude-skills`, `claude-code`)
   - 既存登録の author の他レポ
2. 上の「最低条件」を機械的にチェック
3. 「質の判断」基準で目視 (LLM が短い yes/no で判断)
4. yes → `register_agent` / `register_skill` 実行
5. no → `memory/skipped.md` に repo URL + 理由を記録 (重複拾い防止)

## 登録しない例

- private repo
- archived repo
- `CLAUDE.md` / `identity.md` / `SKILL.md` を含まない
- README が空 / "TODO" だけ / 機械翻訳の繰り返し
- 同じ author が短期間に大量に submit している
- 既に `agents_catalog` / `skills_catalog` に存在する (再 submit で origin が curated に上書きされないので無害だが、無駄なので skip)

## 削除依頼が来たら

このエージェントは DELETE 経路を持たない。SQL で kensaku63 / p-take55 が手で対応する:

```sql
DELETE FROM agents_catalog WHERE github_repo = 'owner/repo';
DELETE FROM skills_catalog WHERE github_repo = 'owner/repo';
```

`ON CASCADE` で votes / comments も削除される (テーブル定義済み)。

## 効用文 (headline) の書き方 — スキル必須運用

スキルの submit には `headline_ja` / `headline_en` を必ず付ける (API 上は任意だが運用必須)。
カタログの見出しはスキル生名ではなく効用文が主役になる (aachat PR #620 以降)。

- 「このスキルで何ができるようになるか」を動詞止めの1文で。例: `brainstorming` → 「曖昧な仕様を言語化する問いを出す」
- 全角24字以内目安 (カードで1行)。60字を超えると 400
- スキル生名の再掲・言い換えだけは禁止 (「ブレインストーミングをする」は不合格)
- 修正は新しい文で再 submit (COALESCE のため NULL には戻せない。description と同じ制約)

## タグの付け方

タグは Discover の棚・タイル・カードバッジの源泉。`tags: [{key, label_ja, label_en}]` で送る。

- key: lowercase kebab (`^[a-z0-9][a-z0-9-]{0,31}$`)、最大20個、重複禁止。GitHub topics は概ねそのまま使えるが、必ずこの形式に正規化してから送る
- **配列の順序 = 重要度**。先頭1〜2個がカードのバッジに出る。最重要の職能タグを先頭に
- 新しい key には `label_ja` / `label_en` を必ず付ける (ラベル未登録のタグは UI に生 key が出る)。既存 key はラベル省略可 (COALESCE)
- 置換セマнティクスの罠: **省略 = 既存維持 / `[]` = クリア / 配列 = 全置換**。部分追加はできないので、更新時は完成形の配列を送る
- 参考語彙 (旧カテゴリ体系から継承): engineering / marketing / design / administration / research / review / testing / sre / seo / sns / copywriting / meeting / accounting / support など。乱造せず、既存タグ (`GET /v1/discover/tags`) を先に確認して寄せる

## 依存 (deps) の申告 — スキル

SKILL.md を読み、スキルが前提にする外部ツールを `deps: [{kind: "cli"|"mcp", name}]` で申告する。

- kind は 2 値のみ。name はツールの一般名 (例: `jq`, `tavily`, `playwright`)。インストールコマンドは書かない
- 省略 = 既存維持 / `[]` = クリア / 配列 = 全置換

## 埋め戻し (backfill) runbook

契約追加後の既存行に効用文・タグラベル・deps を行き渡らせる手順:

1. `GET /v1/discover/tags?limit=100` でラベル未登録 (label_ja が null) の key を確認
2. `GET /v1/agents/discover` / `GET /v1/skills/discover` を offset で走査し、headline_ja が null のスキル・タグが空/未整備の行をリストアップ
3. 各 repo を register_agent / register_skill で再 submit (効用文・タグ+ラベル・deps を添えて)。専用バッチ・専用 API は無い — 再 submit が唯一の管理経路

## サムネイル生成 — プロジェクトテンプレート

テンプレートのサムネは aachat 本体リポジトリの `dev/thumbnail-kit/` で生成する
(部品CSS + レンダラ + runbook が自己完結。詳細は同ディレクトリの README.md と PATTERNS.md)。

1. 実行環境: node 22 + `npm install` + `npx playwright install chromium` (kit ディレクトリ内)
2. `GET /v1/discover/project-templates/{slug}` でメタデータ取得 → PATTERNS.md の型を選び kit.css の部品だけで HTML を組む
3. `node render.mjs work/<slug>.html work/<slug>.png` — センタリング逸脱と外部アイコン404の警告をゼロにする
4. `PUT /v1/admin/project-templates/{slug}/thumbnail` (Content-Type: image/png, ≤2MB) でアップロード。**admin 権限の JWT が必要** (通常の curation JWT とは別。kensaku に発行を依頼)
5. 再生成は同じ手順 (内容ハッシュ入りキーで新URLに置き換わる)
