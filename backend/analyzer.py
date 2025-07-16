import fitz  # PyMuPDF
import hashlib
from openai import OpenAI
from datetime import datetime
import os
from dotenv import load_dotenv
import re
import json
from tempfile import NamedTemporaryFile
import requests
from pathlib import Path
from pydantic import BaseModel
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
import tiktoken
load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

tokenizer = tiktoken.get_encoding("cl100k_base")

def trim_to_max_tokens(messages, max_tokens=65536):
    if not messages or len(messages) < 2:
        return messages

    system_msg = messages[0]
    user_msg = messages[1]

    # 分割 user 内容为若干段（按换行分隔的知识点）
    knowledge_list = user_msg["content"].split("\n")

    trimmed_knowledge = []
    total_tokens = len(tokenizer.encode(system_msg["content"]))
    
    for knowledge in knowledge_list:
        knowledge_tokens = len(tokenizer.encode(knowledge + "\n"))
        if total_tokens + knowledge_tokens > max_tokens:
            break
        trimmed_knowledge.append(knowledge)
        total_tokens += knowledge_tokens

    # 返回裁剪后的 messages
    return [
        system_msg,
        {"role": "user", "content": "\n".join(trimmed_knowledge)}
    ]

def append_and_trim_messages(messages, new_user_input, new_assistant_output=None, max_tokens=65536):
    """
    添加新一轮对话，并自动裁剪超出的历史内容
    """
    if new_user_input:
        messages.append({"role": "user", "content": new_user_input})
    if new_assistant_output:
        messages.append({"role": "assistant", "content": new_assistant_output})

    # 保留 system message
    system_msg = messages[0]
    history = messages[1:]

    # 从后往前保留消息
    trimmed = []
    total_tokens = len(tokenizer.encode(system_msg["content"]))

    for msg in reversed(history):
        token_count = len(tokenizer.encode(msg["content"]))
        if total_tokens + token_count > max_tokens:
            break
        trimmed.insert(0, msg)
        total_tokens += token_count

    return [system_msg] + trimmed

def safe_json_dump(data):
    return json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data

def extract_pdf_text(path, max_pages=30):
    doc = fitz.open(path)
    text = ""
    for page in doc[:min(max_pages, len(doc))]:
        text += page.get_text()
    return text
    
def extract_json_from_text(text):
    # 移除 Markdown 代码块包裹
    text = re.sub(r"```json|```", "", text).strip()
    json_start = text.find('[')
    json_end = text.rfind(']')
    if json_start != -1 and json_end != -1:
        return text[json_start:json_end + 1]
    return text
def extract_directory_text(pdf_path, directory_page):
    """
    提取指定目录页的文本内容。
    :param pdf_path: PDF 文件路径
    :param directory_page: 目录所在页数（1-based）
    :return: 目录页的文本内容
    """
    doc = fitz.open(pdf_path)
    # 转换为 0-based 页码
    page = doc.load_page(directory_page - 1)
    return page.get_text()

def extract_text_in_range(pdf_path, start_page, end_page):
    """
    从 PDF 中提取指定页码范围的文本。
    """
    doc = fitz.open(pdf_path)
    text = ""
    
    for page_num in range(start_page - 1, end_page):  # 页面是从 0 开始的
        page = doc.load_page(page_num)
        text += page.get_text("text")  # 提取页面文本
    return text

