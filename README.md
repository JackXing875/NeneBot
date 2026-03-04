
<div align="center">


# NeneBot: A RAG-Powered Ayachi Nene AI Companion

 <div>&nbsp;</div>

<img src="assets/nene.gif" width="300" alt="Ayachi Nene">

 <div>&nbsp;</div>

<p align="center">
  <b>A Local LLM Conversational Agent for Ayachi Nene powered by Retrieval-Augmented Generation</b><br>
  <i>"メンカタカラメヤサイダブルニンニクアブラマシマシ！"</i>
</p>

 <div>&nbsp;</div>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Node.js-20%2B-339933.svg?style=flat-square&logo=node.js&logoColor=white" alt="Node.js">
  <img src="https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue.js-3.x-4FC08D.svg?style=flat-square&logo=vuedotjs&logoColor=white" alt="Vue">
  <img src="https://img.shields.io/badge/Vite-5.x-646CFF.svg?style=flat-square&logo=vite&logoColor=white" alt="Vite">
  <img src="https://img.shields.io/badge/Tailwind_CSS-4.x-38B2AC.svg?style=flat-square&logo=tailwind-css&logoColor=white" alt="Tailwind">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Ollama-Local_LLM-black.svg?style=flat-square&logo=ollama&logoColor=white" alt="Ollama">
  <img src="https://img.shields.io/badge/Qwen-2.5-blue.svg?style=flat-square&logo=alibabacloud&logoColor=white" alt="Qwen">
  <img src="https://img.shields.io/badge/FAISS-Vector_DB-1877F2.svg?style=flat-square&logo=meta&logoColor=white" alt="FAISS">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Linter-Ruff-D7FF3C.svg?style=flat-square&logo=python&logoColor=black" alt="Ruff">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPLv3-green.svg?style=flat-square" alt="License"></a>
</p>


