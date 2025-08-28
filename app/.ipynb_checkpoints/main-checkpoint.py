import streamlit as st
import os
import sys
import re
from datetime import datetime
from typing import Tuple, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(PROJECT_ROOT)  # ✅ 强制将 cwd 设置为 feynmind 项目根目录
sys.path.append(PROJECT_ROOT)

from backend.upload import handle_upload
from backend.analyzer import analyze_pdf
from backend.analyzer import analyze_chapters_by_ai_from_directory
from backend.analyzer import extract_structured_summary
from backend.analyzer import safe_json_dump
from backend.analyzer import ask_question_in_section
from backend import db

db.init_db()

st.set_page_config(page_title="FeynMind AI 学习助手", layout="wide")

UPLOAD_DIR = "data"
SUMMARY_DIR = "summaries"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)

def render_project_selector(db) -> Optional[Tuple[int, str]]:
    """渲染项目选择器，并返回 (项目ID, 项目名)，如果无项目则返回 None"""
    projects = db.get_all_projects()
    if not projects:
        st.info("⚠️ 当前没有任何项目，请先上传资料。")
        return None

    # 构造项目选项（展示名: ID）
    project_options = {f"{name} ({file_path})": id for id, name, file_path, *_ in projects}
    project_names = list(project_options.keys())

    # 初始化 session_state
    if "selected_project_name" not in st.session_state or st.session_state.selected_project_name not in project_names:
        st.session_state.selected_project_name = project_names[0]

    # 渲染 selectbox，绑定 session_state
    st.selectbox(
        "📘 选择学习项目",
        project_names,
        index=project_names.index(st.session_state.selected_project_name),
        key="selected_project_name"
    )

    # 获取当前项目 ID 与名字
    selected_name = st.session_state.selected_project_name
    selected_id = project_options[selected_name]

    # 显示项目简要信息
    project_info = next((p for p in projects if p[0] == selected_id), None)
    if project_info:
        st.markdown(f"📁 路径：`{project_info[2]}`")

    return selected_id, selected_name

# 创建侧边栏
with st.sidebar:
    st.title("FeynMind 导航")
    page = st.radio("选择页面：", ["项目管理", "上传资料", "学习辅助", "学习归档"])

# 创建主内容容器
main_container = st.container()

