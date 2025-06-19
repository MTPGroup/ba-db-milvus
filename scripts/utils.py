import logging

import httpx
from bs4 import BeautifulSoup
from rich.logging import RichHandler
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed


def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")

    for h2 in soup.find_all("h2"):
        headline_span = h2.find("span", class_="mw-headline")
        if headline_span:
            # 用 headline span 里的纯文本替换 h2 的全部内容
            h2.string = headline_span.get_text(strip=True)
    for h3 in soup.find_all("h3"):
        headline_span = h3.find("span", class_="mw-headline")
        if headline_span:
            # 用 headline span 里的纯文本替换 h3 的全部内容
            h3.string = headline_span.get_text(strip=True)

    # 去除所有 <script> 和 <style> 标签
    for tag in soup(["script", "style", "link"]):
        tag.decompose()

    # 去除模板、导航等无关内容
    for cls in [
        "infoBox",
        "mobile-noteTA-0",
        "toc",
        "navbox largeNavbox",
        "mw-editsection-bracket",
        "notice dablink",
    ]:
        for tag in soup.find_all(class_=cls):
            tag.decompose()

    # 返回清理后的 HTML
    return str(soup)


def extract_text_from_node(node):
    """递归提取节点内所有文本"""
    if node.get("type") == "text":
        return node.get("raw", "")
    if node.get("type") == "strong":
        return "".join(
            extract_text_from_node(child) for child in node.get("children", [])
        )
    if node.get("type") == "emphasis":
        return "".join(
            extract_text_from_node(child) for child in node.get("children", [])
        )
    if node.get("type") == "link":
        return "".join(
            extract_text_from_node(child) for child in node.get("children", [])
        )
    if node.get("type") == "paragraph":
        return "".join(
            extract_text_from_node(child) for child in node.get("children", [])
        )
    if node.get("type") == "image":
        return node.get("attrs", {}).get("title", "") or "".join(
            extract_text_from_node(child) for child in node.get("children", [])
        )
    if "children" in node:
        return "".join(extract_text_from_node(child) for child in node["children"])
    return ""


def extract_text_from_table(table_node):
    """将table节点转为纯文本（每行用 | 分隔）"""
    lines = []
    for child in table_node.get("children", []):
        if child.get("type") in ("table_head", "table_body"):
            for row in child.get("children", []):
                if row.get("type") == "table_row":
                    cells = row.get("children", [])
                    line = (
                        "| "
                        + " | ".join(
                            extract_text_from_node(cell).strip() for cell in cells
                        )
                        + " |"
                    )
                    lines.append(line)
    return "\n".join(lines)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.RequestError)),
)
async def get_page_revid(title: str) -> int:
    """获取指定页面的修订版本号"""
    url = "https://moegirl.icu/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "ids",
        "format": "json",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    async with httpx.AsyncClient() as ctx:
        resp = await ctx.get(url, params=params, headers=headers, timeout=20.0)
        data = resp.json()
        page = next(iter(data["query"]["pages"].values()))
        return page["revisions"][0]["revid"]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.RequestError)),
)
async def get_page_text(title: str, redirect_count: int = 0) -> str:
    """获取指定页面的HTML内容，并自动处理重定向。

    Args:
        title (str): 页面标题
        redirect_count (int, optional): 当前重定向次数，用于防止无限循环. Defaults to 0.

    Returns:
        str: 清理后的HTML字符串
    """

    url = "https://moegirl.icu/api.php"
    params = {
        "action": "parse",
        "page": title,
        "format": "json",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    async with httpx.AsyncClient() as ctx:
        try:
            resp = await ctx.get(url, params=params, headers=headers, timeout=20.0)
            logger.info(f"爬取页面: {title} - 状态码: {resp.status_code}")
            data = resp.json()
            html = data["parse"]["text"]["*"]

            if "parse" not in data or "text" not in data["parse"]:
                logger.warning(
                    f"页面 '{title}' 的 API 响应格式不正确，缺少 'parse' 或 'text' 键。"
                )
                return ""

            # 解析HTML以检查重定向
            soup = BeautifulSoup(html, "html.parser")
            redirect_div = soup.find("div", class_="redirectMsg")

            if redirect_div:
                redirect_link = redirect_div.find("a")
                if redirect_link and redirect_link.get("title"):
                    new_title = redirect_link.get("title")
                    logger.info(f"页面 '{title}' 重定向到 '{new_title}'，正在跟随...")
                    # 递归调用自身以获取新页面的内容
                    return await get_page_text(new_title, redirect_count + 1)
                else:
                    logger.warning(f"在页面 '{title}' 上找到重定向，但无法提取新标题。")
                    return ""
            return clean_html(html)
        except httpx.ConnectTimeout:
            logger.error(f"请求超时: {title}")
            raise
        except Exception as e:
            logger.error(f"请求失败: {title} - {e}")
            raise


logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()],
)
logger = logging.getLogger("rich")
