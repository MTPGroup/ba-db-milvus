import json
from pathlib import Path

from pymilvus import CollectionSchema, FieldSchema, MilvusClient
from sentence_transformers import SentenceTransformer

from ..core.config import MILVUS_URI
from ..core.utils import logger
from .insert_data import process_and_insert_school, process_and_insert_student
from .schemas import (
    club_fields,
    game_basic_info_fields,
    quote_fields,
    relation_fields,
    school_fields,
    student_fields,
)


def create_collections(
    client: MilvusClient,
    fields: list[FieldSchema],
    collection_name: str,
    description: str = "",
):
    """创建 Milvus 集合

    Args:
        client (MilvusClient): Milvus 客户端实例。
        fields (list[FieldSchema]): 集合字段定义列表。
        collection_name (str): 集合名称。
        description (str, optional): 集合描述。默认为空字符串。
    """

    if client.has_collection(collection_name):
        logger.info(f"集合 '{collection_name}' 已存在，将被删除并重建。")
        client.drop_collection(collection_name)

    schema = CollectionSchema(
        fields=fields, auto_id=True, description=description, enable_dynamic_field=False
    )

    client.create_collection(
        collection_name=collection_name, schema=schema, description=description
    )
    logger.info(f"集合 '{collection_name}' 创建成功。")


def insert_student_data(client: MilvusClient, model: SentenceTransformer):
    """加载所有学生JSON文件并将其插入Milvus"""
    logger.info("开始准备和插入学生数据...")

    # 查找所有学生数据文件
    data_dir = Path(__file__).parents[2] / "data" / "students" / "json"
    if not data_dir.exists():
        logger.warning(f"数据目录不存在: {data_dir}")
        return

    student_files = list(data_dir.glob("*.json"))
    if not student_files:
        logger.warning(f"在 {data_dir} 中未找到学生JSON文件。")
        return

    logger.info(f"找到 {len(student_files)} 个学生文件。开始处理...")

    # 循环处理并插入每个文件
    for file_path in student_files:
        process_and_insert_student(client, model, file_path)

    # Flush集合以确保数据可被搜索
    logger.info("正在刷新 'students' 集合以确保数据可见...")
    client.flush(collection_name="students")
    logger.info("'students' 集合刷新完成。")

    logger.info("正在刷新 'student_quotes' 集合以确保数据可见...")
    client.flush(collection_name="student_quotes")
    logger.info("'student_quotes' 集合刷新完成。")

    logger.info("正在刷新 'student_relations' 集合以确保数据可见...")
    client.flush(collection_name="student_relations")
    logger.info("'student_relations' 集合刷新完成。")


def insert_school_data(client: MilvusClient, model: SentenceTransformer):
    """加载所有学校JSON文件并将其插入Milvus"""

    logger.info("开始准备和插入学校数据...")

    # 查找所有学校数据文件
    data_dir = Path(__file__).parents[2] / "data" / "schools" / "json"
    if not data_dir.exists():
        logger.warning(f"学校数据目录不存在: {data_dir}")
        return

    school_files = list(data_dir.glob("*.json"))
    if not school_files:
        logger.warning(f"在 {data_dir} 中未找到学校JSON文件。")
        return

    logger.info(f"找到 {len(school_files)} 个学校文件。开始处理...")

    # 循环处理并插入每个文件
    for file_path in school_files:
        process_and_insert_school(client, model, file_path)

    # Flush集合以确保数据可被搜索
    logger.info("正在刷新 'schools' 集合...")
    client.flush(collection_name="schools")
    logger.info("'schools' 集合刷新完成。")

    logger.info("正在刷新 'clubs' 集合...")
    client.flush(collection_name="clubs")
    logger.info("'clubs' 集合刷新完成。")


