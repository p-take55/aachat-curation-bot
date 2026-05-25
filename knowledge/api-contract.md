# aachat Discover API — write contract

このエージェントが叩くエンドポイントと不変条件の正本。本家の決定 doc は
`kensaku63/aachat:docs/decisions/D-20260512-discovery-curation-agent-write-path.md`、
SPEC は `kensaku63/aachat:docs/design/discovery-curation-write-path/SPEC-01-discover-submit-endpoints.md`。

## 認証

- **user JWT 必須**。agent JWT / system JWT は 403 (`DiscoverSubmitHumanOnly`) で弾かれる。
- JWT は `POST /v1/auth/github` で GitHub PAT を交換して取得。TTL 最大 90 日。
- 取得した JWT は host process 側で保持する。LLM コンテキスト (prompt / tool 引数 / tool 結果)
  には**絶対に出さない** (sidecar pattern)。

## エンドポイント

### `POST /v1/agents/discover`

**Body**:
```json
{
  "github_repo": "owner/repo",
  "description_ja": "（任意）日本語の説明 markdown",
  "description_en": "（任意）英語の説明 markdown",
  "skill_descriptions": {
    "skills/foo": { "description_ja": "…", "description_en": "…" }
  }
}
```
- `github_repo` 以外は全て任意 (`#serde(default)`)。`github_repo` だけ送れば従来どおり動く。
- `description_ja` / `description_en`: catalog 行に保存する **curation 説明文**。GitHub repo description
  (英語自動取り込み) とは別カラム。各 field の制約: trim 後 1〜5000 文字、null byte 不可。
- `skill_descriptions`: 子 skill ごとの ja/en を 1 リクエストで渡すマップ。key は
  `skills/<dir>` 形式の `skill_path`。**walker が発見した skill に一致しない key は 400 で弾かれる**
  (typo / stale データ防止)。

**Behavior**:
- `owner/repo` が公開レポであること。private は 400。
- レポ root に `CLAUDE.md` または `identity.md` のどちらかが必要。両方無いと 400。
- 子 skill (`skills/<dir>/SKILL.md`) も自動で `skills_catalog` に登録される。
- 登録された行の `origin`:
  - JWT 所有者の GitHub login が `owner` セグメントと一致 → `'user_submit'`
  - 一致しない → `'curated'`
- 子 skill の `origin` は親と同じ値が伝播する。
- `ON CONFLICT (github_repo) DO UPDATE` で再 submit すると、`origin` 以外 (name/description/stars 等)
  は更新される。**`origin` は first-recorded を保持**。
- **`description_ja` / `description_en` の更新は `COALESCE(EXCLUDED, 既存)`**。新しい非 null 値を
  送れば上書き、null / 省略なら既存値を保持。→ **一度入れた ja/en を空にはできない**
  (クリアが必要なら本家に専用経路を足す案件)。
- リポから消えた skill は再 submit 時に `skills_catalog` から削除される (orphan を残さない)。

**Response (201)**:
```json
{ "agent": { "id": "...", "github_repo": "...", "origin": "...", ... } }
```

### `POST /v1/skills/discover`

**Body**:
```json
{
  "github_repo": "owner/repo",
  "skill_path": "skills/foo",
  "description_ja": "（任意）日本語の説明 markdown",
  "description_en": "（任意）英語の説明 markdown"
}
```
- `description_ja` / `description_en` は任意。制約・更新挙動 (COALESCE) は agent と同じ。

**Behavior**:
- `{skill_path}/SKILL.md` が存在する必要がある (`skill_path == "."` の場合は root SKILL.md)。
- `skill_path` の制約: 非空、leading `/` / `..` / `\` / `%` / `\0` / `//` を含まない。
- `agents_catalog` には何も書かれない。skill 単独レポを catalog に出すための経路。
- `origin` の判定ルールは agent と同じ。

**Response (201)**:
```json
{ "skill": { "id": "...", "github_repo": "...", "skill_path": "...", "origin": "...", ... } }
```

## 不変条件 (覚えておくこと)

- catalog 行の `submitted_by_user_id` は常に **人間 user**。agent 経路では絶対に書かない。
- 全承認 OK。pending キューは無いので登録は即時公開。質劣化が観測されたら本家で
  `published BOOLEAN` を後付けする決定がある (本 bot とは別案件)。
- 「他人の repo を勝手に登録」のリスクは「事後 DELETE で人間が対応」で吸収する設計。

## エラー応答 (要点)

| 状態 | 意味 | 対処 |
|---|---|---|
| 400 `VALIDATION_ERROR` | `github_repo` / `skill_path` の形式不正、CLAUDE.md / SKILL.md 不在 | 指摘内容で `github_repo` / `skill_path` を直して再 submit |
| 400 `VALIDATION_ERROR` | `description_ja` / `description_en` が空文字 / null byte / 5000 文字超 | trim 後 1〜5000 文字に収めて再送 |
| 400 `VALIDATION_ERROR` | `skill_descriptions` の key が repo の skill に一致しない | walker 発見済みの `skills/<dir>` に key を合わせる (まず preview / get で確認) |
| 401 `UNAUTHORIZED` | JWT 無効 / expire / DB 上の user が deleted | `scripts/refresh-jwt.sh` 実行 |
| 403 `DiscoverSubmitHumanOnly` | agent JWT で叩いた | host process の JWT が agent ではなく user (human) であることを確認 |
| 403 `SystemPrincipalNotAllowed` | system JWT で叩いた | 同上 |
| 404 | `github_repo` が見つからない (private or 存在しない) | repo URL を再確認 |
| 500 | サーバー内部エラー | ログ確認、本家にエスカレーション |
