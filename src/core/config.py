import os

from dotenv import load_dotenv

# 从项目根目录的 .env 文件加载环境变量
load_dotenv()

# Milvus/Zilliz Cloud 连接信息
MILVUS_URI = os.getenv("MILVUS_URI")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")

# 向量维度
VECTOR_DIM = 768
