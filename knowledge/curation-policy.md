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
