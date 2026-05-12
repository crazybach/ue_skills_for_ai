# ue_skills_for_ai

Custom Codex skill store for AI-assisted Unreal Engine workflows and related tools.

This repository uses the Codex skill-installer-compatible curated layout. Each skill is a directory under `skills/.curated/<skill-name>` and contains a `SKILL.md` file plus optional bundled resources.

## List Skills

```powershell
python C:\Users\j_ma2\.codex\skills\.system\skill-installer\scripts\list-skills.py --repo crazybach/ue_skills_for_ai --path skills/.curated
```

## Install uematgen

```powershell
python C:\Users\j_ma2\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo crazybach/ue_skills_for_ai --path skills/.curated/uematgen
```

## Install a Pinned Version

```powershell
python C:\Users\j_ma2\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo crazybach/ue_skills_for_ai --path skills/.curated/uematgen --ref uematgen-v0.1.0
```

## Versioning

Skills are versioned independently. When updating a skill, bump `metadata.version` in that skill's `SKILL.md`, update `catalog/skills.json`, and create a skill-specific tag such as `uematgen-v0.1.1`.

Restart Codex after installing or updating local skills.
