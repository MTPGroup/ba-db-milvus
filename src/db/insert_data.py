import json
from pathlib import Path

from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer

from ..core.utils import logger


def _format_text_from_sections(data, keys):
    """辅助函数，用于从JSON数据的多个部分格式化文本。"""

    full_text = []
    for key in keys:
        if key in data:
            section = data[key]
            if isinstance(section, list):
                for item in section:
                    if isinstance(item, str):
                        full_text.append(item)
                    elif isinstance(item, dict) and "content" in item:
                        if isinstance(item["content"], list):
                            full_text.extend(item["content"])
                        else:
                            full_text.append(str(item["content"]))
            else:
                full_text.append(str(section))
    # 清理并连接文本
    return "\n".join(
        [line.strip().replace("|", "") for line in full_text if line.strip()]
    )


def process_and_insert_quotes(
    client: MilvusClient,
    model: SentenceTransformer,
    student_name: str,
    quotes_data: dict,
):
    """处理并插入单个学生的所有台词。"""

    if not quotes_data:
        return

    quotes_to_insert = []
    for version, lines in quotes_data.items():
        if not isinstance(lines, list):
            continue
        for line in lines:
            # 简单清洗，去除空行和多余空格
            cleaned_line = line["line"].strip()
            if not cleaned_line:
                continue

            # 生成向量
            vector = model.encode(cleaned_line, convert_to_tensor=False).tolist()
            quotes_to_insert.append(
                {
                    "student_name": student_name,
                    "version": version,
                    "quote_text": cleaned_line,
                    "quote_vector": vector,
                }
            )

    if quotes_to_insert:
        try:
            result = client.insert(
                collection_name="student_quotes", data=quotes_to_insert
            )
            logger.info(
                f"为学生 '{student_name}' 成功插入 {len(quotes_to_insert)} 条台词, IDs: {result['ids']}"
            )
        except Exception as e:
            logger.error(f"为学生 '{student_name}' 插入台词时失败: {e}")


def process_and_insert_relations(
    client: MilvusClient,
    model: SentenceTransformer,
    student_name: str,
    profile_data: dict,
):
    """处理并插入单个学生的人物关系。"""
    related_persons_list = profile_data.get("相关人物_list", [])
    # 如果列表为空，则尝试解析字符串
    if not related_persons_list:
        related_persons_str = profile_data.get("相关人物", "")
        if related_persons_str:
            related_persons_list = [
                name.strip() for name in related_persons_str.split(",")
            ]

    if not related_persons_list:
        return

    # 使用学生的所属团体作为关系类型的代理
    relation_type = profile_data.get("所属团体", "未知关系")

    relations_to_insert = []
    for related_name in related_persons_list:
        if not related_name:
            continue

        # 创建一个描述性句子用于生成向量
        embedding_text = f"{student_name}与{related_name}的关系是{relation_type}。"
        vector = model.encode(embedding_text, convert_to_tensor=False).tolist()

        relations_to_insert.append(
            {
                "student_name": student_name,
                "related_student_name": related_name,
                "relation_type": relation_type,
                "relation_vector": vector,
            }
        )

    if relations_to_insert:
        try:
            result = client.insert(
                collection_name="student_relations", data=relations_to_insert
            )
            logger.info(
                f"为学生 '{student_name}' 成功插入 {len(relations_to_insert)} 条人物关系, IDs: {result['ids']}"
            )
        except Exception as e:
            logger.error(f"为学生 '{student_name}' 插入人物关系时失败: {e}")


def process_and_insert_student(
    client: MilvusClient, model: SentenceTransformer, json_file_path: Path
):
    """
    处理单个学生的JSON数据文件，生成嵌入向量，并插入到'students'集合中。
    """

    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        student_profile = data.get("学生档案", {})

        # 提取和组合数据字段
        name = student_profile.get("译名", json_file_path.stem)
        affiliation_string = student_profile.get("所属团体", "")
        school_map = {
            "三一": "三一综合学园",
            "格赫娜": "格赫娜学园",
            "千年": "千年科学学园",
            "阿拜多斯": "阿拜多斯高中",
            "赤冬": "赤冬联邦学园",
            "山海经": "山海经高级中学",
            "瓦尔基里": "瓦尔基里警察学校",
            "SRT": "SRT特殊学园",
            "百鬼夜行": "百鬼夜行联合学园",
            "阿里乌斯": "阿里乌斯分校",
        }
        school = "未知"  # 默认值
        for keyword, full_name in school_map.items():
            if keyword in affiliation_string:
                school = full_name
                break
        aliases = student_profile.get("别号", "")
        tags = student_profile.get("萌点", "")
        related_students = ", ".join(student_profile.get("related_persons_list", []))

        profile_text = "\n".join([f"{k}: {v}" for k, v in student_profile.items()])
        introduction_text = _format_text_from_sections(data, ["简介", "人物设定"])
        experience_text = _format_text_from_sections(data, ["人物经历", "角色相关"])

        # 为嵌入生成一段全面的文本
        embedding_text = (
            f"姓名: {name}\n"
            f"简介: {introduction_text}\n"
            f"经历: {experience_text}\n"
            f"档案: {profile_text}"
        )

        # 生成向量
        vector = model.encode(embedding_text, convert_to_tensor=False).tolist()

        # 准备插入数据 (注意截断以符合schema长度限制)
        student_data = {
            "name": name,
            "school": school,
            "aliases": aliases,
            "profile": profile_text[:1024],
            "introduction": introduction_text[:2048],
            "experience": experience_text[:4096],
            "tags": tags[:512],
            "related_students": related_students[:256],
            "vector": vector,
        }

        # 插入数据
        student_insert_result = client.insert(
            collection_name="students", data=student_data
        )
        logger.info(f"成功插入学生: {name}, IDs: {student_insert_result['ids']}")

        # 处理并插入台词
        quotes_data = data.get("角色台词", {})
        process_and_insert_quotes(client, model, name, quotes_data)

        # 处理并插入人物关系
        process_and_insert_relations(client, model, name, student_profile)

        return student_insert_result

    except Exception as e:
        logger.error(f"处理或插入学生 '{json_file_path.stem}' 时失败: {e}")
        return None


