# 🌍 undefined

> **"Sovereignty of this world resides in the players, and all power emanates from them."**

A Text-Based Multiplayer Reality Simulation Game

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎮 Introduction

**undefined** is an AI-powered text-based open-world game.

- 🤖 **AI Referee**: Every action is judged realistically through 7 simulation engines
- 🌐 **Real-time Multiplayer**: Share the same world with other players via WebSocket
- 🔬 **Invention System**: Invent new materials or tools and register them globally
- 🗺️ **Infinite World**: Procedurally generated biomes based on coordinates

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/pearl-100/undefined-public.git undefined
cd undefined
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables
```bash
# Create .env file
cp env.example .env

# Edit .env file
SERVER_API_KEY=your-api-key-here
SERVER_DEFAULT_MODEL=gemini/gemini-3-flash-preview
GIT_AUTO_PUSH=false
```

### 4. (Optional) Set Up Initial Data
```bash
# To start with example data:
cp world_data.example.json world_data.json
```
On first startup, `world_data.json` (if present) will be automatically migrated into the SQLite database (`world.db`).

### 5. Run the Server
```bash
python main.py
```

The server runs at `http://localhost:8000`.

---

## 🎯 Game Commands

| Command | Description |
|---------|-------------|
| `/do <action>` | Request AI judgment for an action (e.g., `/do pick up a stone`) |
| `/look [-p\|-o\|-i] [target]` | Observe nearby surroundings, people(-p), objects(-o), or items(-i) |
| `/check` | Check your physical status |
| `/inven` | Check inventory |
| `/move <direction>` | Move (north/south/east/west) |
| `/say <message>` | Speak to nearby players |
| `/name <name>` | Change nickname |
| `/materials` | View discovered materials registry |
| `/blueprints` | View crafting blueprints registry |
| `/rules` | View current world rules |
| `/respawn` | Revive after death |
| `/export` | View account recovery code |
| `/import <code>` | Recover account |
| `/help` | Show help |

---

## 🔧 Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Realtime**: WebSocket
- **AI**: LiteLLM (Groq, OpenAI, Anthropic, Gemini supported)
- **Database**: SQLite (aiosqlite)
- **Frontend**: Vanilla HTML/CSS/JS

---

## 📁 Project Structure

```
undefined/
├── main.py                 # Main server application
├── database.py             # SQLite database module
├── world_rules.json        # AI simulation rules
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html          # Frontend
├── world_data.example.json # Initial data example
├── env.example             # Environment variables example
├── .gitignore              # Git ignore list
└── README.md
```

---

## ⚙️ Environment Variables

These values are read from your `.env` file via `python-dotenv` (see `env.example`).

> Note: `SERVER_DEFAULT_MODEL` is used **only for Free/Guest mode** (when the client does not provide an API key and the server falls back to `SERVER_API_KEY`).

| Variable | Description | Code default (if unset) | Recommended (env.example / Quick Start) |
|----------|-------------|--------------------------|------------------------------------------|
| `SERVER_API_KEY` | Server API key for free/guest users | (empty) | `your-api-key-here` |
| `SERVER_DEFAULT_MODEL` | Default AI model for free/guest users | `gemini-2.5-flash` | `gemini-3-flash-preview` |
| `GIT_AUTO_PUSH` | Auto backup Git push at midnight | `false` | `false` |
| `ADMIN_UUIDS` | Admin UUIDs (comma separated) | (empty) | (empty) |
| `BMC_WEBHOOK_SECRET` | Buy Me a Coffee webhook secret | (empty) | (empty) |

---

## 🗄️ Database Schema

The `world.db` SQLite file is automatically created on server start.

| Table | Description |
|-------|-------------|
| `users` | Player info (position, inventory, status) |
| `objects` | World objects |
| `materials` | Discovered materials |
| `object_types` | Crafting blueprints |
| `logs` | History logs |
| `supporters` | Supporter info |

---

## 🔄 Migration

Existing `world_data.json` users will be automatically migrated to SQLite on server start:

1. Server starts
2. Detects `world_data.json`
3. Migrates data to SQLite DB
4. Moves original file to `backups/` folder

---

## 💾 Backup System

- **Auto Backup**: Daily at midnight, DB → JSON export (`backups/world_data_date.json`)
- **Git Integration**: Auto commit & push when `GIT_AUTO_PUSH=true`

---

## 🎨 The 7 Simulation Engines

1. **Bio-Engine** 🩸 - Biological realism (injuries, hunger, disease)
2. **Decay-Engine** ⏳ - Entropy and time (corrosion, decay)
3. **Social-Engine** 🗣️ - Memes and politics (reputation, atmosphere)
4. **Economic-Engine** 💎 - Scarcity and value (dynamic pricing)
5. **Meteorological-Engine** 🌪️ - Weather physics
6. **Epistemic-Engine** 📚 - Knowledge preservation (tech levels)
7. **Ecological-Engine** 🌿 - Ecosystem chain reactions

---

## 🤝 Contributing

1. Fork
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Pull Request

---

## ☕ Support

If you like this project:

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/2805khun)

Supporters receive a 🌟 gold username in-game!

---

## 📜 License

MIT License - Free to use, modify, and distribute.

---

<p align="center">
  <i>"Hello, World!" - Genesis Monolith</i>
</p>
