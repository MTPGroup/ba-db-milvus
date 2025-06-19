import asyncio
import json
from pathlib import Path

from markdownify import markdownify as md
from rich.progress import Progress
from utils import get_page_revid, get_page_text, logger


async def main():
    """主函数，爬取学生信息并保存为Markdown文件。"""
    # 从本地文件中读取学生信息
    students_info_revid = await get_page_revid("蔚蓝档案/学生")
    student_info_path = (
        Path(__file__).parents[1]
        / "data"
        / "students"
        / f"students_info_{students_info_revid}.json"
    )
    if student_info_path.exists():
        with open(student_info_path, "r", encoding="utf-8") as f:
            student_info = json.load(f)
        logger.info("学生信息已加载。")
    else:
        logger.warning(f"学生信息文件 {student_info_path} 不存在，开始爬取学生信息。")
        # 如果文件不存在，则需要爬取学生信息
        from collect_student_info import fetch_and_save_student_info

        await fetch_and_save_student_info()
        with open(student_info_path, "r", encoding="utf-8") as f:
            student_info = json.load(f)
        logger.info("学生信息已加载。")

    output_dir = Path(__file__).parents[1] / "data" / "students" / "markdown"
    output_dir.mkdir(parents=True, exist_ok=True)

    student_info = [
        student
        for student in student_info
        if student.get("标题", "").find("页面不存在") == -1
    ]

    crawl_results = []

    with Progress() as progress:
        task = progress.add_task("[cyan]保存学生markdown...", total=len(student_info))
        for student in student_info:
            # 获取相应学生的wiki页面
            title = student.get("标题", "")
            if title:
                try:
                    # 获取页面的最新修订版本号
                    revid = await get_page_revid(title)
                    output_path = output_dir / f"{title}_{revid}.md"
                    if output_path.exists():
                        msg = f"{title} 的 revid={revid} 已存在，跳过更新。"
                        logger.info(msg)
                        crawl_results.append(
                            {
                                "title": title,
                                "revid": revid,
                                "status": "skipped",
                                "msg": msg,
                            }
                        )
                        progress.update(task, advance=1)
                        await asyncio.sleep(2)
                        continue
                    html = await get_page_text(title)
                    md_text = md(
                        html, heading_style="atx", bullets="-", convert_links=True
                    )
                    with open(output_path, "w", encoding="utf-8") as output_file:
                        output_file.write(md_text)
                    msg = f"已保存 {title} 的wiki页面的 markdown 版本到 {output_path}"
                    logger.info(msg)
                    crawl_results.append(
                        {"title": title, "revid": revid, "status": "saved", "msg": msg}
                    )
                except Exception as e:
                    msg = f"获取 {title} 的wiki页面时出错: {e}"
                    logger.error(msg)
                    crawl_results.append(
                        {"title": title, "revid": None, "status": "failed", "msg": msg}
                    )
            else:
                msg = "学生信息中没有有效的姓名，跳过该学生。"
                logger.warning(msg)
                crawl_results.append(
                    {"title": title, "revid": None, "status": "invalid", "msg": msg}
                )
            progress.update(task, advance=1)
            await asyncio.sleep(2)

    logger.info("====== 爬取结果汇总 ======")
    for r in crawl_results:
        logger.info(f"{r['title']} | {r['status']} | {r['msg']}")


if __name__ == "__main__":
    asyncio.run(main())