[**中文文档 (Chinese Version)**](README_ch.md) | [**Vision**](#-vision) | [**Features**](#-features) | [**Quick Start**](#-quick-start) | [**Architecture**](#%EF%B8%8F-architecture) | [**FAQ**](#-faq)

</div>

---

## Vision

Traditional AI role-playing bots often suffer from two fatal flaws: **"Hallucinations"** (making up fake lore) and **"OOC"** (Out of Character responses). While conventional Fine-tuning can help, it is hardware-intensive and rarely eradicates these issues completely.

**NeneBot** is an attempt to bring **RAG (Retrieval-Augmented Generation)** architecture to *Galgame* character simulation. We completely bypassed expensive cloud APIs to build a 100% local, privacy-first engine:
* **External Memory Engine**: By slicing and vectorizing the original script of *Sanoba Witch*, we give the AI "true" memories.
* **Authentic Reproduction**: The LLM is forced to reference retrieved original dialogue, perfectly capturing Nene's gentle, shy, and responsible personality.
* **Ultimate Front-end Aesthetics**: Ditching clunky terminal interfaces for an immersive, modern visual novel (Galgame) UI.

---

## Features

* **Lightning-Fast Local Inference**: Powered by Ollama and Qwen 2.5, enjoy seamless conversations completely offline. Absolute privacy guaranteed.
* **Millisecond Semantic Retrieval**: Utilizes Meta's FAISS vector database alongside the `bge-small-zh` embedding model to pinpoint relevant historical scripts.
* **Threshold Fallback Mechanism**: Features a custom `match_threshold` filter. If the topic is unfamiliar, Nene seamlessly transitions to zero-shot character playing rather than forcing irrelevant memories.
* **Immersive Visual Experience**: A stunning Vue 3 + Vite front-end featuring a dark glassmorphism UI, typewriter effects, and dynamic breathing layouts.
* **Out-of-the-Box Automation**: Includes 1-click installation and startup scripts for both Windows and Linux. No terminal anxiety required.

---

## Quick Start

We have prepared a "babysitter-level" quick start guide for users without a technical background. Please choose the steps based on your OS:

### For Windows Users

**Step 1: Install Prerequisites (Skip if already installed)**
1. Download and install [Python 3.10+](https://www.python.org/downloads/). **[CRITICAL]**: Ensure you check <kbd>Add Python to PATH</kbd> at the bottom of the installer!
2. Download and install [Node.js (LTS version)](https://nodejs.org/).
3. Download and install [Ollama for Windows](https://ollama.com/download/windows).

**Step 2: Download NeneBot**
Click the green `Code` button on this GitHub page and select `Download ZIP`. Extract it to a folder on your PC (e.g., `D:\NeneBot`).

**Step 3: One-Click Ignition!**
Open the extracted folder and **double-click `start_windows.bat`**.
* Grab a coffee. The script will automatically download dependencies, wake up the AI engine, and launch your browser.
* Once the beautiful Galgame UI pops up, Nene is ready to chat!

---

### For Linux Users 

Open your terminal and execute the following elegant commands:

```bash
# 1. Clone the repository
git clone [https://github.com/your-username/NeneBot.git](https://github.com/your-username/NeneBot.git)
cd NeneBot

# 2. Grant execution permissions to scripts
chmod +x scripts/setup.sh scripts/run.sh

# 3. Run the automated setup (Only required once)
./scripts/setup.sh

# 4. Ignite the engines!
./scripts/run.sh
```

> **Tip:** Once started, visit `http://localhost:5173` in your browser for the UI. The backend API Swagger docs are located at `http://localhost:8000/docs`.

---

## Architecture

This project strictly adheres to microservice and front/back-end decoupling standards:

```text
NeneBot/
├── 📂 data/             # Raw script corpus (for vectorization)
├── 📂 vector_store/     # FAISS persistent vector index
├── 📂 frontend/         # Vue 3 + Vite immersive UI
├── 📂 src/              # FastAPI core backend service
│   ├── api/             # Routing and Pydantic data validation
│   ├── core/            # pydantic-settings config and global exceptions
│   ├── infrastructure/  # External adapters (FAISS client, Ollama bridge)
│   └── services/        # Core business logic (RAG pipeline, Embeddings)
├── 📂 scripts/          # DevOps toolbox (Setup, Run, Linters)
├── 📄 pyproject.toml    # Industrial linter configs (Ruff & Mypy)
└── 📄 requirements.txt  # Python dependency list

```

---

## Advanced Configuration

For developers who want to tweak the bot, you can easily customize Nene:

* **Adjust Strictness**: Modify `self.match_threshold` (default 0.8) in `src/services/rag_pipeline.py`. Lower values make her stick strictly to the script; higher values allow more creative freedom.
* **Change Sprites & Backgrounds**: Replace `nene_sprite.png` and `bg_room.jpg` in the `frontend/public/` directory. Changes apply instantly thanks to Vite HMR.
* **Modify System Prompt**: Update `self.system_prompt` in `rag_pipeline.py` to add new personality traits or instructions.

---

## FAQ

<details>
<summary><b>1. "Python / Node is not recognized as an internal or external command" on Windows?</b></summary>





You either haven't installed Python/Node.js, or forgot to add them to your environment variables. Reinstall them and ensure you check the "Add to PATH" option.
</details>

<details>
<summary><b>2. The chat is stuck on "Thinking...", followed by a connection error?</b></summary>





This usually means the Ollama service isn't running, or your machine ran out of VRAM/RAM to load the Qwen 2.5 model. Check your task manager, or try running <code>ollama run qwen2.5</code> manually in the terminal to diagnose the engine.
</details>

<details>
<summary><b>3. Can I swap the character to someone else (e.g., Ayase Mitsukasa)?</b></summary>





Absolutely! This is a universal architecture. Simply:

1. Replace <code>data/raw/train.jsonl</code> with Ayase's dialogue data.
2. Run <code>python scripts/init_vector_db.py</code> to rebuild the memory database.
3. Replace the sprite assets in <code>frontend/public/</code>.
4. Update the character name and persona in the system prompt.
</details>

---

## Contributing

We welcome contributions from the community! Whether it's fixing bugs, improving the CSS aesthetics, or providing better script datasets, please follow these steps:

1. `Fork` the Project.
2. Create your Feature Branch: `git checkout -b feature/AmazingFeature`
3. Commit your Changes: `git commit -m 'feat: Add some AmazingFeature'`
4. Push to the Branch: `git push origin feature/AmazingFeature`
5. Open a Pull Request.

*(Note: Before submitting PRs, please run `./scripts/run_linter.sh` to ensure your code passes our strict Ruff and Mypy checks.)*

---

## License

Distributed under the **[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0)**.
This project is for technical exploration and learning purposes only. The copyright of the character sprites, background art, and game scripts belongs to the original creator (Yuzusoft). Please do not use them for commercial purposes.