def analyze_pdf(filepath, mode="full", max_pages=1000, chapter_map=None):
    PDF_NAME = os.path.basename(filepath)
    BASE_DIR = Path("book_analysis")
    KNOWLEDGE_DIR = BASE_DIR / "knowledge_bases"
    SUMMARIES_DIR = BASE_DIR / "summaries"
    PDF_PATH = Path(filepath)
    OUTPUT_PATH = KNOWLEDGE_DIR / f"{PDF_NAME.replace('.pdf', '_knowledge.json')}"
    MODEL = "deepseek-chat"

    for directory in [KNOWLEDGE_DIR, SUMMARIES_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(PDF_PATH)

    knowledge_base = defaultdict(list) if mode == "fast" else []

    def analyze_chapter(title, start, end):
        combined_text = f"章节标题: {title}\n第一页内容:\n{doc[start].get_text()}\n最后一页内容:\n{doc[end].get_text()}"
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": """你是一个学习资料提取助手，请从以下页面中提取可学习的知识点（定义、公式、结论、原理等），跳过目录、致谢、版权页、索引等无实质内容页面。

                    请以 JSON 结构返回：
                    {
                    "has_content": true,
                    "knowledge": ["知识点一...", "知识点二..."]
                    }
                    如无内容请返回：
                    {
                    "has_content": false,
                    "knowledge": []
                    }"""}, 
                    {"role": "user", "content": combined_text}
                ],
                temperature=1.0
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"^```json|```$", "", raw)
            parsed = json.loads(raw)
            return title, parsed if parsed.get("has_content") else None
        except Exception as e:
            print(f"⚠️ 分析章节 {title} 失败：{e}")
            return title, None

    def analyze_page(page_num):
        page_text = doc[page_num].get_text()
        if not page_text.strip():
            return page_num, None
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": """你是一个学习资料提取助手，请从以下页面中提取可学习的知识点（定义、公式、结论、原理等），跳过目录、致谢、版权页、索引等无实质内容页面。

                    请以 JSON 结构返回：
                    {
                    "has_content": true,
                    "knowledge": ["知识点一...", "知识点二..."]
                    }
                    如无内容请返回：
                    {
                    "has_content": false,
                    "knowledge": []
                    }"""}, 
                    {"role": "user", "content": f"Page text: {page_text}"}
                ],
                temperature=1.0
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"^```json|```$", "", raw)
            parsed = json.loads(raw)
            return page_num, parsed if parsed.get("has_content") else None
        except Exception as e:
            print(f"⚠️ 分析第 {page_num+1} 页失败：{e}")
            return page_num, None

    if mode == "fast" and chapter_map:
        print("🚀 并发章节分析开始")
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            # 提交所有章节分析任务
            for chapter in chapter_map:
                start = chapter.get("start_page", 1) - 1
                end = chapter.get("end_page", 1) - 1
                if 0 <= start < doc.page_count and 0 <= end < doc.page_count:
                    title = chapter.get("title", f"章节 {start+1}-{end+1}")
                    print(f"📖 提交分析任务: {title}")
                    futures.append(executor.submit(analyze_chapter, title, start, end))

            # 保证按顺序处理返回的结果
            for future in futures:
                title, result = future.result()
                if result:
                    knowledge_base[title] = result["knowledge"]
                    print(f"✅ 提取 {title} 知识点 {len(result['knowledge'])} 条")
                else:
                    print(f"⏭️ {title} 无内容")

    elif mode == "full":
        print("🚀 并发逐页分析开始")
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            # 提交逐页分析任务
            for page_num in range(min(max_pages, doc.page_count)):
                futures.append(executor.submit(analyze_page, page_num))

            # 保证按顺序处理返回的结果
            for future in futures:
                page_num, result = future.result()
                if result:
                    knowledge_base.extend(result["knowledge"])
                    print(f"✅ 第 {page_num+1} 页提取知识点 {len(result['knowledge'])} 条")
                else:
                    print(f"⏭️ 第 {page_num+1} 页无内容")

    else:
        print("❌ 参数错误，未执行分析")
        return None

    # 保存知识库
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump({"knowledge": knowledge_base}, f, indent=2, ensure_ascii=False)

    # 统一整理
    if isinstance(knowledge_base, dict):
        all_knowledge = sum(knowledge_base.values(), [])
    else:
        all_knowledge = knowledge_base

    # 生成总结
    print("🤔 正在生成总结...")
    try:
        # 初始化 messages
        messages = [
            {"role": "system", "content": "请将以下知识点整理为结构化 Markdown 学习总结，使用合理的标题与项目符号列表"}
        ]

        # 将知识点按段分批，每批控制长度
        def chunks(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        for knowledge_chunk in chunks(all_knowledge, 1000):
            user_input = "\n".join(knowledge_chunk)
            print(user_input)
            # 发送当前轮的对话
            completion = client.chat.completions.create(
                model=MODEL,
                messages=messages + [{"role": "user", "content": user_input}],
                temperature=0.7
            )
            assistant_output = completion.choices[0].message.content.strip()

            # 更新对话历史（并自动裁剪）
            messages = append_and_trim_messages(messages, user_input, assistant_output)

        # 最后一轮总结生成
        final_completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=1.0
        )
        final_summary = final_completion.choices[0].message.content.strip()

        # 保存为 Markdown
        filename = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        outpath = SUMMARIES_DIR / filename
        with open(outpath, 'w', encoding='utf-8') as f:
            f.write(f"# 分析总结：{PDF_NAME}\n\n{final_summary}\n\n---\n*由 AI 分析生成*")
        print(f"✅ 分析完成，保存于 {outpath}")
        return str(outpath)

    except Exception as e:
        print(f"❌ 总结生成失败：{e}")
        return None


def analyze_chapters_by_ai_from_directory(pdf_path, start_page, end_page, project_id, db_save_fn,offset=0):
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    chapter_map = []

    fewshot_prompt = """
        请从以下文本中识别出书籍的章节结构，并以 JSON 数组格式返回，每个章节对象应包含：
        - "title": 章节名称（如："第一章 绪论"）
        - "start_page": 起始页码（整数）
        - "end_page": 结束页码（整数）

        输出格式如下：

        [
        { "title": "引言", "start_page": 1, "end_page": 2 },
        { "title": "第一章 人工智能概述", "start_page": 3, "end_page": 10 },
        { "title": "第二章 模型训练方法", "start_page": 11, "end_page": 20 }
        ]

        请不要添加任何额外文字、说明或换行后的注释，只返回 JSON 格式的数据。输出我给你的内容中可提取到的所有章节信息。
        """

    chunk_text = ""
    for i in range(start_page - 1, end_page):  # -1 because PyMuPDF uses 0-based indexing
        if i < total_pages:
            text = doc.load_page(i).get_text()
            # 清理文本：移除空格、换行符、制表符和标点符号
            text = re.sub(r'\s+', '', text)  # 移除空白字符
            text = re.sub(r'[.,，。、；：""''（）()\[\]【】．]', '', text)  # 移除标点符号
            chunk_text += text
    print(f"🤖 提取目录页内容（前600字）：{chunk_text[:600]}...")
    prompt = fewshot_prompt + "\n\n" + chunk_text[:10000]

    try:
        print(f"🤖 正在分析第 {start_page} 到第 {end_page} 页目录结构...")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个智能文档结构分析助手，请提取书籍章节结构。"},
                {"role": "user", "content": prompt}
            ],
            temperature=1,
        )
        ai_text = response.choices[0].message.content.strip()
        print(f"🤖 AI 返回：\n{ai_text[:500]}...\n")
    except Exception as e:
        print(f"⚠️ 分析失败：第 {start_page}-{end_page} 页，错误：{e}")
        return []

    try:
        cleaned_text = extract_json_from_text(ai_text)
        chapter_map = json.loads(cleaned_text)
    except Exception as parse_error:
        print(f"⚠️ JSON 解析失败：{parse_error}")
        return []
    # ✅ 对所有章节页码加上偏置
    for ch in chapter_map:
        ch["start_page"] += offset
        ch["end_page"] += offset
    # 去重 + 排序
    unique_map = {(c["title"], c["start_page"], c["end_page"]): c for c in chapter_map}
    final_map = sorted(unique_map.values(), key=lambda x: x["start_page"])

    for ch in final_map:
        section_text = ""
        for i in range(ch["start_page"] - 1, ch["end_page"]):
            if 0 <= i < total_pages:
                section_text += doc.load_page(i).get_text()

        section_summary = section_text[:500].replace("\n", " ")
        content_hash = hashlib.md5(section_text.encode("utf-8")).hexdigest()

        db_save_fn(
            project_id,
            ch["title"],
            ch["start_page"],
            ch["end_page"],
            section_summary,
            content_hash
        )

    print(f"✅ 共识别章节 {len(final_map)} 个。")
    return final_map

def extract_structured_summary(full_summary):
    structure_prompt = f"""
        你是一名教学助理，请根据以下学习资料总结，提取以下结构化内容，返回 JSON 格式：

        - classification：对材料所属学科/主题的分类
        - overview：对整个材料的简要介绍
        - outline：为材料构建一个条理清晰的大纲
        - questions：从材料中提出需要进一步理解或尚未解决的问题（不少于3条）
        - keywords：提取学习资料中的关键词
        - main_sentences：提取学习资料中的主旨句
        - argument_structure：提取学习资料中的论述结构
        - resolved_questions：列出已解决的问题
        - unresolved_questions：列出待解决的问题

        请用纯 JSON 格式返回，不要添加任何解释、markdown、注释或其他内容。

        以下是材料总结内容：
        {full_summary}
    """

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一名教学助理，擅长提取结构化总结信息"},
            {"role": "user", "content": structure_prompt}
        ],
        temperature=1.0,
    )

    raw_output = response.choices[0].message.content
    print("🧠 AI 原始返回内容：\n", raw_output)

    try:
        # 提取 markdown 块中的 JSON
        json_str = re.search(r"\{[\s\S]*\}", raw_output).group()
        struct_data = json.loads(json_str)
    except Exception as e:
        print("❌ 结构化字段提取失败，原因：", e)
        struct_data = {
            "classification": "",
            "overview": "",
            "outline": "",
            "questions": "",
            "keywords": "",
            "main_sentences": "",
            "argument_structure": "",
            "resolved_questions": "",
            "unresolved_questions": ""
        }

    return struct_data

def ask_question_in_section(pdf_path, start_page, end_page, question):
    """
    从指定页码范围提取文本并提交问题给 AI。
    """
    # 提取页码范围内的文本
    text = extract_text_in_range(pdf_path, start_page, end_page)
    
    # 将文本和问题一起提交给 AI 进行问答
    try:
        response = client.chat.completions.create(
            model="deepseek-reasoner",  # 使用 AI 模型
            messages=[
                {"role": "system", "content": "你是一个学习资料提取助手，帮助回答关于学习资料的问题。"},
                {"role": "user", "content": f"以下是相关内容：\n{text}\n\n问题：{question}\n请基于这些内容回答问题："}
            ],
            temperature=1.0
        )
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as e:
        print(f"❌ 提问失败：{e}")
        return "抱歉，发生了错误。请稍后再试。"
