from src.core.utils import logger
from src.db.builder import build_database

if __name__ == "__main__":
    try:
        logger.info("启动数据库构建流程...")
        build_database()
        logger.info("数据库构建流程成功完成。")
    except Exception as e:
        logger.error(f"数据库构建过程中发生错误: {e}")
        # 可以在这里添加更详细的错误处理
