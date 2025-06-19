from typing import Any, Dict, List, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer

from ..core.config import MILVUS_TOKEN, MILVUS_URI
from ..core.utils import logger


class SearchRequest(BaseModel):
    collection_name: Literal[
        "students",
        "student_quotes",
        "student_relations",
        "schools",
        "clubs",
        "game_basic_info",
    ] = Field(..., description="要搜索的集合的名称。")
    query: str = Field(..., description="用于搜索的文本查询。")
    top_k: int = Field(3, gt=0, le=20, description="要返回的最佳结果数量。")
    filter_by_name: str | None = Field(
        None, description="（可选）按名称精确过滤，仅对students, schools, clubs有效。"
    )


class SearchResultItem(BaseModel):
    id: Any
    distance: float
    entity: Dict[str, Any]


class SearchResponse(BaseModel):
    results: List[SearchResultItem]


load_dotenv()

app = FastAPI(
    title="蔚蓝档案知识库 API",
    description="用于在蔚蓝档案 Milvus 数据库中搜索信息的 API。",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    """
    在应用启动时加载所有必要资源：
    - 连接到 Milvus。
    - 加载句向量模型。
    - 确保所有集合都已创建索引并加载到内存中。
    """
    # 初始化 Milvus 客户端
    logger.info(f"正在连接到 Milvus: {MILVUS_URI}...")
    if not MILVUS_URI or not MILVUS_TOKEN:
        raise RuntimeError("必须在 .env 文件中设置 MILVUS_URI 和 MILVUS_TOKEN")

    client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN)
    app.state.milvus_client = client
    logger.info("成功连接到 Milvus。")

    # 加载句向量模型
    model_name = "paraphrase-multilingual-mpnet-base-v2"
    logger.info(f"正在加载句向量模型: {model_name}...")
    model = SentenceTransformer(model_name)
    app.state.embedding_model = model
    logger.info("句向量模型加载成功。")

    app.state.pk_fields = {}

    # 确保所有集合都已建立索引并加载
    collections_to_load = [
        "students",
        "student_quotes",
        "student_relations",
        "schools",
        "clubs",
        "game_basic_info",
    ]

    for name in collections_to_load:
        try:
            if not client.has_collection(name):
                logger.warning(f"集合 '{name}' 不存在，将跳过加载。")
                continue

            collection_info = client.describe_collection(name)
            pk_field = next(
                (f["name"] for f in collection_info["fields"] if f.get("is_primary")),
                None,
            )
            if pk_field:
                app.state.pk_fields[name] = pk_field
                logger.info(f"缓存集合 '{name}' 的主键: '{pk_field}'")

            # 自动确定向量字段名
            vector_field = next(
                (
                    f["name"]
                    for f in collection_info["fields"]
                    if f["name"].endswith("vector")
                ),
                None,
            )
            if not vector_field:
                logger.warning(f"在集合 '{name}' 中未找到向量字段，跳过。")
                continue

            # 加载集合
            logger.info(f"正在加载集合 '{name}' 到内存...")
            client.load_collection(name)
            logger.info(f"集合 '{name}' 加载成功。")

        except Exception as e:
            logger.error(f"准备集合 '{name}' 时失败: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """在应用关闭时释放资源。"""
    logger.info("正在释放资源...")
    app.state.milvus_client = None
    app.state.embedding_model = None
    logger.info("资源已释放。")


def get_output_fields(collection_name: str) -> List[str]:
    """根据集合名称返回推荐的输出字段列表。"""
    field_map = {
        "students": [
            "name",
            "school",
            "profile",
            "introduction",
            "experience",
            "aliases",
        ],
        "student_quotes": ["student_name", "version", "quote_text"],
        "student_relations": ["student_name", "related_student_name", "relation_type"],
        "schools": ["name", "introduction", "facilities"],
        "clubs": ["name", "school", "description"],
        "game_basic_info": ["category", "title", "content"],
    }
    return field_map.get(collection_name, ["*"])


@app.post("/api/v1/search", response_model=SearchResponse, summary="通用向量搜索")
async def search(
    request: SearchRequest,
    client: MilvusClient = Depends(lambda: app.state.milvus_client),
    model: SentenceTransformer = Depends(lambda: app.state.embedding_model),
):
    """
    在指定的集合中执行向量相似性搜索。
    """
    # 将查询文本编码为向量
    try:
        logger.info(f"正在处理查询: {request.query}...")
        query_vector = model.encode(request.query, convert_to_tensor=False).tolist()
    except Exception as e:
        logger.error(f"查询编码失败: {e}")
        raise HTTPException(status_code=500, detail="处理查询文本失败。")

    search_filter = None
    if request.filter_by_name and request.collection_name in [
        "students",
        "schools",
        "clubs",
        "student_quotes",
    ]:
        if request.collection_name == "student_quotes":
            search_filter = f"student_name like '%{request.filter_by_name}%'"
        else:
            search_filter = f"name like '%{request.filter_by_name}%' or aliases like '%{request.filter_by_name}%'"
        logger.info(f"应用过滤器: {search_filter}")

    # 执行搜索
    try:
        if search_filter:
            raw_results = client.search(
                collection_name=request.collection_name,
                data=[query_vector],
                limit=request.top_k,
                output_fields=get_output_fields(request.collection_name),
                search_params={"metric_type": "L2"},
                filter=search_filter,
            )
        else:
            raw_results = client.search(
                collection_name=request.collection_name,
                data=[query_vector],
                limit=request.top_k,
                output_fields=get_output_fields(request.collection_name),
                search_params={"metric_type": "L2"},
            )
        primary_key_field = app.state.pk_fields.get(request.collection_name)
        if not primary_key_field:
            raise HTTPException(
                status_code=500,
                detail=f"未找到集合 '{request.collection_name}' 的主键配置。",
            )

        formatted_results = []
        for hit in raw_results[0]:
            formatted_hit = {
                "id": hit.get(primary_key_field),
                "distance": hit.get("distance"),
                "entity": hit.get("entity"),
            }
            formatted_results.append(formatted_hit)

        return {"results": formatted_results}
    except Exception as e:
        logger.error(f"在集合 '{request.collection_name}' 上搜索失败: {e}")
        if "collection not loaded" in str(e):
            raise HTTPException(
                status_code=503,
                detail=f"服务不可用: 集合 '{request.collection_name}' 未加载。",
            )
        raise HTTPException(status_code=500, detail="搜索过程中发生错误。")


@app.get("/", summary="API根目录")
async def root():
    return {"message": "欢迎使用蔚蓝档案知识库 API。请访问 /docs 查看交互式文档。"}
