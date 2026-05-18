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
{ "github_repo": "owner/repo" }
```

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

**Response (201)**:
```json
{ "agent": { "id": "...", "github_repo": "...", "origin": "...", ... } }
```

### `POST /v1/skills/discover`

**Body**:
```json
{ "github_repo": "owner/repo", "skill_path": "skills/foo" }
```

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
| 401 `UNAUTHORIZED` | JWT 無効 / expire / DB 上の user が deleted | `scripts/refresh-jwt.sh` 実行 |
| 403 `DiscoverSubmitHumanOnly` | agent JWT で叩いた | host process の JWT が agent ではなく user (human) であることを確認 |
| 403 `SystemPrincipalNotAllowed` | system JWT で叩いた | 同上 |
| 404 | `github_repo` が見つからない (private or 存在しない) | repo URL を再確認 |
| 500 | サーバー内部エラー | ログ確認、本家にエスカレーション |
