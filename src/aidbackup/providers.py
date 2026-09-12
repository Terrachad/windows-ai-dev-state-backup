"""An explicit allowlist of current-user state locations, not a disk scanner."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .core import BackupError, Component, absolute, lexists


@dataclass(frozen=True)
class Location:
    id: str
    path: Path
    kind: str
    group: str
    custom: bool = False
    restore_allowed: bool = True


def locations(home: Path, env: Mapping[str, str]) -> list[Location]:
    home = absolute(home)
    roaming = absolute(env.get("APPDATA") or str(home / "AppData" / "Roaming"))
    local = absolute(env.get("LOCALAPPDATA") or str(home / "AppData" / "Local"))
    docs = home / "Documents"
    # Redirected Documents: caller supplies the actual Windows Known Folder path.
    if env.get("AIDBACKUP_DOCUMENTS"):
        docs = absolute(env["AIDBACKUP_DOCUMENTS"])
    result = []

    def add(id, path, kind="directory", group="developer", variable=None, restorable=True):
        default = absolute(path)
        actual = absolute(env[variable]) if variable and env.get(variable) else default
        result.append(Location(id, actual, kind, group, actual != default, restorable))

    add("claude", home / ".claude", group="agent", variable="CLAUDE_CONFIG_DIR")
    add("codex", home / ".codex", group="agent", variable="CODEX_HOME")
    add("claude-global", home / ".claude.json", "file", "agent")
    add("claude-global-backup", home / ".claude.json.backup", "file", "agent")
    for id, filename in (("gitconfig", ".gitconfig"), ("git-credentials", ".git-credentials"),
                         ("npmrc", ".npmrc"), ("yarnrc", ".yarnrc"),
                         ("yarnrc-yaml", ".yarnrc.yml"), ("wslconfig", ".wslconfig")):
        add(id, home / filename, "file")
    for id, dirname in (("ssh", ".ssh"), ("docker", ".docker"), ("aws", ".aws"),
                        ("azure", ".azure"), ("kube", ".kube"), ("gnupg-home", ".gnupg")):
        add(id, home / dirname)
    xdg = absolute(env.get("XDG_CONFIG_HOME") or str(home / ".config"))
    add("git-xdg", xdg / "git")
    add("gh", roaming / "GitHub CLI", variable="GH_CONFIG_DIR")
    add("gh-home", home / ".config" / "gh")
    add("gnupg", roaming / "gnupg", variable="GNUPGHOME")
    add("gcloud", roaming / "gcloud", variable="CLOUDSDK_CONFIG")
    add("powershell", docs / "PowerShell")
    add("windows-powershell", docs / "WindowsPowerShell")
    add("vscode", roaming / "Code" / "User")
    add("cursor", roaming / "Cursor" / "User")
    for name in ("Claude", "ChatGPT", "Codex", "OpenAI"):
        add("desktop-" + name.lower(), roaming / name, group="desktop", restorable=False)
    packages = local / "Packages"
    if packages.is_dir():
        for package in sorted(packages.iterdir()):
            if not package.name.lower().startswith(("claude_", "openai.codex_", "openai.chatgpt_")):
                continue
            # Package family names are kept as source references, never restore targets.
            for state in ("LocalState", "RoamingState", "LocalCache", "Settings"):
                path = package / state
                id = "desktop-package-" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
                add(id, path, group="desktop", restorable=False)
    return result


def current_context() -> tuple[Path, dict[str, str]]:
    if os.name != "nt":
        raise BackupError("Live-profile discovery and restore are supported on Windows only. "
                          "Verification and isolated tests can run on other systems.")
    env = dict(os.environ)
    home = absolute(env["USERPROFILE"])
    # Read the Known Folder registry value without launching a shell or changing it.
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
            value, _ = winreg.QueryValueEx(key, "Personal")
        env["AIDBACKUP_DOCUMENTS"] = os.path.expandvars(value)
    except FileNotFoundError:
        pass
    return home, env


def discover(home: Path, env: Mapping[str, str], *, include_dev=False,
             include_desktop=False, tools: list[str] | None = None) -> list[Component]:
    allowed_tools = {"claude", "codex"}
    if tools and not set(tools) <= allowed_tools:
        raise BackupError("Only claude and codex are valid --tools values.")
    available = locations(home, env)
    core = {x.id: x for x in available if x.id in allowed_tools}
    selected = set(tools) if tools else {key for key, value in core.items() if lexists(value.path)}
    for id, loc in core.items():
        if loc.custom and not lexists(loc.path):
            raise BackupError(f"Configured custom {id} directory is missing: {loc.path}")
    if not selected:
        raise BackupError("No Claude Code or Codex state detected. Check the Windows account and custom homes.")
    for id in selected:
        if not core[id].path.is_dir():
            raise BackupError(f"Required selected state is missing: {core[id].path}")
    result = []
    for loc in available:
        if loc.group == "agent":
            enabled = loc.id in selected or (loc.id.startswith("claude-global") and "claude" in selected)
        else:
            enabled = (loc.group == "developer" and include_dev) or (loc.group == "desktop" and include_desktop)
        if enabled and lexists(loc.path):
            result.append(Component(loc.id, loc.path, loc.kind,
                                    "custom" if loc.custom else "default", loc.restore_allowed))
    return result


def restore_targets(manifest: dict, home: Path, env: Mapping[str, str], *,
                    selected: list[str] | None = None, overrides: Mapping[str, str] | None = None) -> dict[str, Path]:
    """Never obtain a write destination from snapshot source_path metadata."""
    known = {loc.id: loc for loc in locations(home, env)}
    overrides = overrides or {}
    if not isinstance(overrides, Mapping) or any(not isinstance(k, str) or not isinstance(v, str)
                                               for k, v in overrides.items()):
        raise BackupError("Target map must be a JSON object mapping component IDs to absolute path strings.")
    components = {c["id"]: c for c in manifest["components"]}
    wanted = set(selected) if selected else {id for id, c in components.items() if c["restore_allowed"]}
    if not wanted <= components.keys():
        raise BackupError("A requested component is absent from this snapshot.")
    if not set(overrides) <= wanted:
        raise BackupError("Target-map entries must match explicitly selected/restorable components.")
    targets = {}
    for id in sorted(wanted):
        c = components[id]
        if not c["restore_allowed"] or id not in known:
            raise BackupError(f"Unknown/manual-only component is not auto-restorable: {id}")
        loc = known[id]
        if c["source_mode"] == "custom" and not loc.custom and id not in overrides:
            raise BackupError(f"{id} used a custom home. Configure its current environment variable "
                              "or supply an explicit --target-map. Old source paths will not be reused.")
        targets[id] = absolute(overrides[id]) if id in overrides else loc.path
    return targets