def insert_game_basic_info_data(client: MilvusClient, model: SentenceTransformer):
    """加载游戏基本信息JSON文件并将其插入Milvus"""
    logger.info("开始准备和插入游戏基本信息数据...")

    data_file = Path(__file__).parents[2] / "data" / "games" / "game_info.json"
    if not data_file.exists():
        logger.warning(f"游戏基本信息数据文件不存在: {data_file}")
        return

    try:
        with data_file.open("r", encoding="utf-8") as f:
            game_data = json.load(f)
    except Exception as e:
        logger.error(f"加载游戏基本信息JSON文件失败: {e}")
        return

    all_info_entries = []
    logger.info("正在处理游戏基本信息条目并生成向量...")

    def process_items(category, items, parent_title=None):
        # items 可能是字符串列表，也可能是字典列表
        for item in items:
            if isinstance(item, str):
                # 直接插入
                entry = {
                    "category": category,
                    "title": parent_title or category,
                    "content": item,
                    "vector": model.encode(item, convert_to_tensor=False).tolist(),
                }
                all_info_entries.append(entry)
            elif isinstance(item, dict):
                # 处理字典
                title = item.get("title", parent_title or category)
                # 处理 content
                content = item.get("content", [])
                if isinstance(content, list):
                    for c in content:
                        if c:
                            entry = {
                                "category": category,
                                "title": title,
                                "content": c,
                                "vector": model.encode(
                                    c, convert_to_tensor=False
                                ).tolist(),
                            }
                            all_info_entries.append(entry)
                elif isinstance(content, str):
                    entry = {
                        "category": category,
                        "title": title,
                        "content": content,
                        "vector": model.encode(
                            content, convert_to_tensor=False
                        ).tolist(),
                    }
                    all_info_entries.append(entry)
                # 递归处理 subsections
                subsections = item.get("subsections", [])
                if isinstance(subsections, list) and subsections:
                    process_items(category, subsections, parent_title=title)

    for category, items in game_data.items():
        process_items(category, items)

    if not all_info_entries:
        logger.warning("没有找到可插入的游戏基本信息数据。")
        return

    try:
        logger.info(
            f"正在向 'game_basic_info' 集合插入 {len(all_info_entries)} 条数据..."
        )
        client.insert(collection_name="game_basic_info", data=all_info_entries)
        logger.info("游戏基本信息数据插入成功。")
    except Exception as e:
        logger.error(f"向 'game_basic_info' 集合插入数据时出错: {e}")
        return

    logger.info("正在刷新 'game_basic_info' 集合以确保数据可见...")
    client.flush(collection_name="game_basic_info")
    logger.info("'game_basic_info' 集合刷新完成。")


def build_database():
    """构建 Milvus 数据库并插入初始数据"""

    # if not MILVUS_URI or not MILVUS_TOKEN:
    #     raise ValueError("请在 .env 文件中设置 MILVUS_URI 和 MILVUS_TOKEN")
    if not MILVUS_URI:
        raise ValueError("请在 .env 文件中设置 MILVUS_URI")
    # 初始化 Milvus 客户端
    client = MilvusClient(uri=MILVUS_URI)

    # 创建集合
    collections = [
        ("students", "学生信息集合", student_fields),
        ("student_quotes", "学生名言集合", quote_fields),
        ("student_relations", "学生关系集合", relation_fields),
        ("schools", "学校信息集合", school_fields),
        ("clubs", "社团信息集合", club_fields),
        ("game_basic_info", "游戏基本信息集合", game_basic_info_fields),
    ]
    for name, description, fields in collections:
        try:
            create_collections(client, fields, name, description)
        except Exception as e:
            logger.error(f"创建集合 '{name}' 时出错: {e}")
            continue

    # 加载嵌入模型 (推荐使用多语言模型以处理中英文混合内容)
    model_name = "paraphrase-multilingual-mpnet-base-v2"
    try:
        logger.info(f"正在加载嵌入模型: {model_name}...")
        model = SentenceTransformer(model_name)
        logger.info("嵌入模型加载成功。")
    except Exception as e:
        logger.error(f"加载嵌入模型失败: {e}")
        logger.error(
            "请确保已安装 'sentence-transformers' 和 'torch'。运行: uv add sentence-transformers torch"
        )
        raise

    # 插入学生数据
    insert_student_data(client, model)

    # 插入学校数据
    insert_school_data(client, model)

    # 插入游戏基本信息数据
    insert_game_basic_info_data(client, model)

    # 构建所有向量索引
    logger.info("正在为所有集合构建向量索引...")
    for collection, _, _ in collections:
        try:
            if not client.has_collection(collection):
                logger.warning(f"集合 '{collection}' 不存在，跳过索引构建。")
                continue

            # 自动确定向量字段名
            collection_info = client.describe_collection(collection)
            vector_field = next(
                (
                    f["name"]
                    for f in collection_info["fields"]
                    if f["name"].endswith("vector")
                ),
                None,
            )
            if not vector_field:
                logger.warning(
                    f"在集合 '{collection}' 中未找到向量字段，跳过索引构建。"
                )
                continue

            # 构建索引
            logger.info(f"正在为集合 '{collection}' 构建向量索引...")
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name=vector_field,
                index_type="AUTOINDEX",
                metric_type="L2",
            )
            client.create_index(
                collection_name=collection,
                index_params=index_params,
            )
            logger.info(f"集合 '{collection}' 的向量索引构建成功。")

        except Exception as e:
            logger.error(f"为集合 '{collection}' 构建索引时出错: {e}")
