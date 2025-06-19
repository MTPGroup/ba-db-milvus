import json
import re
from pathlib import Path

import mistune
from mistune.plugins.formatting import strikethrough
from mistune.plugins.table import table
from rich.progress import Progress
from utils import extract_text_from_node, extract_text_from_table, logger


def extract_text_from_cell(cell):
    """递归提取cell内所有文本"""
    if "raw" in cell:
        return cell["raw"]
    if "children" in cell:
        return "".join(extract_text_from_cell(child) for child in cell["children"])
    return ""


def extract_links_from_cell(cell) -> list[str]:
    """递归提取cell内所有 link/text 的人物名"""
    names = []
    if cell.get("type") == "link":
        # 只提取 link 的文本
        for child in cell.get("children", []):
            if child.get("type") == "text":
                names.append(child.get("raw", "").strip())
    elif cell.get("type") == "text":
        # 逗号、顿号分隔的文本也可能有
        for name in cell.get("raw", "").replace("、", ",").split(","):
            name = name.strip()
            if name:
                names.append(name)
    elif "children" in cell:
        for child in cell["children"]:
            names.extend(extract_links_from_cell(child))
    return names


def extract_profile_table_from_ast(ast):
    profile = {}
    related_persons = []
    for node in ast:
        if node.get("type") == "table":
            for child in node.get("children", []):
                if child.get("type") == "table_body":
                    rows = child.get("children", [])
                    i = 0
                    while i < len(rows):
                        row = rows[i]
                        if row.get("type") != "table_row":
                            i += 1
                            continue
                        cells = row.get("children", [])
                        key = (
                            extract_text_from_cell(cells[0]).strip()
                            if len(cells) > 0
                            else ""
                        )
                        value = (
                            extract_text_from_cell(cells[1]).strip()
                            if len(cells) > 1
                            else ""
                        )
                        # 跳过空行和表头
                        if not key or key in ["学生档案", "基本资料"]:
                            i += 1
                            continue
                        # 处理相关人物
                        if key == "相关人物":
                            # 下一行是具体人物
                            if i + 1 < len(rows):
                                next_row = rows[i + 1]
                                next_cells = next_row.get("children", [])
                                if next_cells:
                                    related_persons = extract_links_from_cell(
                                        next_cells[0]
                                    )
                                    # 过滤掉包含括号或冒号的名字
                                    related_persons = [
                                        person
                                        for person in related_persons
                                        if person.find("）") == -1
                                        and person.find("：") == -1
                                    ]
                                    profile["相关人物"] = ",".join(related_persons)
                                    profile["相关人物_list"] = related_persons
                                i += 2
                                continue
                        # 普通字段
                        if key and value:
                            profile[key] = value
                        i += 1
            break
    return profile


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


def flatten_section_content(section_nodes):
    """将section下的内容合并为纯文本或结构化内容"""
    result = []
    for node in section_nodes:
        if node.get("type") == "heading" and node.get("attrs", {}).get("level") == 3:
            # 三级标题，作为子块
            sub_title = extract_text_from_node(node).strip()
            result.append({"sub_title": sub_title, "content": []})
        elif node.get("type") == "paragraph":
            text = extract_text_from_node(node).strip()
            if text:
                # 放到最近的三级标题下，否则直接加到result
                if result and isinstance(result[-1], dict) and "content" in result[-1]:
                    result[-1]["content"].append(text)
                else:
                    result.append(text)
        elif node.get("type") == "table":
            table_text = extract_text_from_table(node)
            if table_text:
                if result and isinstance(result[-1], dict) and "content" in result[-1]:
                    result[-1]["content"].append(table_text)
                else:
                    result.append(table_text)
        # 可扩展更多类型
    return result


def parse_game_data_section(ast):
    game_data = {}
    in_game_data = False
    current_version = None
    current_content = []
    for node in ast:
        # 找到“游戏数据”二级标题
        if node.get("type") == "heading" and node.get("attrs", {}).get("level") == 2:
            title = extract_text_from_node(node).strip()
            if title == "游戏数据":
                in_game_data = True
                continue
            elif in_game_data:
                # 离开游戏数据section
                break
        if not in_game_data:
            continue
        # 三级标题作为版本名
        if node.get("type") == "heading" and node.get("attrs", {}).get("level") == 3:
            if current_version and current_content:
                game_data[current_version] = current_content
            current_version = extract_text_from_node(node).strip()
            current_content = []
        elif node.get("type") == "paragraph":
            text = extract_text_from_node(node).strip()
            if text:
                current_content.append(text)
        elif node.get("type") == "table":
            table_text = extract_text_from_table(node)
            if table_text:
                current_content.append(table_text)
    # 最后一个版本
    if current_version and current_content:
        game_data[current_version] = current_content
    return game_data


