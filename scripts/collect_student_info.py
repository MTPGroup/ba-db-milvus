import asyncio
import json
from pathlib import Path
from venv import logger

from bs4 import BeautifulSoup
from utils import get_page_revid, get_page_text


def extract_student_data(html_content: str) -> list:
    """从Wiki页面的HTML内容中提取学生信息。

    Args:
        html_content (str): Wiki页面的HTML内容。

    Returns:
        list:  提取的学生信息列表，每个学生信息是一个字典。
    """
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find(
        "table",
        class_="wikitable AnnTools-MWFilter-result AnnTools-MWFilter-result-text-align-center sortable",
    )
    if not table:
        return []

    headers = [th.get_text(strip=True) for th in table.find_all("th")]

    try:
        name_index = headers.index("姓名")
    except ValueError:
        return []

    # student_dict = {}
    student_list = []
    for row in table.find("tbody").find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < len(headers):
            continue

        name_cell = cells[name_index]
        link = name_cell.find("a")
        if not (link and "title" in link.attrs):
            continue

        # student_name_key = link['title']

        row_data = {}
        for i, header in enumerate(headers):
            value = cells[i].get("data-value", cells[i].get_text(strip=True))
            row_data[header] = value

        # student_dict[student_name_key] = row_data
        title = link["title"]
        row_data["标题"] = title
        student_list.append(row_data)

    return student_list


async def fetch_and_save_student_info():
    """主函数，爬取学生信息并保存为JSON文件。"""
    # 获取 revid
    revid = await get_page_revid("蔚蓝档案/学生")
    output_file = (
        Path(__file__).parents[1] / "data" / "students" / f"students_info_{revid}.json"
    )
    if output_file.exists():
        logger.info(f"学生信息文件 {output_file} 已存在，跳过更新。")
        return
    # 爬取学生信息并转换为Markdown格式
    html = await get_page_text("蔚蓝档案/学生")
    # md_text = md(html, heading_style="atx", bullets="-", convert_links=True)
    # 提取学生数据
    student_data = extract_student_data(html)
    # 保存学生数据为 JSON 文件
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(student_data, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    asyncio.run(fetch_and_save_student_info())
