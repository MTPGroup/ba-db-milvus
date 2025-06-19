from pymilvus import DataType, FieldSchema

from ..core.config import VECTOR_DIM

student_fields = [
    FieldSchema(
        name="student_id",
        dtype=DataType.INT64,
        is_primary=True,
        description="学生ID",
    ),
    FieldSchema(
        name="name", dtype=DataType.VARCHAR, max_length=64, description="学生姓名"
    ),
    FieldSchema(
        name="school", dtype=DataType.VARCHAR, max_length=64, description="学校名称"
    ),
    FieldSchema(
        name="aliases", dtype=DataType.VARCHAR, max_length=256, description="学生别名"
    ),
    FieldSchema(
        name="profile", dtype=DataType.VARCHAR, max_length=2048, description="学生档案"
    ),
    FieldSchema(
        name="introduction",
        dtype=DataType.VARCHAR,
        max_length=8192,
        description="学生介绍",
    ),
    FieldSchema(
        name="experience",
        dtype=DataType.VARCHAR,
        max_length=16384,
        description="学生经历",
    ),
    FieldSchema(
        name="tags", dtype=DataType.VARCHAR, max_length=512, description="学生标签"
    ),
    FieldSchema(
        name="related_students",
        dtype=DataType.VARCHAR,
        max_length=256,
        description="相关学生列表 (逗号分隔)",
    ),
    FieldSchema(
        name="vector",
        dtype=DataType.FLOAT_VECTOR,
        dim=VECTOR_DIM,
        description="学生向量表示",
    ),
]

quote_fields = [
    FieldSchema(
        name="quote_id",
        dtype=DataType.INT64,
        is_primary=True,
        description="台词ID",
    ),
    FieldSchema(
        name="student_name",
        dtype=DataType.VARCHAR,
        max_length=64,
        description="关联的学生姓名",
    ),
    FieldSchema(
        name="version",
        dtype=DataType.VARCHAR,
        max_length=32,
        description="台词版本，如'原始','新年'",
    ),
    FieldSchema(
        name="quote_text",
        dtype=DataType.VARCHAR,
        max_length=1024,
        description="台词内容",
    ),
    FieldSchema(
        name="quote_vector",
        dtype=DataType.FLOAT_VECTOR,
        dim=VECTOR_DIM,
        description="台词向量表示",
    ),
]

relation_fields = [
    FieldSchema(
        name="relation_id",
        dtype=DataType.INT64,
        is_primary=True,
        description="关系ID",
    ),
    FieldSchema(
        name="student_name",
        dtype=DataType.VARCHAR,
        max_length=64,
        description="学生姓名",
    ),
    FieldSchema(
        name="related_student_name",
        dtype=DataType.VARCHAR,
        max_length=64,
        description="相关学生姓名",
    ),
    FieldSchema(
        name="relation_type",
        dtype=DataType.VARCHAR,
        max_length=64,
        description="关系类型，如'便利屋68'",
    ),
    FieldSchema(
        name="relation_vector",
        dtype=DataType.FLOAT_VECTOR,
        dim=VECTOR_DIM,
        description="关系向量表示",
    ),
]

school_fields = [
    FieldSchema(
        name="school_id",
        dtype=DataType.INT64,
        is_primary=True,
        description="学校ID",
    ),
    FieldSchema(
        name="name", dtype=DataType.VARCHAR, max_length=128, description="学校名称"
    ),
    FieldSchema(
        name="basic_info",
        dtype=DataType.VARCHAR,
        max_length=1024,
        description="基本资料",
    ),
    FieldSchema(
        name="introduction",
        dtype=DataType.VARCHAR,
        max_length=4096,
        description="学校简介",
    ),
    FieldSchema(
        name="facilities",
        dtype=DataType.VARCHAR,
        max_length=2048,
        description="校内设施",
    ),
    FieldSchema(
        name="students_and_clubs",
        dtype=DataType.VARCHAR,
        max_length=16384,
        description="学生与社团信息",
    ),
    FieldSchema(
        name="history",
        dtype=DataType.VARCHAR,
        max_length=4096,
        description="学校历史",
    ),
    FieldSchema(
        name="overview",
        dtype=DataType.VARCHAR,
        max_length=4096,
        description="学校概况",
    ),
    FieldSchema(
        name="vector",
        dtype=DataType.FLOAT_VECTOR,
        dim=VECTOR_DIM,
        description="学校文本向量",
    ),
]

club_fields = [
    FieldSchema(
        name="club_id",
        dtype=DataType.INT64,
        is_primary=True,
        description="社团ID",
    ),
    FieldSchema(
        name="name", dtype=DataType.VARCHAR, max_length=64, description="社团名称"
    ),
    FieldSchema(
        name="school", dtype=DataType.VARCHAR, max_length=128, description="所属学校"
    ),
    FieldSchema(
        name="description",
        dtype=DataType.VARCHAR,
        max_length=8192,
        description="社团描述",
    ),
    FieldSchema(
        name="vector",
        dtype=DataType.FLOAT_VECTOR,
        dim=VECTOR_DIM,
        description="社团描述的向量",
    ),
]

game_basic_info_fields = [
    FieldSchema(
        name="info_id",
        dtype=DataType.INT64,
        is_primary=True,
        description="游戏信息ID",
    ),
    FieldSchema(
        name="category",
        dtype=DataType.VARCHAR,
        max_length=64,
        description="信息类别，如'背景设定','游戏系统'",
    ),
    FieldSchema(
        name="title", dtype=DataType.VARCHAR, max_length=128, description="条目标题"
    ),
    FieldSchema(
        name="content",
        dtype=DataType.VARCHAR,
        max_length=65535,
        description="条目内容",
    ),
    FieldSchema(
        name="vector",
        dtype=DataType.FLOAT_VECTOR,
        dim=VECTOR_DIM,
        description="内容向量",
    ),
]
