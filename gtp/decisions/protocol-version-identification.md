## 未決定事項

配布するAgent Skillから、対応するprotocol versionをどう確認できるようにするか。

## 採用した手段

`skills/gtp/GTP.md`と`skills/gtp/SKILL.md`の両方にprotocol version `2.0`を表示する。独立した`skills/pre-submission-review/`はGTP protocol versionを表示しない。別のversion file、照合checker、CIは追加しない。

## 変更履歴

- [PR #155](https://github.com/shinya0x00/github-task-protocol/pull/155)で、利用projectへcopyするroot `GTP.md`から、Skill直下の`GTP.md`へversion表示先を変更。
- この変更で、Pre-submission Review SkillをGTP protocol versionの表示対象に含めない境界を追加。
