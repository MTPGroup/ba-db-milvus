import asyncio
import json
from pathlib import Path

import mistune
from mistune.plugins.formatting import strikethrough
from mistune.plugins.table import table
from utils import (
    extract_text_from_node,
    extract_text_from_table,
    get_page_revid,
    logger,
)


def flatten_section_content(section_nodes):
    """将section下的内容合并为结构化内容（table转为文本）"""
    result = []
    current_sub = None
    for node in section_nodes:
        # 四级标题，作为子块
        if node.get("type") == "heading" and node.get("attrs", {}).get("level") == 4:
            sub_title = extract_text_from_node(node).strip()
            current_sub = {"sub_title": sub_title, "content": []}
            result.append(current_sub)
        elif node.get("type") in ("paragraph", "list", "table"):
            text = None
            if node.get("type") == "paragraph":
                text = extract_text_from_node(node).strip()
            elif node.get("type") == "list":
                # 提取列表文本
                items = []
                for item in node.get("children", []):
                    if item.get("type") == "list_item":
                        items.append(extract_text_from_node(item).strip())
                text = "\n".join(items)
            elif node.get("type") == "table":
                # 可用你已有的 extract_text_from_table
                text = extract_text_from_table(node)
            if text:
                if current_sub:
                    current_sub["content"].append(text)
                else:
                    result.append(text)
        # 可扩展更多类型
    return result


def flatten_section_content_to_text(section_nodes):
    """递归提取所有文本为纯文本字符串"""
    texts = []
    for node in section_nodes:
        if node.get("type") in ("paragraph", "heading"):
            text = extract_text_from_node(node).strip()
            if text:
                texts.append(text)
        elif node.get("type") == "list":
            for item in node.get("children", []):
                if item.get("type") == "list_item":
                    item_text = extract_text_from_node(item).strip()
                    if item_text:
                        texts.append(item_text)
        elif node.get("type") == "table":
            table_text = extract_text_from_table(node)
            if table_text:
                texts.append(table_text)
        # 可递归处理嵌套结构
        if "children" in node and node.get("type") not in ("list", "table"):
            texts.append(flatten_section_content_to_text(node["children"]))
    return "\n".join(t for t in texts if t)


def parse_section_by_level(nodes, level):
    """递归按标题级别分组，level为当前分组的标题级别（如3/4/5）"""
    result = []
    current = None
    for node in nodes:
        if (
            node.get("type") == "heading"
            and node.get("attrs", {}).get("level") == level
        ):
            if current:
                result.append(current)
            title = extract_text_from_node(node).strip()
            current = {"title": title, "content": []}
        elif node.get("type") in ("paragraph", "list", "table"):
            text = None
            if node.get("type") == "paragraph":
                text = extract_text_from_node(node).strip()
            elif node.get("type") == "list":
                items = []
                for item in node.get("children", []):
                    if item.get("type") == "list_item":
                        items.append(extract_text_from_node(item).strip())
                text = "\n".join(items)
            elif node.get("type") == "table":
                text = extract_text_from_table(node)
            if text and current:
                current["content"].append(text)
        elif (
            node.get("type") == "heading" and node.get("attrs", {}).get("level") > level
        ):
            # 递归处理下一级标题
            sub_nodes = [node]
            idx = nodes.index(node) + 1
            while idx < len(nodes) and not (
                nodes[idx].get("type") == "heading"
                and nodes[idx].get("attrs", {}).get("level") <= level
            ):
                sub_nodes.append(nodes[idx])
                idx += 1
            subs = parse_section_by_level(sub_nodes, level + 1)
            if subs and current:
                current.setdefault("subsections", []).extend(subs)
    if current:
        result.append(current)
    return result


def extract_sections(ast, section_names):
    """按二级标题分块，提取指定section内容"""
    sections = {}
    current_section = None
    current_content = []
    for node in ast:
        # 识别二级标题
        if node.get("type") == "heading" and node.get("attrs", {}).get("level") == 2:
            # 保存上一个section
            if current_section and current_section in section_names:
                sections[current_section] = list(current_content)
            # 新section
            current_section = extract_text_from_node(node).strip()
            current_content = []
        else:
            if current_section and current_section in section_names:
                current_content.append(node)
    # 保存最后一个section
    if current_section and current_section in section_names:
        sections[current_section] = list(current_content)
    return sections


async def main():
    """主函数, 解析游戏信息文件为 Json。"""

    # 从本地文件中读取游戏信息
    game_info_revid = await get_page_revid("蔚蓝档案")
    game_info_path = (
        Path(__file__).parents[1] / "data" / "games" / f"game_info_{game_info_revid}.md"
    )
    game_info_path.parent.mkdir(parents=True, exist_ok=True)

    if game_info_path.exists():
        logger.info("已存在游戏信息文件。")
    else:
        logger.warning(f"游戏信息文件 {game_info_path} 不存在，开始爬取游戏信息。")
        # 如果文件不存在，则需要爬取游戏信息
        from collect_game_info import fetch_and_save_game_info

        await fetch_and_save_game_info(revid=game_info_revid)

    # 解析 markdown 文件
    md_text = game_info_path.read_text(encoding="utf-8")
    markdown = mistune.create_markdown(renderer="ast", plugins=[table, strikethrough])
    ast = markdown(md_text)

    section_names = ["背景设定（世界观）", "游戏系统"]
    sections = extract_sections(ast, section_names)

    # 展开内容
    structured = {}
    for sec, nodes in sections.items():
        if sec == "游戏系统":
            structured[sec] = parse_section_by_level(nodes, 3)
        else:
            structured[sec] = flatten_section_content(nodes)
    output_file = Path(__file__).parents[1] / "data" / "games" / "game_info.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(structured, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    asyncio.run(main())
