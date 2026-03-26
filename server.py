#!/usr/bin/env python3
"""
Obsidian MCP Server
Gives Claude full read/write/search/list access to any Obsidian vault
under a configured base path.
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Configuration ────────────────────────────────────────────────────────────
VAULTS_BASE = Path(os.environ.get("OBSIDIAN_BASE", "/home/k41r0s3/Desktop/Obsidian"))

# ── Helpers ───────────────────────────────────────────────────────────────────

def resolve_vault(vault_name: str) -> Path:
    """Resolve vault name to absolute path. Raises if it doesn't exist."""
    path = VAULTS_BASE / vault_name
    if not path.exists():
        raise FileNotFoundError(f"Vault '{vault_name}' not found at {path}")
    return path


def resolve_note(vault_path: Path, note: str) -> Path:
    """
    Resolve note name to .md path inside vault.
    Accepts:
      - bare name  'profile'          → profile.md
      - with ext   'profile.md'       → profile.md
      - subfolder  'subfolder/note'   → subfolder/note.md
    """
    note = note.strip()
    if not note.endswith(".md"):
        note += ".md"
    return vault_path / note


def list_vault_tree(vault_path: Path) -> dict:
    """Return a nested dict of all .md files in the vault."""
    tree = {}
    for md_file in sorted(vault_path.rglob("*.md")):
        rel = md_file.relative_to(vault_path)
        parts = list(rel.parts)
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node[parts[-1]] = str(rel)
    return tree


def tree_to_string(tree: dict, indent: int = 0) -> str:
    lines = []
    for key, val in tree.items():
        prefix = "  " * indent
        if isinstance(val, dict):
            lines.append(f"{prefix}📁 {key}")
            lines.append(tree_to_string(val, indent + 1))
        else:
            lines.append(f"{prefix}  • {key}")
    return "\n".join(lines)


def search_in_vault(vault_path: Path, query: str, case_sensitive: bool = False) -> list[dict]:
    """Full-text search across all .md files in a vault."""
    results = []
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(query), flags)

    for md_file in sorted(vault_path.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        matches = []
        for i, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                matches.append({"line": i, "text": line.strip()})

        if matches:
            results.append({
                "file": str(md_file.relative_to(vault_path)),
                "matches": matches[:10],          # cap at 10 hits per file
                "total_matches": len(matches),
            })

    return results


# ── Server setup ──────────────────────────────────────────────────────────────
app = Server("obsidian-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="obsidian_list",
            description=(
                "List all notes inside an Obsidian vault. "
                "Pass vault_name='Resume Builder' (or any folder name under the base path). "
                "Pass vault_name='.' or leave blank to list all top-level vaults."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "vault_name": {
                        "type": "string",
                        "description": "Vault folder name, e.g. 'Resume Builder' or 'mcp.hack'",
                        "default": ".",
                    }
                },
            },
        ),
        Tool(
            name="obsidian_read",
            description=(
                "Read the full content of a note from an Obsidian vault. "
                "Example: vault_name='Resume Builder', note='profile'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "vault_name": {
                        "type": "string",
                        "description": "Vault folder name, e.g. 'Resume Builder'",
                    },
                    "note": {
                        "type": "string",
                        "description": "Note name (with or without .md), e.g. 'profile' or 'subfolder/note'",
                    },
                },
                "required": ["vault_name", "note"],
            },
        ),
        Tool(
            name="obsidian_write",
            description=(
                "Write content to a note in an Obsidian vault. "
                "mode='overwrite' replaces everything. "
                "mode='append' adds to the bottom. "
                "mode='prepend' adds to the top. "
                "Creates the note (and any parent folders) if it doesn't exist."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "vault_name": {
                        "type": "string",
                        "description": "Vault folder name, e.g. 'Resume Builder'",
                    },
                    "note": {
                        "type": "string",
                        "description": "Note name, e.g. 'profile' or 'subfolder/note'",
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content to write",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["overwrite", "append", "prepend"],
                        "default": "overwrite",
                        "description": "Write mode: overwrite | append | prepend",
                    },
                },
                "required": ["vault_name", "note", "content"],
            },
        ),
        Tool(
            name="obsidian_search",
            description=(
                "Full-text search for a keyword or phrase across all notes in a vault. "
                "Returns matching files with line numbers and surrounding context."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "vault_name": {
                        "type": "string",
                        "description": "Vault folder name to search in, e.g. 'Resume Builder'",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search term or phrase",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to match case exactly",
                    },
                },
                "required": ["vault_name", "query"],
            },
        ),
    ]


