# Registry & Publication Rules

Канон для server-side publication pipeline и governance.

## Ownership

- Один canonical tool id = один owner.
- Alias не может перехватывать чужой canonical id.
- Cross-module conflicts блокируются до publish.
- Reserved namespaces принимаются только от `owner_scope=core|platform|builtin`.

## Publish pipeline

Публикация проходит через один и тот же путь:

1. `create/upload`
2. normalize manifest
3. validate contract
4. preflight ZIP
5. smoke load/register/list_tools
6. conflict check
7. publish in registry

Если любой шаг падает, pack не публикуется.

## Validation gates

Server блокирует публикацию, если обнаружено:

- missing required manifest fields
- invalid semantic ids
- invalid aliases
- invalid semver fields
- missing `dependencies` / `redaction` / `resources`
- invalid lifecycle
- runtime smoke mismatch с declared tools
- reserved namespace violation

## Lifecycle

- `experimental`
- `stable`
- `deprecated`
- `removed`

Правила:

- Deprecated tool по возможности должен иметь replacement.
- Alias живёт ограниченный migration window и не является source of truth.
- Removal должен идти после major-level contract change.
