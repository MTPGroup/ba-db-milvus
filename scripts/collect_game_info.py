import asyncio
from pathlib import Path

from markdownify import markdownify as md
from utils import get_page_revid, get_page_text, logger


async def fetch_and_save_game_info(revid=None):
    """主函数，爬取游戏信息并保存为Markdown文件。"""

    # 从本地文件中读取游戏信息
    game_info_revid = revid if revid else await get_page_revid("蔚蓝档案")
    game_info_path = (
        Path(__file__).parents[1] / "data" / "games" / f"game_info_{game_info_revid}.md"
    )
    game_info_path.parent.mkdir(parents=True, exist_ok=True)

    if game_info_path.exists():
        logger.info("已存在游戏信息文件。")
        return
    else:
        logger.warning(f"游戏信息文件 {game_info_path} 不存在，开始爬取游戏信息。")
        # 如果文件不存在，则需要爬取游戏信息
        html = await get_page_text("蔚蓝档案")
        md_text = md(html, heading_style="atx", bullets="-", convert_links=True)
        with open(game_info_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        logger.info(f"游戏信息已保存到 {game_info_path}。")


if __name__ == "__main__":
    asyncio.run(fetch_and_save_game_info())
