import asyncio
import json
from pathlib import Path

from markdownify import markdownify as md
from rich.progress import Progress
from utils import get_page_revid, get_page_text, logger


async def main():
    """主函数，爬取学校信息并保存为Markdown文件。"""
    # 从本地文件中读取学生信息
    school_info_path = (
        Path(__file__).parents[1] / "data" / "schools" / "school_info.json"
    )
    if school_info_path.exists():
        with open(school_info_path, "r", encoding="utf-8") as f:
            school_info = json.load(f)
        logger.info("学校信息已加载。")
    else:
        logger.warning(f"学校信息文件 {school_info_path} 不存在，开始爬取学校信息。")
        # 如果文件不存在，则需要爬取学校信息
        from collect_school_info import fetch_and_save_school_info

        await fetch_and_save_school_info()
        with open(school_info_path, "r", encoding="utf-8") as f:
            school_info = json.load(f)
        logger.info("学校信息已加载。")

    output_dir = Path(__file__).parents[1] / "data" / "schools" / "markdown"
    output_dir.mkdir(parents=True, exist_ok=True)

    school_info = school_info

    crawl_results = []

    with Progress() as progress:
        task = progress.add_task("[cyan]保存学校markdown...", total=len(school_info))
        for school in school_info:
            try:
                # 获取页面的最新修订版本号
                revid = await get_page_revid(school)
                output_path = output_dir / f"{school}_{revid}.md"
                if output_path.exists():
                    msg = f"{school} 的 revid={revid} 已存在，跳过更新。"
                    logger.info(msg)
                    crawl_results.append(
                        {
                            "title": school,
                            "revid": revid,
                            "status": "skipped",
                            "msg": msg,
                        }
                    )
                    progress.update(task, advance=1)
                    await asyncio.sleep(2)
                    continue
                html = await get_page_text(school)
                md_text = md(html, heading_style="atx", bullets="-", convert_links=True)
                with open(output_path, "w", encoding="utf-8") as output_file:
                    output_file.write(md_text)
                msg = f"已保存 {school} 的wiki页面的 markdown 版本到 {output_path}"
                logger.info(msg)
                crawl_results.append(
                    {"title": school, "revid": revid, "status": "saved", "msg": msg}
                )
            except Exception as e:
                msg = f"获取 {school} 的wiki页面时出错: {e}"
                logger.error(msg)
                crawl_results.append(
                    {"title": school, "revid": None, "status": "failed", "msg": msg}
                )
            progress.update(task, advance=1)
            await asyncio.sleep(2)

    logger.info("====== 爬取结果汇总 ======")
    for r in crawl_results:
        logger.info(f"{r['title']} | {r['status']} | {r['msg']}")


if __name__ == "__main__":
    asyncio.run(main())
