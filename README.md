
<div align="center">

<img src="assets/nene.gif" width="400" alt="Ayachi Nene">

# 🌸 NeneBot: Industrial RAG-Powered Assistant
**基于检索增强生成 (RAG) 架构的绫地宁宁（《魔女的夜宴》）本地大模型对话服务**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-00a393.svg)](https://fastapi.tiangolo.com)
[![Ollama](https://img.shields.io/badge/Ollama-LLM-white)](https://ollama.com/)
[![FAISS](https://img.shields.io/badge/FAISS-Vector_DB-black)](https://github.com/facebookresearch/faiss)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

</div>

---

## 📖 项目愿景 (Vision)

**NeneBot** 旨在探索如何利用工业级 RAG 架构解决二次元角色对话中的“幻觉”与“语气偏差”问题。与传统的全量微调（Fine-tuning）不同，本项目采用“外挂记忆引擎”方案：
- **零训练成本**：通过剧本语料库的向量化，实现即时的知识更新。
- **原汁原味**：强制模型参考原版剧本台词，最大程度还原宁宁的性格特征与说话习惯。
- **工业级解耦**：前后端完全分离，支持多种向量数据库与 LLM 后端切换。

---

## 🛠️ 技术栈 (Tech Stack)



* **Core Engine**: [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous high-performance framework)
* **Vector Database**: [FAISS](https://faiss.ai/) (Efficient similarity search by Meta)
* **Embedding Model**: `BAAI/bge-small-zh-v1.5` (State-of-the-art Chinese embedding)
* **LLM Backend**: [Ollama](https://ollama.com/) (Running Qwen2.5 locally)
* **UI Framework**: [Streamlit](https://streamlit.io/) (Interactive AI frontend)
* **DevOps**: Docker, Makefile, Ruff (Linter), Mypy (Type checking)

---

## 📂 项目目录结构 (Directory Structure)

```text
NeneBot/
├── data/raw/                  # 原始剧本语料 (train.jsonl)
├── vector_store/              # 持久化向量索引与元数据
├── src/                       # 核心业务逻辑
│   ├── api/                   # FastAPI 路由与 Pydantic 模型
│   ├── core/                  # 配置中心 (Settings) 与全局异常/日志
│   ├── infrastructure/        # 外部服务适配器 (FAISS, Ollama Client)
│   └── services/              # 核心服务 (RAG Pipeline, Embedding)
├── ui/                        # 前端交互界面 (Streamlit)
├── scripts/                   # 自动化运维脚本 (数据库初始化、Linters)
├── deploy/                    # 部署相关配置 (Dockerfile)
├── requirements.txt           # 依赖清单
├── Makefile                   # 工业标准自动化指令
└── README.md
```

---

## 🚀 快速开始 (Quick Start)

### 1. 环境准备

确保你的机器安装了 **Python 3.10+** 和 **Ollama**。

```bash
# 1. 安装系统级依赖 (Linux/WSL)
sudo apt-get update && sudo apt-get install zstd -y

# 2. 安装 Ollama 并运行模型
curl -fsSL [https://ollama.com/install.sh](https://ollama.com/install.sh) | sh
ollama serve &
ollama run qwen2.5
```

### 2. 安装项目依赖

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 数据灌库与点火
执行：

```bash
# 生成向量索引
python scripts/init_vector_db.py

# 启动后端服务
python src/main.py
```

### 4. 启动可视化界面

在新的终端中运行：

```bash
streamlit run ui/app.py

```

---

## 🧠 核心 RAG 算法流程 (RAG Flow)

1. **Semantic Search**: 使用 `bge-small-zh` 将玩家输入转化为 512 维向量。
2. **Threshold Filtering**: 在 FAISS 中检索 Top-K 结果，并应用 `match_threshold`（默认 0.8）过滤无关记忆。
3. **Prompt Synthesis**: 动态注入检索到的宁宁原话作为 Few-shot 样本。
4. **Inference**: 结合系统提示词，由本地 Qwen2.5 生成最终回复。

---

## ⚙️ 工业级规范 (Standard & Quality)

* **Type Safety**: 全量使用 Python Type Hints，通过 `mypy` 静态检查。
* **Linting**: 严格遵守 Google Python Style Guide，使用 `ruff` 进行格式化。
* **Configuration**: 基于 `pydantic-settings` 的环境变量管理。
* **Logging**: 结构化日志输出，支持生产环境追踪。

---

## 🤝 贡献指南 (Contributing)

欢迎提交 Pull Request 或 Issue！

1. Fork 本项目。
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)。
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)。
4. 推送到分支 (`git push origin feature/AmazingFeature`)。
5. 开启一个 Pull Request。

---

## 📄 开源协议 (License)

本项目采用 [**GNU General Public License v3.0**](https://www.google.com/search?q=LICENSE) 许可。

---

<div align="center">
<i>"保科君，接下来的工作也要一起努力哦..."</i>
</div>