# 根据选择的页面显示内容
with main_container:
    if page == "项目管理":
        st.title("📁 项目管理")
        result = render_project_selector(db)
        if result is None:
            st.stop()
        selected_project_id, selected_project_name = result

        st.warning("⚠️ 删除操作无法恢复，请谨慎操作！")
        confirm = st.checkbox("我确认要删除该项目及其所有关联数据")
        if st.button("🗑️ 删除该项目"):
            if confirm:
                db.delete_project(selected_project_id)
                st.success("✅ 项目已删除，请刷新页面")
                st.stop()
        # 学习计划展示与编辑
        st.subheader("📅 学习计划")
        plan = db.get_learning_plan_by_project_id(selected_project_id)
        col1, col2 = st.columns(2)
        with col1:
            daily_minutes = st.number_input("每天学习时间（分钟）", min_value=1, value=plan["daily_minutes"] if plan else 60)
        with col2:
            target_days = st.number_input("计划学习天数", min_value=1, value=plan["target_days"] if plan else 30)

        if st.button("保存学习计划"):
            db.save_learning_plan(selected_project_id, daily_minutes, target_days)
            st.success("✅ 学习计划已保存")

        st.markdown("---")

        # ⬇️ 章节目录结构
        with st.expander("📑 章节目录结构", expanded=False):
            chapter_list = db.get_chapter_map_by_project(selected_project_id)
            updated_chapters = []

            for i, (title, start, end, _) in enumerate(chapter_list):
                st.markdown(f"**章节 {i+1}**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_title = st.text_input("章节标题", value=title, key=f"title_{i}")
                with col2:
                    new_start = st.number_input("开始页", value=start, min_value=1, key=f"start_{i}")
                with col3:
                    new_end = st.number_input("结束页", value=end, min_value=new_start, key=f"end_{i}")
                updated_chapters.append((title, new_title, new_start, new_end))  # 加上原始标题

            if st.button("保存章节更新"):
                for old_title, new_title, start, end in updated_chapters:
                    db.update_chapter_map(selected_project_id, old_title, new_title, start, end)
                st.success("✅ 章节目录已更新")

        # ⬇️ AI 总结原文
        with st.expander("📜 AI 总结原文", expanded=False):
            full_summary = db.get_full_summary_by_project_id(selected_project_id, stage=0)
            if full_summary:
                content = st.text_area("总结全文", value=full_summary["content"] or "", height=200)
                if st.button("保存总结原文"):
                    db.update_summary(
                        selected_project_id, stage=0, content=content,
                        classification=full_summary["classification"] or "",
                        overview=full_summary["overview"] or "",
                        outline=full_summary["outline"] or "",
                        questions=full_summary["questions"] or "",
                        keywords=full_summary["keywords"] or "",
                        main_sentences=full_summary["main_sentences"] or "",
                        argument_structure=full_summary["argument_structure"] or "",
                        resolved_questions=full_summary["resolved_questions"] or "",
                        unresolved_questions=full_summary["unresolved_questions"] or "",
                        chapter_title=""
                    )
                    st.success("✅ 总结原文已保存")
            else:
                st.info("⚠️ 暂无该项目的 AI 总结内容。")

        # ⬇️ 结构化总结
        with st.expander("🧠 AI 结构化分析", expanded=False):
            if full_summary:
                classification = st.text_input("分类", value=full_summary["classification"] or "")
                overview = st.text_area("概要", value=full_summary["overview"] or "", height=100)
                outline = st.text_area("大纲", value=full_summary["outline"] or "", height=100)
                questions = st.text_area("提出的问题", value=full_summary["questions"] or "", height=100)
                keywords = st.text_area("关键词", value=full_summary["keywords"] or "", height=100)
                main_sentences = st.text_area("关键句", value=full_summary["main_sentences"] or "", height=100)
                argument_structure = st.text_area("论证结构", value=full_summary["argument_structure"] or "", height=100)
                resolved_questions = st.text_area("已解决问题", value=full_summary["resolved_questions"] or "", height=100)
                unresolved_questions = st.text_area("未解决问题", value=full_summary["unresolved_questions"] or "", height=100)

                if st.button("保存结构化总结"):
                    db.update_summary(
                        selected_project_id,
                        stage=0,
                        content=full_summary["content"] or "",
                        classification=classification,
                        overview=overview,
                        outline=outline,
                        questions=questions,
                        keywords=keywords,
                        main_sentences=main_sentences,
                        argument_structure=argument_structure,
                        resolved_questions=resolved_questions,
                        unresolved_questions=unresolved_questions,
                        chapter_title=""
                    )
                    st.success("✅ 结构化总结已保存")
            else:
                st.info("⚠️ 暂无结构化数据可编辑")

    elif page == "上传资料": 
        st.title("📄 上传资料")
        uploaded_file = st.file_uploader("选择 PDF 或 TXT 文件", type=["pdf", "txt"])

        if uploaded_file:
            filepath = handle_upload(uploaded_file, UPLOAD_DIR)
            project_name = os.path.splitext(uploaded_file.name)[0]
            project_id = db.get_project_id_by_name(project_name)

            db.add_project(project_name, filepath)
            project_id = db.get_project_id_by_name(project_name)
            st.markdown(f"**上传时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            if(project_id):
                st.success(f"✅ 新项目已创建：{project_name}")     
            
            #提取扫描版pdf中的文字，让他适应当前的分析函数
            #提取扫描版pdf中的文字，让他适应当前的分析函数
            if st.button("🔍 扫描PDF提取文字"):
                with st.spinner("正在提取PDF文字内容..."):
                    try:
                        # 使用OCRmyPDF处理PDF文件（原地处理）
                        ocrmypdf.ocr(
                            filepath, 
                            filepath,  # 输出到原文件
                            language='eng+chi_sim',  # 支持中英文
                            deskew=True,  # 自动校正倾斜
                            rotate_pages=True,  # 自动旋转页面
                            force_ocr=True,  # 强制OCR，即使已有文本层
                            jobs=4,  # 使用4个CPU核心
                            progress_bar=False  # 不显示进度条
                        )
                        st.success("✅ PDF文字提取完成！文件已原地更新。")
                        
                        # 验证OCR是否成功
                        st.info("📋 文字提取完成，现在可以进行目录分析和内容分析了。")
                        
                    except ocrmypdf.exceptions.PriorOcrFoundError:
                        st.warning("⚠️ 文件已经包含文本层，无需再次OCR")
                    except Exception as e:
                        st.error(f"❌ OCR处理失败：{str(e)}")
                        st.info("💡 请确保已安装OCRmyPDF及其依赖：`pip install ocrmypdf`")
            # 学习计划输入
            st.subheader("📅 学习计划")
            col1, col2 = st.columns(2)
            with col1:
                target_days = st.number_input("计划学习天数（天）", min_value=1, value=30, step=1)
            with col2:
                daily_minutes = st.number_input("每天学习时间（分钟）", min_value=1, value=60, step=1)

            if st.button("💾 保存学习计划"):
                db.save_learning_plan(project_id, daily_minutes, target_days)
                st.success("🎉 学习计划已保存！")

            summary_filename = project_name + "_summary.md"
            summary_path = os.path.join(SUMMARY_DIR, summary_filename)

            st.subheader("📑 目录提取")
            col1, col2,col3 = st.columns(3)
            with col1:
                start_page = st.number_input("请输入目录起始页数（从 1 开始）", min_value=1, step=1)
            with col2:
                end_page = st.number_input("请输入目录结束页数（从 1 开始）", min_value=start_page, step=1)
            with col3:
                offset = st.number_input(" 页面偏置📏（如目录写第3页，实际为17页，则偏置为14）", value=0, step=1)
            # 识别目录结构
            if st.button("🔍 AI 分析目录结构"):
                with st.spinner("🔍 正在分析目录结构..."):
                    try:
                        chapter_map = analyze_chapters_by_ai_from_directory(
                            filepath, start_page, end_page, project_id, db.save_chapter_map,offset
                        )
                        st.session_state.chapter_map = chapter_map  # 保存目录结构
                        if chapter_map:
                            st.success("📑 目录结构分析成功！")
                        else:
                            st.warning("⚠️ 无法识别章节结构。")
                    except Exception as e:
                        st.error(f"❌ 目录结构分析失败：{e}")

            # 保证目录结构始终显示
            if "chapter_map" in st.session_state:
                with st.expander("📑 识别的章节结构"):
                    for chapter in st.session_state.chapter_map:
                        st.markdown(f"**章节标题**: {chapter['title']}")
                        st.markdown(f"**页码范围**: {chapter['start_page']} - {chapter['end_page']}")

            # 选择分析模式
            if "chapter_map" in st.session_state:
                analysis_mode = st.radio("选择分析模式", ["逐页分析（详细）", "快速分析（目录页）"])
                mode_value = "full" if analysis_mode == "逐页分析（详细）" else "fast"

                if st.button("🤖 AI 分析内容"):
                    with st.spinner("AI 正在分析内容..."):
                        try:
                            summary_path = analyze_pdf(filepath, mode=mode_value, chapter_map=st.session_state.chapter_map)
                            with open(summary_path, "r", encoding="utf-8") as f:
                                summary_content = f.read()
                            st.markdown("✅ 分析完成！")
                            with st.expander("📝 原始总结内容"):
                                st.markdown(summary_content)

                            # 提取结构化
                            structured = extract_structured_summary(summary_content)
                            with st.expander("🧩 结构化字段"):
                                st.json(structured)

                            db.save_summary(
                                project_id,
                                stage=0,
                                content=summary_content,
                                classification=structured.get("classification"),
                                overview=structured.get("overview"),
                                outline=safe_json_dump(structured.get("outline")),
                                questions=safe_json_dump(structured.get("questions")),
                                keywords=safe_json_dump(structured.get("keywords")),
                                main_sentences=safe_json_dump(structured.get("main_sentences")),
                                argument_structure=safe_json_dump(structured.get("argument_structure")),
                                resolved_questions=safe_json_dump(structured.get("resolved_questions")),
                                unresolved_questions=safe_json_dump(structured.get("unresolved_questions")),
                                chapter_title=""
                            )
                            st.success("✅ 总结与保存成功！")
                        except Exception as e:
                            st.error(f"❌ 分析失败：{e}")

    elif page == "学习辅助":
        st.title("🧠 学习辅助")

        result = render_project_selector(db)
        if result is None:
            st.stop()
        selected_project_id, selected_project_name = result

        # 项目详情
        projects = db.get_all_projects()
        project_info = next(p for p in projects if p[0] == selected_project_id)
        project_path = project_info[2]
        current_stage, completed_pages, current_chapter = project_info[3], project_info[4], project_info[5]
        chapter_records = db.get_chapter_map_by_project(selected_project_id)
        chapter_list = [c[0] for c in chapter_records]

        def format_stage_description(stage, chapter):
            return {
                1: "全书 - 阶段一（略读 / 速读）",
                2: f"全书 - 阶段二：{chapter or '（未指定章节）'} - 阶段一",
                3: f"全书 - 阶段二：{chapter or '（未指定章节）'} - 阶段二"
            }.get(stage, "未知阶段")

        st.markdown(f"当前阶段：`{format_stage_description(current_stage, current_chapter)}`")
        st.markdown(f"已完成页数：`{completed_pages}`")
        st.markdown("---")
        
        # --- 1. 章节问答 ---
        st.subheader("💬 章节问答")

        # 假设 chapter_records 是从数据库中读取的章节信息
        chapter_map = {f"{c[0]}（{c[1]}-{c[2]}页）": (c[1], c[2]) for c in chapter_records}
        selected_chapter = st.selectbox("选择章节", list(chapter_map.keys()), key="qa_chapter")
        user_question = st.text_area("请输入你的问题")

        if st.button("提交问题"):
            start, end = chapter_map[selected_chapter]
            with st.spinner("🤖 思考中，请稍候..."):
                    result = ask_question_in_section(project_path, start, end, user_question)

            st.markdown("#### 🤖 回答结果：")
            st.markdown(result)

        st.markdown("---")

        # --- 2. 学习记录提交 ---
        st.subheader("📝 今日学习记录")
        studied_minutes = st.number_input("今日学习时间（分钟）", min_value=0, step=5)
        studied_pages = st.number_input("今日学习页数（或章节范围）", min_value=0, step=1)
        if st.button("提交学习记录"):
            db.log_progress(selected_project_id, studied_minutes, studied_pages)
            st.success("✅ 学习记录已提交")
        
        # --- 3. 学习进度图表 ---
        logs = db.get_progress_logs_by_project_id(selected_project_id)

        st.subheader("📊 每日学习时间与页数")

        if logs:
            import pandas as pd
            df_logs = pd.DataFrame(logs, columns=["date", "minutes", "pages"])
            df_logs["date"] = pd.to_datetime(df_logs["date"])

            # 绘制每日学习时间柱状图
            st.subheader("每日学习时间（分钟）")
            st.bar_chart(df_logs.sort_values("date").set_index("date")["minutes"])

            # 绘制每日学习页数柱状图
            st.subheader("每日学习页数")
            st.bar_chart(df_logs.sort_values("date").set_index("date")["pages"])

        else:
            st.info("暂无学习记录")



        st.markdown("---")

        # --- 4. 提交总结 ---
        st.subheader("📘 提交总结")
        summary_content = st.text_area("总结内容", height=150)
        summary_mode = st.selectbox("总结范围", ["整本书", "页码范围", "章节"], key="summary_mode")

        # 动态输入：根据模式展示不同输入
        page_range = st.text_input("输入页码范围（如 12-20）") if summary_mode == "页码范围" else None
        chapter_select = st.selectbox("选择章节", chapter_list, key="summary_chapter") if summary_mode == "章节" else None

        # 处理 chapter_title 的值（页码范围会作为伪章节保存）
        chapter_title = None
        if summary_mode == "章节":
            chapter_title = chapter_select
        elif summary_mode == "页码范围":
            try:
                start_page, end_page = map(int, page_range.split("-"))
                chapter_title = page_range.strip()  # 直接存为类似 "12-20"
            except:
                st.error("❌ 页码范围格式错误，请输入如 12-20 的格式")
                st.stop()

        if st.button("保存总结"):
            db.save_summary(selected_project_id, stage=current_stage, content=summary_content, chapter_title=chapter_title)
            stage_updated = False

            # === 阶段推进逻辑 ===
            if current_stage == 1 and summary_mode == "整本书":
                db.update_project_stage(selected_project_id, 2)
                first_chapter = chapter_list[0] if chapter_list else None
                db.update_current_chapter(selected_project_id, first_chapter)
                st.success("✅ 总结已保存，进入阶段二 - 第一个章节")
                stage_updated = True

            elif current_stage in [2, 3] and summary_mode == "章节":
                db.update_current_chapter(selected_project_id, chapter_title)
                if current_stage == 2:
                    db.update_project_stage(selected_project_id, 3)
                    st.success(f"✅ 总结已保存，进入 {chapter_title} - 阶段二")
                    stage_updated = True
                elif current_stage == 3:
                    idx = chapter_list.index(chapter_title) if chapter_title in chapter_list else -1
                    if idx + 1 < len(chapter_list):
                        next_chap = chapter_list[idx + 1]
                        db.update_current_chapter(selected_project_id, next_chap)
                        db.update_project_stage(selected_project_id, 2)
                        st.success(f"✅ 总结已保存，进入 {next_chap} - 阶段一")
                        stage_updated = True
                    else:
                        st.success("✅ 总结已保存，已完成所有章节！")

            if not stage_updated:
                st.success("✅ 总结已保存（未推进阶段）")

            # 更新展示的阶段信息
            if stage_updated:
                new_info = next(p for p in db.get_all_projects() if p[0] == selected_project_id)
                new_stage = new_info[3]
                new_chapter = new_info[5]
                st.markdown(f"📌 当前阶段已更新为：`{format_stage_description(new_stage, new_chapter)}`")

        st.markdown("---")

        # --- 5. 标记难点 ---
        st.subheader("❗ 标记难点")
        dp_mode = st.radio("标记方式", ["按章节", "按页码范围"], key="difficulty_mode")

        # 根据标记方式来获取位置
        if dp_mode == "按章节":
            dp_location = st.selectbox("选择章节", chapter_list, key="difficulty_chapter")
        else:
            dp_location = st.text_input("输入页码范围（如 5-10）", key="difficulty_range")

        dp_title = st.text_input("难点名称")


        if st.button("添加难点"):
            # 将 dp_location 传递给 save_difficult_point 函数
            db.save_difficult_point(selected_project_id, dp_title, dp_location)
            st.success("✅ 已添加难点")


    elif page == "学习归档":
        st.title("📚 学习归档")

        # --- 1. 选择项目 ---
        result = render_project_selector(db)
        if result is None:
            st.stop()
        selected_project_id, selected_project_name = result

        # 获取项目详情
        projects = db.get_all_projects()
        project_info = next(p for p in projects if p[0] == selected_project_id)
        project_path = project_info[2]

        # --- 2. 展示提交的总结 ---
        st.subheader("📘 所有总结")
        summaries = db.get_summaries_by_project(selected_project_id)

        # 阶段名称映射
        stage_map = {
            1: "阶段一：全书总结",
            2: "阶段二：章节总结",
            3: "阶段三：局部总结"
        }

        if summaries:
            for i, (stage, content, chapter_title, created_at) in enumerate(summaries):
                # 判断是否为页码范围（格式为如 "12-20"）
                if chapter_title and re.fullmatch(r"\d{1,4}-\d{1,4}", chapter_title.strip()):
                    scope_label = f"页码: {chapter_title}"
                elif chapter_title:
                    scope_label = f"章节: {chapter_title}"
                else:
                    scope_label = "整本书"

                # 展示展开卡片
                with st.expander(f"{stage_map.get(stage, f'未知阶段 {stage}')} - {scope_label} - {created_at}", expanded=False):
                    st.markdown(content)
        else:
            st.info("暂无总结记录")

        st.markdown("---")

        # --- 3. 展示难点标记 ---
        difficulty_points = db.get_difficulty_points_by_project(selected_project_id)

        st.subheader("📌 标记的难点")
        if difficulty_points:
            for point_id, title, page_or_chapter, created_at in difficulty_points:
                with st.expander(f"{title} ({page_or_chapter}) - {created_at}"):
                    # 用于编辑
                    new_title = st.text_input(f"难点名称（ID: {point_id}）", title, key=f"title_{point_id}")
                    new_page_or_chapter = st.text_input("页码/章节", page_or_chapter, key=f"page_{point_id}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 保存修改", key=f"save_{point_id}"):
                            db.update_difficulty_point(point_id, new_title, new_page_or_chapter)
                            st.success("已更新！请刷新页面查看效果")
                    with col2:
                        if st.button("🗑️ 删除", key=f"delete_{point_id}"):
                            db.delete_difficulty_point(point_id)
                            st.warning("已删除！请刷新页面")
        else:
            st.info("暂无难点记录")

        st.markdown("---")

        # --- 4. 章节/页码范围问答 ---
        st.subheader("🤖 针对难点提问")

        if len(difficulty_points) > 0:
            selected_dp = st.selectbox("选择一个难点", [f"{dp[1]} ({dp[2]})" for dp in difficulty_points])
            
            # 提取选中的难点的页面或章节信息
            point_id, title, page_or_chapter, created_at = next(dp for dp in difficulty_points if f"{dp[1]} ({dp[2]})" == selected_dp)

            # 获取章节或页码范围
            start_page, end_page = None, None
            if "-" in page_or_chapter:  # 如果是页码范围
                try:
                    start_page, end_page = map(int, page_or_chapter.split("-"))
                except ValueError:
                    st.error("页码范围格式错误，应为 '起始页-结束页'")
                    st.stop()
            else:  # 如果是章节
                # 查询章节信息
                matched = [c for c in db.get_chapter_map_by_project(selected_project_id) if c[0] == page_or_chapter]
                if matched:
                    start_page, end_page = matched[0][1], matched[0][2]  # 使用索引获取 start_page 和 end_page
                else:
                    st.error("未找到对应章节，检查章节名称是否正确")
                    st.stop()
            # 调用 AI 问答
            question = st.text_area("输入你的问题")
            if st.button("提交问题") and question:
                with st.spinner("AI 正在思考..."):
                    answer = ask_question_in_section(project_path, start_page, end_page, question)

                st.markdown("#### 🤖 AI 回答：")
                st.markdown(answer)

        else:
            st.info("请先添加一个难点以进行提问。")
