実装範囲と完了条件を固定します

<!-- gtp-record:v1 -->

```json
{
  "gtp": "1.0",
  "type": "contract",
  "id": "01234567-89ab-4def-8123-456789abcdef",
  "supersedes": [],
  "goal": "walking skeletonを実装する",
  "scope": ["src/", "tests/"],
  "done_conditions": {
    "acceptance_artifact": {
      "text": "受け入れ記録がsource commitに存在する",
      "evidence_kind": "artifact"
    }
  }
}
```
