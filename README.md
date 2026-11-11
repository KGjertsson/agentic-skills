# agentic-skills

The single source of truth for my project-agnostic Claude Code skills.

## Layout

```
skills/<name>/SKILL.md     # the generic workflow or rules
skills/<name>/...          # scripts the skill uses
```

Anything that only applies to one repository lives in that repository, in `.claude/skill-config/<name>.md` (and `.json` where a script reads it). A skill reads its config first. If the file is missing, the skill says so and asks, rather than guessing.

## Install

Link each skill into your user-level skills directory, on every environment you run Claude Code in.

WSL or Linux:

```bash
ln -s /mnt/c/Users/gjert/Documents/dev/agentic-skills/skills/<name> ~/.claude/skills/<name>
```

Windows (a junction needs no admin rights):

```powershell
New-Item -ItemType Junction -Path "$HOME\.claude\skills\<name>" -Target "C:\Users\gjert\Documents\dev\agentic-skills\skills\<name>"
```

## Skills

| Skill | What it does | Per-repo config |
|---|---|---|
| `ship` | Ships an agreed change: implement, PR, independent review, merge | `.claude/skill-config/ship.md` |
| `immutable-java` | Immutability rules for Java, plus a checker for what ArchUnit can't see | `.claude/skill-config/immutable-java.md` and `.json` |
