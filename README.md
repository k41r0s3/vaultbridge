# vaultbridge

A lightweight Python MCP server that gives Claude full read/write/search/list access to any Obsidian vault on your machine. Claude Desktop auto-starts it — no manual server startup needed.

## Tools Exposed

| Tool | Description |
|---|---|
| `obsidian_list` | List all notes in a vault, or list all available vaults |
| `obsidian_read` | Read a note's full content |
| `obsidian_write` | Write/append/prepend content to a note |
| `obsidian_search` | Full-text search across all notes in a vault |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/k41r0s3/vaultbridge.git ~/vaultbridge
cd ~/obsidian-vault-mcp
```

### 2. Create the virtual environment & install dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Register with Claude Desktop

Edit `~/.config/Claude/claude_desktop_config.json` and add this inside the `"mcpServers"` block:

```json
"obsidian-vault-mcp": {
  "command": "/home/YOUR_USER/vaultbridge/.venv/bin/python",
  "args": [
    "/home/YOUR_USER/obsidian-vault-mcp/server.py"
  ],
  "env": {
    "OBSIDIAN_BASE": "/home/YOUR_USER/path/to/your/Obsidian"
  }
}
```

Replace `YOUR_USER` and `OBSIDIAN_BASE` with your actual username and Obsidian vaults folder path.

### 4. Restart Claude Desktop

Close and reopen Claude Desktop. The server starts automatically — no manual startup needed. You should see `vaultbridge` in the connected tools.

---

## Usage

Once connected, just tell Claude naturally:

**List all vaults:**
> "List all my Obsidian vaults"

**List notes in a vault:**
> "List all notes in my Resume Builder vault"

**Read a note:**
> "Read the skills note from my Resume Builder vault"

**Update a note:**
> "Append this new project to my projects note in Resume Builder: ..."

**Search:**
> "Search for 'Burp Suite' across my Resume Builder vault"

**Generate a tailored resume:**
> "Read all the resume notes from my Resume Builder vault — here's a job description: [JD]. Generate a tailored resume."

---

## Configuration

| Env Variable | Description |
|---|---|
| `OBSIDIAN_BASE` | Path to the folder containing all your Obsidian vaults |

The server auto-discovers any vault folder under `OBSIDIAN_BASE` — no config changes needed when you add new vaults.

---

## Project Structure

```
obsidian-vault-mcp/
├── .venv/            # isolated Python env (gitignored)
├── .gitignore
├── server.py         # MCP server
├── requirements.txt  # pinned dependencies
└── README.md
```