def extract_table_as_list(table_node):
    """将table节点转为台词列表，每行是dict"""
    result = []
    headers = []
    for child in table_node.get("children", []):
        if child.get("type") == "table_head":
            for row in child.get("children", []):
                if row.get("type") == "table_cell":
                    headers.append(extract_text_from_node(row).strip())
        if child.get("type") == "table_body":
            for row in child.get("children", []):
                if row.get("type") == "table_row":
                    cells = row.get("children", [])
                    row_data = [extract_text_from_node(cell).strip() for cell in cells]
                    # 跳过全空行
                    if not any(row_data) or row_data[0] == "场合":
                        continue
                    # 只保留有内容的前两列
                    if len(row_data) >= 2:
                        result.append({"occasion": row_data[0], "line": row_data[1]})
    return result


def parse_quotes_section(ast):
    quotes = {}
    in_quotes = False
    current_version = None
    for node in ast:
        # 找到“角色台词”二级标题
        if node.get("type") == "heading" and node.get("attrs", {}).get("level") == 2:
            title = extract_text_from_node(node).strip()
            if title == "角色台词":
                in_quotes = True
                continue
            elif in_quotes:
                break
        if not in_quotes:
            continue
        # 三级标题作为版本名
        if node.get("type") == "heading" and node.get("attrs", {}).get("level") == 3:
            current_version = extract_text_from_node(node).strip()
            quotes[current_version] = []
        elif node.get("type") == "table" and current_version:
            quotes[current_version].extend(extract_table_as_list(node))
    return quotes


if __name__ == "__main__":
    md_path = Path(__file__).parents[1] / "data" / "students" / "markdown"
    # 寻找 md_path 下的所有 .md 文件
    md_files = list(md_path.glob("*.md"))
    # 匹配“学生名_revid.md”，如“陆八魔亚瑠_123456.md”
    pattern = re.compile(r"^(?P<name>.+)_(?P<revid>\d+)\.md$")
    latest_files = {}
    for md_file in md_files:
        m = pattern.match(md_file.name)
        if not m:
            continue
        name = m.group("name")
        revid = int(m.group("revid"))
        # 只保留revid最大的文件
        if name not in latest_files or revid > latest_files[name][0]:
            latest_files[name] = (revid, md_file)

    # 只保留最大revid的md文件
    md_files = [item[1] for item in latest_files.values()]
    if not md_files:
        logger.error("没有找到任何 .md 文件，请检查路径。")
        exit(1)

    with Progress() as progress:
        task = progress.add_task("[cyan]处理学生Markdown文件...", total=len(md_files))
        # 处理所有 .md 文件
        for md_file in md_files:
            logger.info(f"正在处理文件: {md_file.name}")
            md_text = md_file.read_text(encoding="utf-8")

            markdown = mistune.create_markdown(
                renderer="ast", plugins=[table, strikethrough]
            )
            ast = markdown(md_text)

            section_names = ["简介", "人物设定", "人物经历", "角色相关"]
            sections = extract_sections(ast, section_names)

            # 展开内容
            structured = {}
            for sec, nodes in sections.items():
                structured[sec] = flatten_section_content(nodes)

            profile = extract_profile_table_from_ast(ast)
            structured["学生档案"] = profile

            # TODO: 解析游戏数据部分
            # game_data = parse_game_data_section(ast)
            # structured['游戏数据'] = game_data

            quotes = parse_quotes_section(ast)
            structured["角色台词"] = quotes

            m = pattern.match(md_file.name)
            if not m:
                logger.error(f"文件名格式不正确: {md_file.name}")
                continue
            student_name = m.group("name")
            if student_name == "初音未来":
                progress.update(task, advance=1)
                continue  # 跳过初音未来
            output_file = md_file.parents[1] / "json" / f"{student_name}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(structured, f, ensure_ascii=False, indent=4)
            progress.update(task, advance=1)