def process_and_insert_clubs(
    client: MilvusClient, model: SentenceTransformer, school_name: str, clubs_data: list
):
    """从学校数据中提取社团信息，并插入到'clubs'集合中。"""

    if not clubs_data:
        return

    clubs_to_insert = []
    for club_section in clubs_data:
        if not isinstance(club_section, dict) or "sub_title" not in club_section:
            continue

        club_name = club_section.get("sub_title", "").strip()
        content_list = club_section.get("content", [])
        content_list = [content for content in content_list if content.find("|") == -1]

        if not club_name or not content_list:
            continue

        # 将描述内容列表合并为单个字符串
        description_text = "\n".join(
            [str(item).strip() for item in content_list if str(item).strip()]
        )

        # 为嵌入生成文本
        embedding_text = (
            f"学校: {school_name}\n社团: {club_name}\n描述: {description_text}"
        )
        vector = model.encode(embedding_text, convert_to_tensor=False).tolist()

        clubs_to_insert.append(
            {
                "name": club_name,
                "school": school_name,
                "description": description_text[:2048],  # 安全截断以符合schema
                "vector": vector,
            }
        )

    if clubs_to_insert:
        try:
            result = client.insert(collection_name="clubs", data=clubs_to_insert)
            logger.info(
                f"为学校 '{school_name}' 成功插入 {len(clubs_to_insert)} 个社团, IDs: {result['ids']}"
            )
        except Exception as e:
            logger.error(f"为学校 '{school_name}' 插入社团时失败: {e}")


def process_and_insert_school(
    client: MilvusClient, model: SentenceTransformer, json_file_path: Path
):
    """处理单个学校的JSON数据文件，生成嵌入向量，并插入到'schools'集合中。"""
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 提取和组合数据字段
        basic_info_dict = data.get("基本资料", {})
        name = basic_info_dict.get("学校名称", json_file_path.stem)

        # 使用辅助函数格式化各个文本部分
        basic_info_text = "\n".join([f"{k}: {v}" for k, v in basic_info_dict.items()])
        introduction_text = _format_text_from_sections(data, ["简介"])
        facilities_text = _format_text_from_sections(data, ["校内设施"])
        students_and_clubs_text = _format_text_from_sections(data, ["学生与社团"])
        history_text = _format_text_from_sections(data, ["历史"])
        overview_text = _format_text_from_sections(data, ["概况"])

        # 为嵌入生成一段全面的文本
        embedding_text = (
            f"学校名称: {name}\n"
            f"基本资料: {basic_info_text}\n"
            f"简介: {introduction_text}\n"
            f"设施: {facilities_text}\n"
            f"学生与社团: {students_and_clubs_text}\n"
            f"历史与概况: {history_text}\n{overview_text}"
        )

        # 生成向量
        vector = model.encode(embedding_text, convert_to_tensor=False).tolist()

        # 准备插入数据 (使用切片进行安全截断)
        school_data = {
            "name": name[:64],
            "basic_info": basic_info_text[:1024],
            "introduction": introduction_text[:4096],
            "facilities": facilities_text[:2048],
            "students_and_clubs": students_and_clubs_text[:8192],
            "history": history_text[:4096],
            "overview": overview_text[:4096],
            "vector": vector,
        }

        # 插入数据
        school_insert_result = client.insert(
            collection_name="schools", data=school_data
        )
        logger.info(f"成功插入学校: {name}, IDs: {school_insert_result['ids']}")

        club_data = data.get("学生与社团", [])
        process_and_insert_clubs(client, model, name, club_data)

        return school_insert_result

    except Exception as e:
        logger.error(f"处理或插入学校 '{json_file_path.stem}' 时失败: {e}")
        return None
