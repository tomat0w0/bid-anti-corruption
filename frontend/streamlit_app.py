import streamlit as st
import requests
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# 页面配置
st.set_page_config(
    page_title="招标廉政体检系统",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
.metric-card {
    background-color: #f0f2f6;
    padding: 1rem;
    border-radius: 0.5rem;
    border-left: 4px solid #1f77b4;
}
.risk-high {
    border-left-color: #ff4b4b;
}
.risk-medium {
    border-left-color: #ffa500;
}
.risk-low {
    border-left-color: #00cc00;
}
.stAlert > div {
    padding: 0.5rem 1rem;
}
</style>
""", unsafe_allow_html=True)

# 应用状态管理
if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []
if 'api_url' not in st.session_state:
    st.session_state.api_url = "http://localhost:8000"
if 'projects' not in st.session_state:
    st.session_state.projects = []
if 'file_project_mapping' not in st.session_state:
    st.session_state.file_project_mapping = {}
if 'analyze_button' not in st.session_state:
    st.session_state.analyze_button = False

def get_system_status(api_url: str) -> Optional[Dict[str, Any]]:
    """获取系统状态"""
    try:
        response = requests.get(f"{api_url}/stats", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

def format_risk_level(level: str) -> str:
    """格式化风险等级显示"""
    level_map = {
        'high': '🔴 高风险',
        'medium': '🟡 中风险', 
        'low': '🟢 低风险'
    }
    return level_map.get(level.lower(), f'❓ {level}')

def create_risk_chart(rule_hits: list) -> go.Figure:
    """创建风险分布图表"""
    if not rule_hits:
        return None
    
    # 统计风险等级分布
    risk_counts = {'high': 0, 'medium': 0, 'low': 0}
    for hit in rule_hits:
        level = hit.get('level', 'medium').lower()
        if level in risk_counts:
            risk_counts[level] += 1
    
    # 创建饼图
    fig = go.Figure(data=[go.Pie(
        labels=['高风险', '中风险', '低风险'],
        values=[risk_counts['high'], risk_counts['medium'], risk_counts['low']],
        hole=0.3,
        marker_colors=['#ff4b4b', '#ffa500', '#00cc00']
    )])
    
    fig.update_layout(
        title="风险等级分布",
        showlegend=True,
        height=300
    )
    
    return fig

# 标题和描述
st.title("🔍 招标廉政体检系统")
st.markdown("### 基于AI的招标文件风险分析平台")
st.markdown("---")

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 系统配置")
    
    # API配置
    api_url = st.text_input(
        "后端API地址", 
        value=st.session_state.api_url,
        help="输入后端服务的完整URL地址"
    )
    st.session_state.api_url = api_url
    
    # 系统状态检查
    if st.button("🔄 检查系统状态"):
        with st.spinner("检查中..."):
            status = get_system_status(api_url)
            if status:
                st.success("✅ 系统连接正常")
                with st.expander("系统详情"):
                    st.json(status)
            else:
                st.error("❌ 无法连接到后端服务")
    
    st.markdown("---")
    
    # 使用说明
    st.header("📖 使用说明")
    st.markdown("""
    1. **上传文件**: 选择.docx或.pdf格式的招标文件
    2. **设置项目**: 为每个文件选择或创建项目
    3. **开始分析**: 点击分析按钮等待结果
    4. **查看结果**: 浏览风险分析报告
    5. **导出报告**: 下载分析结果
    """)
    
    st.markdown("---")
    
    # 分析历史
    if st.session_state.analysis_history:
        st.header("📚 分析历史")
        for i, record in enumerate(reversed(st.session_state.analysis_history[-5:])):
            with st.expander(f"{record.get('project_name', '未命名项目')} - {record['timestamp']}"):
                st.write(f"文件: {record['filename']}")
                st.write(f"风险评分: {record['risk_score']:.2f}")
                st.write(f"风险等级: {format_risk_level(record['risk_level'])}")
                st.write(f"发现问题: {record['total_hits']} 个")

# 主界面布局
tab1, tab2, tab3 = st.tabs(["📄 文件分析", "📊 分析结果", "🔧 系统管理"])

with tab1:
    st.header("📁 文件上传与项目绑定")
    
    # 文件上传
    uploaded_files = st.file_uploader(
        "选择招标文件",
        type=["docx", "pdf"],
        accept_multiple_files=True,
        help="请上传.docx或.pdf格式的招标文件，可以选择多个文件，每个文件大小不超过10MB"
    )
    
    if uploaded_files:
        st.success(f"✅ 已选择 {len(uploaded_files)} 个文件")
        
        # 显示文件列表和项目选择
        st.subheader("📋 文件与项目绑定")
        st.info("请为每个文件选择或创建对应的项目")
        
        # 如果没有项目，添加一个示例项目
        if not st.session_state.projects:
            st.session_state.projects = [
                {"name": "示例项目1", "budget": 100.0, "project_location": "北京市", "company_location": "上海市", "registered_capital": 0.0},
                {"name": "示例项目2", "budget": 200.0, "project_location": "广州市", "company_location": "深圳市", "registered_capital": 0.0}
            ]
        
        # 创建新项目的表单
        with st.expander("➕ 创建新项目"):
            new_project_name = st.text_input("项目名称", key="new_project_name", placeholder="请输入项目名称")
            new_project_budget = st.number_input(
                "项目预算（万元）",
                key="new_project_budget",
                min_value=0.0,
                value=100.0,
                step=10.0,
                format="%.1f"
            )
            new_project_location = st.text_input("项目地点", key="new_project_location", placeholder="如：北京市")
            new_company_location = st.text_input("公司地点", key="new_company_location", placeholder="如：上海市")
            new_registered_capital = st.number_input("注册资本（万元）", key="new_registered_capital", min_value=0.0, value=0.0)
            
            if st.button("添加项目"):
                if new_project_name:
                    # 检查项目是否已存在
                    if not any(p["name"] == new_project_name for p in st.session_state.projects):
                        new_project = {
                            "name": new_project_name,
                            "budget": new_project_budget,
                            "project_location": new_project_location,
                            "company_location": new_company_location,
                            "registered_capital": new_registered_capital
                        }
                        st.session_state.projects.append(new_project)
                        st.success(f"✅ 项目 '{new_project_name}' 已添加")
                        st.rerun()
                    else:
                        st.error(f"❌ 项目 '{new_project_name}' 已存在")
                else:
                    st.error("❌ 请输入项目名称")
        
        # 为每个文件选择项目
        for i, file in enumerate(uploaded_files):
            st.markdown(f"**📄 文件 {i+1}: {file.name}** ({file.size / 1024:.1f} KB)")
            
            # 获取项目列表
            project_names = ["未选择"] + [project["name"] for project in st.session_state.projects]
            
            # 获取当前文件的项目映射
            current_project = st.session_state.file_project_mapping.get(file.name, "未选择")
            
            # 项目选择
            selected_project_name = st.selectbox(
                "选择项目",
                options=project_names,
                index=project_names.index(current_project) if current_project in project_names else 0,
                key=f"project_select_{i}"
            )
            
            # 更新文件-项目映射
            if selected_project_name != "未选择":
                st.session_state.file_project_mapping[file.name] = selected_project_name
                
                # 显示选中的项目信息
                selected_project = next((project for project in st.session_state.projects if project["name"] == selected_project_name), None)
                if selected_project:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.info(f"预算: {selected_project['budget']} 万元")
                    with col2:
                        if selected_project.get("project_location"):
                            st.info(f"项目地点: {selected_project['project_location']}")
                    with col3:
                        if selected_project.get("company_location"):
                            st.info(f"公司地点: {selected_project['company_location']}")
            else:
                # 如果选择了"未选择"，则从映射中移除
                if file.name in st.session_state.file_project_mapping:
                    del st.session_state.file_project_mapping[file.name]
            
            st.markdown("---")
        
        # 显示总大小
        total_size = sum(file.size for file in uploaded_files)
        st.info(f"📏 总大小: {total_size / 1024 / 1024:.2f} MB")
        
        # 检查是否所有文件都已绑定项目
        unbinded_files = [file.name for file in uploaded_files if file.name not in st.session_state.file_project_mapping]
        if unbinded_files:
            st.warning(f"⚠️ 有 {len(unbinded_files)} 个文件未绑定项目，请为所有文件选择项目后再分析")
        
        # 分析按钮
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.session_state.analyze_button = st.button(
                "🔍 开始分析",
                type="primary",
                disabled=not uploaded_files or len(unbinded_files) > 0,
                use_container_width=True
            )
    else:
        st.info("请上传招标文件进行分析")

with tab2:
    st.header("📊 分析结果")
    
    if 'current_result' in st.session_state:
        result = st.session_state.current_result
        
        # 风险概览卡片
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "总体风险评分", 
                f"{result['overall_risk_score']:.2f}",
                delta=None
            )
        
        with col2:
            st.metric(
                "总体风险等级", 
                format_risk_level(result['overall_risk_level'])
            )
        
        with col3:
            total_hits = sum(len(file_result.get('rule_hits', [])) for file_result in result['file_results'])
            st.metric(
                "发现问题", 
                f"{total_hits} 个"
            )
        
        with col4:
            st.metric(
                "处理时间", 
                f"{result['total_processing_time']:.2f}s"
            )
        
        # 风险分布图表
        all_rule_hits = []
        for file_result in result['file_results']:
            all_rule_hits.extend(file_result.get('rule_hits', []))
            
        if all_rule_hits:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                chart = create_risk_chart(all_rule_hits)
                if chart:
                    st.plotly_chart(chart, use_container_width=True)
            
            with col2:
                # 风险标签统计
                tags = []
                for hit in all_rule_hits:
                    tags.extend(hit.get('tags', []))
                
                if tags:
                    tag_counts = pd.Series(tags).value_counts()
                    fig = px.bar(
                        x=tag_counts.values,
                        y=tag_counts.index,
                        orientation='h',
                        title="风险类型分布"
                    )
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
        
        # 详细风险项
        st.markdown("---")
        st.header("🚨 详细风险分析")
        
        # 按文件分组显示风险项
        for file_index, file_result in enumerate(result['file_results']):
            file_info = file_result.get('file_info', {})
            file_name = file_info.get('filename', f"文件 {file_index+1}")
            project_name = file_info.get('project_name', "未命名项目")
            risk_level = file_result.get('risk_level', 'medium').lower()
            risk_score = file_result.get('risk_score', 0.0)
            rule_hits = file_result.get('rule_hits', [])
            
            # 文件风险概览
            with st.expander(f"📄 {file_name} - 项目: {project_name} - 风险评分: {risk_score:.2f} ({format_risk_level(risk_level)})", expanded=True):
                if not rule_hits:
                    st.success("✅ 未发现风险项")
                    continue
                    
                st.info(f"发现 {len(rule_hits)} 个风险项")
                
                # 显示该文件的所有风险项
                for i, hit in enumerate(rule_hits, 1):
                    hit_risk_level = hit.get('level', 'medium').lower()
                    
                    with st.expander(
                        f"风险项 {i}: {hit.get('rule_id', 'Unknown')} - {format_risk_level(hit_risk_level)}",
                        expanded=(hit_risk_level == 'high')
                    ):
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**📝 风险内容:**")
                            st.code(hit.get('snippet', 'N/A'), language=None)
                            
                            if hit.get('tags'):
                                st.markdown(f"**🏷️ 风险标签:** {', '.join(hit['tags'])}")
                            
                            if hit.get('context'):
                                with st.expander("查看上下文"):
                                    st.text(hit['context'])
                            
                            # 显示置信度和原因
                            if isinstance(hit.get('level'), dict):
                                level_info = hit['level']
                                if 'confidence' in level_info:
                                    st.progress(level_info['confidence'])
                                    st.caption(f"置信度: {level_info['confidence']:.1%}")
                                if 'reason' in level_info:
                                    st.info(f"💡 {level_info['reason']}")
                        
                        with col2:
                            # 风险等级指示器
                            if hit_risk_level == 'high':
                                st.error("🔴 高风险")
                            elif hit_risk_level == 'medium':
                                st.warning("🟡 中风险")
                            else:
                                st.success("🟢 低风险")
                            
                            # 匹配位置
                            if 'match_start' in hit:
                                st.caption(f"位置: {hit['match_start']}-{hit.get('match_end', 'N/A')}")
        
        # LLM分析结果
        st.markdown("---")
        st.header("🤖 AI深度分析")
        
        # 按文件分组显示LLM分析结果
        for file_index, file_result in enumerate(result['file_results']):
            file_info = file_result.get('file_info', {})
            file_name = file_info.get('filename', f"文件 {file_index+1}")
            project_name = file_info.get('project_name', "未命名项目")
            llm_results = file_result.get('llm_results', [])
            
            if not llm_results:
                continue
                
            with st.expander(f"📄 {file_name} - 项目: {project_name} - AI分析结果", expanded=True):
                for i, llm_result in enumerate(llm_results, 1):
                    with st.expander(f"AI分析 {i}"):
                        if 'error' in llm_result:
                            st.error(f"❌ {llm_result['error']}")
                        else:
                            st.markdown(f"**分析内容:** {llm_result.get('snippet', 'N/A')}")
                            if 'analysis' in llm_result:
                                st.markdown(f"**AI评估:** {llm_result['analysis']}")
                            if 'confidence' in llm_result:
                                st.progress(llm_result['confidence'])
                                st.caption(f"AI置信度: {llm_result['confidence']:.1%}")
        
        # 导出功能
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("📥 导出分析报告", use_container_width=True):
                # 生成报告
                file_names = [file_result.get('file_info', {}).get('filename', f"文件 {i+1}") 
                             for i, file_result in enumerate(result['file_results'])]
                
                report = {
                    "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "文件数量": len(result['file_results']),
                    "文件列表": file_names,
                    "总体风险评分": result['overall_risk_score'],
                    "总体风险等级": result['overall_risk_level'],
                    "发现问题总数": sum(len(file_result.get('rule_hits', [])) for file_result in result['file_results']),
                    "详细结果": result
                }
                
                st.download_button(
                    label="下载JSON报告",
                    data=json.dumps(report, ensure_ascii=False, indent=2),
                    file_name=f"batch_risk_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
    else:
        st.info("📋 暂无分析结果，请先上传文件进行分析")

with tab3:
    st.header("🔧 系统管理")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 系统状态")
        if st.button("刷新系统状态"):
            status = get_system_status(api_url)
            if status:
                st.json(status)
            else:
                st.error("无法获取系统状态")
    
    with col2:
        st.subheader("🔄 规则管理")
        if st.button("重新加载规则"):
            try:
                response = requests.post(f"{api_url}/reload-rules", timeout=10)
                if response.status_code == 200:
                    st.success("✅ 规则重新加载成功")
                    st.json(response.json())
                else:
                    st.error(f"❌ 重新加载失败: {response.status_code}")
            except Exception as e:
                st.error(f"❌ 操作失败: {str(e)}")
    
    # 清理功能
    st.markdown("---")
    st.subheader("🧹 数据清理")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("清空分析历史", type="secondary"):
            st.session_state.analysis_history = []
            st.success("✅ 分析历史已清空")
    
    with col2:
        if st.button("清空当前结果", type="secondary"):
            if 'current_result' in st.session_state:
                del st.session_state.current_result
                st.success("✅ 当前结果已清空")
    
    with col3:
        if st.button("清空项目映射", type="secondary"):
            st.session_state.file_project_mapping = {}
            st.success("✅ 文件-项目映射已清空")

# 分析处理逻辑
if 'analyze_button' in st.session_state and st.session_state.analyze_button and uploaded_files:
    with st.spinner("🔄 正在分析文件，请稍候..."):
        try:
            # 准备请求数据
            files = {}
            file_project_info = {}
            
            # 收集每个文件的项目信息
            for i, uploaded_file in enumerate(uploaded_files):
                # 根据文件扩展名确定MIME类型
                mime_type = "application/pdf" if uploaded_file.name.lower().endswith(".pdf") else \
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                files[f"files"] = (uploaded_file.name, uploaded_file.getvalue(), mime_type)
                
                # 获取该文件对应的项目
                project_name = st.session_state.file_project_mapping.get(uploaded_file.name)
                if project_name:
                    project = next((p for p in st.session_state.projects if p["name"] == project_name), None)
                    if project:
                        # 准备该文件的项目信息
                        file_project_info[uploaded_file.name] = {
                            "project_name": project["name"],
                            "budget": int(project["budget"] * 10000)  # 转换为元
                        }
                        
                        # 添加可选元数据
                        if project.get("project_location"):
                            file_project_info[uploaded_file.name]["project_location"] = project["project_location"]
                        if project.get("company_location"):
                            file_project_info[uploaded_file.name]["company_location"] = project["company_location"]
                        if project.get("registered_capital", 0) > 0:
                            file_project_info[uploaded_file.name]["registered_capital"] = int(project["registered_capital"] * 10000)
            
            # 发送请求
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 处理每个文件
            all_results = []
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"📤 处理文件 {i+1}/{len(uploaded_files)}: {uploaded_file.name}...")
                progress_bar.progress((i / len(uploaded_files)) * 0.5)
                
                # 准备单个文件的请求
                file_data = {"file": (uploaded_file.name, uploaded_file.getvalue(), 
                                    "application/pdf" if uploaded_file.name.lower().endswith(".pdf") else \
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                
                # 准备表单数据
                form_data = {}
                if uploaded_file.name in file_project_info:
                    project_info = file_project_info[uploaded_file.name]
                    form_data.update(project_info)
                else:
                    # 使用默认值
                    form_data["project_name"] = "未命名项目"
                    form_data["budget"] = 0
                
                # 发送单文件分析请求
                response = requests.post(
                    f"{api_url}/analyze",
                    files=file_data,
                    data=form_data,
                    timeout=300
                )
                
                if response.status_code == 200:
                    file_result = response.json()
                    all_results.append(file_result)
                else:
                    error_detail = "未知错误"
                    try:
                        error_info = response.json()
                        error_detail = error_info.get('detail', response.text)
                    except:
                        error_detail = response.text
                    
                    st.error(f"❌ 文件 {uploaded_file.name} 分析失败 ({response.status_code}): {error_detail}")
            
            # 合并所有结果
            if all_results:
                progress_bar.progress(0.9)
                status_text.text("🔍 整合分析结果...")
                
                # 计算总体风险评分（取最高分）
                overall_risk_score = max([result.get('risk_score', 0) for result in all_results]) if all_results else 0.0
                
                # 确定总体风险等级
                if overall_risk_score >= 4.0:
                    overall_risk_level = "high"
                elif overall_risk_score >= 2.0:
                    overall_risk_level = "medium"
                else:
                    overall_risk_level = "low"
                
                # 构建批量分析结果
                batch_result = {
                    "file_results": all_results,
                    "overall_risk_score": overall_risk_score,
                    "overall_risk_level": overall_risk_level,
                    "total_processing_time": sum([result.get('processing_time', 0) for result in all_results]),
                    "system_info": {
                        "total_files": len(all_results),
                        "total_hits": sum([len(result.get('rule_hits', [])) for result in all_results]),
                        "total_llm_processed": sum([len(result.get('llm_results', [])) for result in all_results]),
                        "successful_files": len(all_results)
                    }
                }
                
                # 保存结果
                st.session_state.current_result = batch_result
                
                # 添加到历史记录
                for i, uploaded_file in enumerate(uploaded_files):
                    project_name = st.session_state.file_project_mapping.get(uploaded_file.name, "未命名项目")
                    file_result = all_results[i] if i < len(all_results) else {"risk_score": 0, "risk_level": "unknown", "rule_hits": []}
                    
                    history_record = {
                        "filename": uploaded_file.name,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "risk_score": file_result.get('risk_score', 0),
                        "risk_level": file_result.get('risk_level', 'unknown'),
                        "total_hits": len(file_result.get('rule_hits', [])),
                        "project_name": project_name
                    }
                    st.session_state.analysis_history.append(history_record)
                
                progress_bar.progress(1.0)
                status_text.text("✅ 分析完成！")
                
                # 显示成功消息
                st.success("🎉 分析完成！请查看'分析结果'标签页")
                
                # 自动切换到结果标签页
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ 所有文件分析失败")
                
        except requests.exceptions.Timeout:
            st.error("⏰ 请求超时，请稍后重试或检查文件大小")
        except requests.exceptions.ConnectionError:
            st.error(f"🔌 无法连接到后端服务，请检查API地址: {api_url}")
        except Exception as e:
            st.error(f"❌ 分析过程中发生错误: {str(e)}")
        finally:
            # 清理进度指示器
            if 'progress_bar' in locals():
                progress_bar.empty()
            if 'status_text' in locals():
                status_text.empty()

# 页脚
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray; padding: 1rem;'>" +
    "🔍 招标廉政体检系统 v2.0.0 | 基于AI技术 | " +
    f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" +
    "</div>",
    unsafe_allow_html=True
)