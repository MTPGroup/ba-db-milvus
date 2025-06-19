import json
import re
from pathlib import Path

import mistune
from mistune.plugins.formatting import strikethrough
from mistune.plugins.table import table
from rich.progress import Progress

FIELD_MAP = {
    "简介": "简介",
    "校内设施": "校内设施",
    "学校设施": "校内设施",
    "学生": "学生与社团",
    "社团及学生": "学生与社团",
    "社团、学生与其他势力": "学生与社团",
    "历史": "历史",
    "概况": "概况",
    "基本资料": "基本资料",
}


def extract_text_from_node(node):
    if node.get("type") == "text":
        return node.get("raw", "")
    if node.get("type") in ("strong", "emphasis", "link", "paragraph"):
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


def extract_profile_table_from_ast(ast):
    profile = {}
    for node in ast:
        if node.get("type") == "table":
            for child in node.get("children", []):
                if child.get("type") == "table_body":
                    rows = child.get("children", [])
                    for row in rows:
                        if row.get("type") != "table_row":
                            continue
                        cells = row.get("children", [])
                        if len(cells) < 2:
                            continue
                        key = extract_text_from_node(cells[0]).strip()
                        value = extract_text_from_node(cells[1]).strip()
                        # 跳过空行和表头
                        if not key or key in ["基本资料"]:
                            continue
                        if key and value:
                            profile[key] = value
            break
    return profile


def extract_sections(ast, section_names):
    sections = {}
    current_section = None
    current_content = []
    for node in ast:
        if node.get("type") == "heading" and node.get("attrs", {}).get("level") == 2:
            if current_section and current_section in section_names:
                sections[current_section] = list(current_content)
            current_section = extract_text_from_node(node).strip()
            current_content = []
        else:
            if current_section and current_section in section_names:
                current_content.append(node)
    if current_section and current_section in section_names:
        sections[current_section] = list(current_content)
    return sections


def flatten_section_content(section_nodes):
    result = []
    for node in section_nodes:
        if node.get("type") == "heading" and node.get("attrs", {}).get("level") == 3:
            sub_title = extract_text_from_node(node).strip()
            result.append({"sub_title": sub_title, "content": []})
        elif node.get("type") == "paragraph":
            text = extract_text_from_node(node).strip()
            if text:
                if result and isinstance(result[-1], dict) and "content" in result[-1]:
                    result[-1]["content"].append(text)
                else:
                    result.append(text)
        elif node.get("type") == "list":
            items = []
            for item in node.get("children", []):
                if item.get("type") == "list_item":
                    items.append(extract_text_from_node(item).strip())
            if items:
                if result and isinstance(result[-1], dict) and "content" in result[-1]:
                    result[-1]["content"].extend(items)
                else:
                    result.extend(items)
        elif node.get("type") == "table":
            table_text = extract_text_from_table(node)
            if table_text:
                if result and isinstance(result[-1], dict) and "content" in result[-1]:
                    result[-1]["content"].append(table_text)
                else:
                    result.append(table_text)
    return result


if __name__ == "__main__":
    md_path = Path(__file__).parents[1] / "data" / "schools" / "markdown"
    md_files = list(md_path.glob("*.md"))
    pattern = re.compile(r"^(?P<name>.+)_(?P<revid>\d+)\.md$")
    latest_files = {}
    for md_file in md_files:
        m = pattern.match(md_file.name)
        if not m:
            continue
        name = m.group("name")
        revid = int(m.group("revid"))
        if name not in latest_files or revid > latest_files[name][0]:
            latest_files[name] = (revid, md_file)
    md_files = [item[1] for item in latest_files.values()]
    if not md_files:
        print("没有找到任何 .md 文件，请检查路径。")
        exit(1)

    with Progress() as progress:
        task = progress.add_task("[cyan]处理学校Markdown文件...", total=len(md_files))
        for md_file in md_files:
            print(f"正在处理文件: {md_file.name}")
            md_text = md_file.read_text(encoding="utf-8")
            markdown = mistune.create_markdown(
                renderer="ast", plugins=[table, strikethrough]
            )
            ast = markdown(md_text)
            section_names = [
                "简介",
                "校内设施",
                "社团及学生",
                "学生",
                "历史",
                "概况",
                "学校设施",
                "社团、学生与其他势力",
            ]
            sections = extract_sections(ast, section_names)
            structured = {}
            for sec, nodes in sections.items():
                structured[sec] = flatten_section_content(nodes)
            profile = extract_profile_table_from_ast(ast)
            structured["基本资料"] = profile
            m = pattern.match(md_file.name)
            if not m:
                print(f"文件名格式不正确: {md_file.name}")
                continue
            school_name = m.group("name")

            output_file = md_file.parents[1] / "json" / f"{school_name}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)

            unified = {}

            for k, v in structured.items():
                std_k = FIELD_MAP.get(k, k)
                # 合并同类项
                if (
                    std_k in unified
                    and isinstance(unified[std_k], list)
                    and isinstance(v, list)
                ):
                    unified[std_k].extend(v)
                else:
                    unified[std_k] = v
            # 保证所有标准字段都存在
            for std_k in FIELD_MAP.values():
                if std_k not in unified:
                    unified[std_k] = [] if std_k != "基本资料" else {}
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(unified, f, ensure_ascii=False, indent=4)
            progress.update(task, advance=1)
