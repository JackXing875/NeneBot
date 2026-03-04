<div align="center">

<img src="assets/nene.gif" width="500" alt="Ayachi Nene">

# NeneBot: A RAG-Powered Ayachi Nene AI Companion

<p align="center">
  <b>基于检索增强生成 (RAG) 架构的绫地宁宁本地大模型对话服务</b><br>
  <i>"メンカタカラメヤサイダブルニンニクアブラマシマシ！"</i>
</p>

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

[**项目愿景**](#-项目愿景-vision) | [**特性一览**](#-核心特性-features) | [**小白极速启动**](#-小白极速启动-getting-started) | [**架构详解**](#-技术架构-architecture) | [**常见问题**](#-常见问题-faq)

</div>

---

## 项目愿景 



传统的二次元角色 AI 往往面临两个致命痛点：**“幻觉”**（乱编设定）和 **“OOC”**（Out Of Character，语气崩坏）。常规的微调不仅耗费显卡，而且难以彻底根除这些问题。

**NeneBot** 是一次将**RAG（检索增强生成）技术**应用于 *Galgame* 角色模拟的尝试。我们摒弃了昂贵的云端 *API*，完全在本地构建：
* **外挂记忆引擎**：将《魔女的夜宴》原版剧本切片并向量化，让 AI 拥有“真物”般的记忆。
* **原汁原味还原**：模型被强制要求参考检索到的原版台词进行输出，100% 还原宁宁温柔、害羞、爱操心的性格特点。
* **极致还原游戏**：告别简陋的控制台，打造沉浸式的现代 Galgame 视觉交互界面。

---

## 核心特性

* **极速本地推理**：依托 Ollama 驱动 Qwen2.5 模型，断网也能和宁宁流畅对话，保护绝对隐私。
* **毫秒级语义检索**：使用 Meta 开源的 FAISS 向量数据库，配合 `bge-small-zh` 模型，精准定位历史剧本。
* 阈值熔断机制**：独创 `match_threshold` 相似度过滤，宁宁遇到不懂的话题会自由发挥，绝不“驴头不对马嘴”。
* **沉浸式视觉体验**：Vue 3 + Vite 驱动的深色磨砂玻璃 UI，支持打字机特效与动态呼吸感布局。
* **全自动开箱即用**：提供 Windows/Linux 双平台一键环境装载与启动脚本，无需任何终端知识。

---

## 极速启动

我们为非技术背景的玩家准备了“保姆级”的一键启动方案。请根据你的操作系统选择相应的步骤：

### Windows 用户

**第一步：安装两大基础软件（如果你的电脑已有，可跳过）**
1. 下载并安装 [Python 3.10+](https://www.python.org/downloads/)。**【极其重要】**：安装界面底部一定要勾选 <kbd>Add Python to PATH</kbd>！
2. 下载并安装 [Node.js (LTS版本)](https://nodejs.org/)，一路点击下一步即可。
3. 下载并安装 [Ollama Windows版](https://ollama.com/download/windows)。

**第二步：下载 NeneBot 源码**
在 GitHub 页面点击绿色的 `Code` 按钮，选择 `Download ZIP`。解压到你的电脑中（建议路径全英文，如 `D:\NeneBot`）。

**第三步：双击运行！**
进入解压后的文件夹，找到并**双击运行 `start_windows.bat`**。
* 喝口水，脚本会自动为你下载依赖、唤醒 AI 引擎并打开浏览器。
* 当你看到精美的 Galgame 界面弹出时，宁宁就已经在等你了！

---

### Linux 用户

打开你的终端，依次执行以下三段优雅的指令：

```bash
# 1. 克隆代码库并进入目录
git clone [https://github.com/your-username/NeneBot.git](https://github.com/your-username/NeneBot.git)
cd NeneBot

# 2. 赋予脚本执行权限
chmod +x scripts/setup.sh scripts/run.sh

# 3. 执行全自动装配 (仅首次需要)
./scripts/setup.sh

# 4. 运行
./scripts/run.sh
```

> **Tip:** 服务启动后，浏览器访问 `http://localhost:5173` 即可进入交互界面。后端 API 文档位于 `http://localhost:8000/docs`。

---

## 技术架构 

本项目的目录结构遵循严格的微服务与前后端解耦规范：

```text
NeneBot/
├── 📂 data/             # 原始剧本语料库 (用于向量化)
├── 📂 vector_store/     # FAISS 持久化向量索引
├── 📂 frontend/         # 🎨 Vue 3 + Vite + Tailwind 沉浸式前端界面
├── 📂 src/              # ⚙️ FastAPI 核心后端服务
│   ├── api/             # 路由控制与 Pydantic 数据校验
│   ├── core/            # pydantic-settings 配置中心与全局异常处理
│   ├── infrastructure/  # 基础设施适配层 (FAISS客户端, Ollama桥接)
│   └── services/        # 核心业务逻辑 (RAG 调度管线, Embedding 服务)
├── 📂 scripts/          # 自动化运维工具箱 (装载、启动、Linter检查)
├── 📄 pyproject.toml    # Ruff & Mypy 工业级代码规范配置
└── 📄 requirements.txt  # Python 依赖清单

```

---

## 高级配置 

对于有开发能力的玩家，你可以通过修改以下文件来“调教”属于你的宁宁：

* **修改严格程度**：在 `src/services/rag_pipeline.py` 中调整 `self.match_threshold`（默认 0.8）。值越小，宁宁的回答越死板（必须完全贴合剧本）；值越大，宁宁越倾向于自由发挥。
* **修改立绘与背景**：替换 `frontend/public/` 目录下的 `nene_sprite.png` 和 `bg_room.jpg`，无需重启即可生效（Vite 热更新支持）。
* **修改提示词**：在 `rag_pipeline.py` 的 `self.system_prompt` 中，可以增加新的性格设定指令。

---

## 常见问题 

<details>
<summary><b>1. 启动时提示 "Python / Node 不是内部或外部命令" 怎么办？</b></summary>


这是因为你没有安装 Python/Node.js，或者安装时忘记配置环境变量。请卸载后重新安装，并在安装界面务必勾选“Add to PATH”选项。
</details>

<details>
<summary><b>2. 聊天框一直显示“宁宁正在思考”，最后提示“大脑连接断开”？</b></summary>





通常是因为 Ollama 服务未启动，或者你的电脑内存/显存不足以运行 Qwen2.5 模型。请检查后台是否有内存溢出，或者尝试在终端手动运行 `ollama run qwen2.5` 测试引擎是否正常。
</details>

<details>
<summary><b>3. 我想换成其他角色（比如三司绫濑）可以吗？</b></summary>





完全可以！本项目是通用架构。你只需要：

1. 准备绫濑的对话记录（替换 <code>data/raw/train.jsonl</code>）。
2. 运行 <code>python scripts/init_vector_db.py</code> 重新构建记忆库。
3. 替换 <code>frontend/public/</code> 下的立绘资源。
4. 修改系统提示词中的名字与设定即可。
</details>

---

## 参与贡献

我们非常欢迎来自社区的力量！无论是提交 Bug 修复、改进前端样式，还是提供更优质的剧本数据集，都可以通过以下流程参与：

1. `Fork` 本仓库。
2. 创建您的特性分支: `git checkout -b feature/AmazingFeature`
3. 提交您的更改: `git commit -m 'feat: Add some AmazingFeature'`
4. 推送至分支: `git push origin feature/AmazingFeature`
5. 开启一个 Pull Request。

*(注：提交代码前，请务必运行 `./scripts/run_linter.sh` 确保代码符合 Ruff 和 Mypy 的规范。)*

---

## 协议声明 

本项目采用 **[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0)** 许可。
本项目仅作为技术探讨与学习使用，立绘及剧本等相关资源版权归原作公司（Yuzusoft）所有，请勿用于任何商业用途。
