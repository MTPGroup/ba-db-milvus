import asyncio
import json
from pathlib import Path

import httpx
from utils import logger


async def fetch_and_save_school_info():
    """爬取并保存学校信息"""
    output_file = Path(__file__).parents[1] / "data" / "schools" / "school_info.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    logger.info("开始爬取学校信息...")
    async with httpx.AsyncClient() as client:
        url = "https://moegirl.icu/api.php"
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": "Category:蔚蓝档案学校及地区",
            "format": "json",
            "formatversion": 2,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            pages = data.get("query", {}).get("categorymembers", [])
            # 如果存在 cmcontinue，则需要继续获取下一页
            while "continue" in data:
                params["cmcontinue"] = data["continue"]["cmcontinue"]
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                pages.extend(data.get("query", {}).get("categorymembers", []))
        except Exception as e:
            logger.error(f"请求错误: {e}")
            raise
    # 提取页面标题
    titles = [page["title"] for page in pages if "title" in page]
    output_file = Path(__file__).parents[1] / "data" / "schools" / "school_info.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(titles, f, ensure_ascii=False, indent=4)
    logger.info(f"学校信息已保存到 {output_file}，共 {len(titles)} 个学校。")


if __name__ == "__main__":
    asyncio.run(fetch_and_save_school_info())