# ── Tool handlers ─────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    # ── obsidian_list ────────────────────────────────────────────────────────
    if name == "obsidian_list":
        vault_name = arguments.get("vault_name", ".").strip()

        if vault_name in (".", "", "all"):
            # List all top-level vaults
            vaults = [
                d.name for d in sorted(VAULTS_BASE.iterdir())
                if d.is_dir() and not d.name.startswith(".")
            ]
            result = f"📂 Obsidian base: {VAULTS_BASE}\n\nVaults found:\n"
            result += "\n".join(f"  • {v}" for v in vaults)
            return [TextContent(type="text", text=result)]

        try:
            vault_path = resolve_vault(vault_name)
        except FileNotFoundError as e:
            return [TextContent(type="text", text=f"❌ {e}")]

        tree = list_vault_tree(vault_path)
        if not tree:
            return [TextContent(type="text", text=f"Vault '{vault_name}' is empty (no .md files found).")]

        result = f"📂 Vault: {vault_name}\n\n"
        result += tree_to_string(tree)
        return [TextContent(type="text", text=result)]

    # ── obsidian_read ────────────────────────────────────────────────────────
    elif name == "obsidian_read":
        vault_name = arguments.get("vault_name", "").strip()
        note_name  = arguments.get("note", "").strip()

        if not vault_name or not note_name:
            return [TextContent(type="text", text="❌ vault_name and note are required.")]

        try:
            vault_path = resolve_vault(vault_name)
        except FileNotFoundError as e:
            return [TextContent(type="text", text=f"❌ {e}")]

        note_path = resolve_note(vault_path, note_name)
        if not note_path.exists():
            return [TextContent(type="text", text=f"❌ Note not found: {note_path.relative_to(VAULTS_BASE)}")]

        content = note_path.read_text(encoding="utf-8")
        header  = f"# 📄 {note_path.relative_to(VAULTS_BASE)}\n\n"
        return [TextContent(type="text", text=header + content)]

    # ── obsidian_write ───────────────────────────────────────────────────────
    elif name == "obsidian_write":
        vault_name = arguments.get("vault_name", "").strip()
        note_name  = arguments.get("note", "").strip()
        content    = arguments.get("content", "")
        mode       = arguments.get("mode", "overwrite")

        if not vault_name or not note_name:
            return [TextContent(type="text", text="❌ vault_name and note are required.")]

        try:
            vault_path = resolve_vault(vault_name)
        except FileNotFoundError as e:
            return [TextContent(type="text", text=f"❌ {e}")]

        note_path = resolve_note(vault_path, note_name)
        note_path.parent.mkdir(parents=True, exist_ok=True)

        if mode == "overwrite" or not note_path.exists():
            note_path.write_text(content, encoding="utf-8")
            action = "created" if not note_path.exists() else "overwritten"

        elif mode == "append":
            existing = note_path.read_text(encoding="utf-8")
            separator = "\n\n" if existing and not existing.endswith("\n\n") else ""
            note_path.write_text(existing + separator + content, encoding="utf-8")
            action = "appended"

        elif mode == "prepend":
            existing = note_path.read_text(encoding="utf-8")
            separator = "\n\n" if existing else ""
            note_path.write_text(content + separator + existing, encoding="utf-8")
            action = "prepended"

        else:
            return [TextContent(type="text", text=f"❌ Unknown mode '{mode}'. Use: overwrite | append | prepend")]

        rel = note_path.relative_to(VAULTS_BASE)
        ts  = datetime.now().strftime("%Y-%m-%d %H:%M")
        return [TextContent(type="text", text=f"✅ Note {action}: {rel} [{ts}]")]

    # ── obsidian_search ──────────────────────────────────────────────────────
    elif name == "obsidian_search":
        vault_name     = arguments.get("vault_name", "").strip()
        query          = arguments.get("query", "").strip()
        case_sensitive = arguments.get("case_sensitive", False)

        if not vault_name or not query:
            return [TextContent(type="text", text="❌ vault_name and query are required.")]

        try:
            vault_path = resolve_vault(vault_name)
        except FileNotFoundError as e:
            return [TextContent(type="text", text=f"❌ {e}")]

        results = search_in_vault(vault_path, query, case_sensitive)

        if not results:
            return [TextContent(type="text", text=f"No results for '{query}' in vault '{vault_name}'.")]

        lines = [f"🔍 Search: '{query}' in '{vault_name}' — {len(results)} file(s) matched\n"]
        for r in results:
            lines.append(f"\n📄 {r['file']}  ({r['total_matches']} match{'es' if r['total_matches']>1 else ''})")
            for m in r["matches"]:
                lines.append(f"   L{m['line']:>4}: {m['text'][:120]}")

        return [TextContent(type="text", text="\n".join(lines))]

    else:
        return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]


# ── Entry point ───────────────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
