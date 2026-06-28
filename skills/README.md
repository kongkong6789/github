# Project Skill Library

Put reusable project Skills here as folders:

```text
skills/
└─ my-skill/
   ├─ SKILL.md
   ├─ skill.registry.json
   ├─ assets/
   └─ scripts/
```

The governance page scans direct child folders that contain `SKILL.md`.
Use `/governance` to import or update a folder into the Skill Registry.
Imported Skills start as `draft`; agents can use them only after approval/activation.

Optional `skill.registry.json` can provide stable defaults such as `skill_id`,
`name`, `scenarios`, `tool_allowlist`, and `output_schema` for re-imports.

Do not place secrets, `.env` files, local caches, or raw business exports in this directory.
