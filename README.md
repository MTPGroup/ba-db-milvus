# BA-DB-Milvus: 蔚蓝档案向量数据库 🚧

这是一个基于 FastAPI 和 Milvus 的后端服务，旨在为《蔚蓝档案》(Blue Archive) 的游戏数据提供强大的向量搜索能力。项目通过将游戏内的学生、学校、社团等信息转换为向量，实现了~~高效的~~语义相似性搜索。

## ✨ 功能特性

- **高性能API**: 使用 FastAPI 构建异步、高性能的搜索 API。
- **向量数据库**: 采用 Milvus 作为核心向量数据库，用于存储和检索高维向量。
- **语义理解**: 利用 `sentence-transformers` 模型将文本数据（如学生简介、台词）编码为语义向量。
- **统一搜索接口**: 提供 `/api/v1/search` 端点，支持对多个数据集合（学生、学校、社团等）的统一查询。
- **混合搜索**: 支持元数据过滤与向量搜索相结合的混合搜索模式，例如，可以先按学生姓名进行筛选，再在结果中进行语义搜索，极大地提高了搜索精度。
- **模块化结构**: 清晰的项目结构，将数据抓取、数据库构建和 API 服务分离，易于维护和扩展。
- **数据自动化**: 包含用于从数据源抓取信息并自动构建数据库的脚本。

## 📂 项目结构

```bash
.
├── data/                 # 存放原始数据 (JSON, 音频等)
├── scripts/              # 用于数据抓取和预处理的一次性脚本
├── src/                  # 核心应用源代码
│   ├── api/              # API 端点定义
│   ├── core/             # 核心配置和共享工具
│   ├── db/               # 数据库交互 (schemas, builder)
│   └── main.py           # FastAPI 应用入口
├── .env                  # (需手动创建) 存储环境变量
├── docker-compose.yml    # 用于运行 Milvus 和 Attu 等依赖服务
├── pyproject.toml        # 项目依赖管理
└── run_build.py          # 用于构建和填充数据库的入口脚本
```

## 🚀 快速开始

### 1. 环境准备

- [Docker](https://www.docker.com/) 和 Docker Compose
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (推荐的 Python 包管理器)

### 2. 安装与配置

1. **克隆仓库**

    ```bash
    git clone <your-repository-url>
    cd ba-db-milvus
    ```

2. **启动依赖服务**
    项目需要 Milvus 数据库。你可以使用提供的 `docker-compose.yml` 文件来快速启动 Milvus 和其管理工具 Attu。

    ```bash
    docker-compose up -d
    ```

    这将在后台启动 Milvus (端口 `19530`) 和 Attu (端口 `8001`)。

3. **创建 Python 虚拟环境并安装依赖**

    ```bash
    uv sync
    ```

4. **配置环境变量**
    在项目根目录创建一个名为 `.env` 的文件，并填入以下内容。这是应用连接到 Milvus 所必需的。

    ```env
    # .env
    MILVUS_URI="http://localhost:19530"
    # MILVUS_TOKEN="" # 如果你的 Milvus 设置了认证，请填入 Token
    ```

### 3. 构建数据库

在首次运行或数据更新后，你需要运行构建脚本来创建集合、插入数据并构建索引。

```bash
uv run run_build.py
```

这个过程可能需要一些时间，因为它会下载模型、处理所有数据文件、生成向量并将其存入 Milvus。

### 4. 启动 API 服务

```bash
uvicorn src.main:app --reload
```

服务启动后，API 将在 `http://127.0.0.1:8000` 上可用。

## 💡 API 使用示例

你可以使用 `curl` 或任何 API 测试工具与 `/api/v1/search` 端点交互。

### 示例 1: 简单的语义搜索

在 `students` 集合中搜索与“补习部的成员”语义最相关的学生。

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/api/v1/search' \
  -H 'Content-Type: application/json' \
  -d '{
  "collection_name": "students",
  "query": "补习部的成员",
  "top_k": 3
}'
```

### 示例 2: 混合搜索 (过滤 + 语义)

先筛选出所有名字中包含“梓”的学生，然后在这些学生中找出与“有点担心她的身体”描述最相关的条目。

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/api/v1/search' \
  -H 'Content-Type: application/json' \
  -d '{
  "collection_name": "students",
  "query": "有点担心她的身体",
  "top_k": 2,
  "filter_by_name": "梓"
}'
```

## 🧐 数据来源

- [萌娘百科](https://moegirl.icu)

## 📜 许可协议

该项目采用 [GNU General Public License v3.0](LICENSE) 许可协议。
