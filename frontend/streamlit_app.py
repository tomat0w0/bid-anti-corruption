import streamlit as st
import requests
import json
import time
from typing import Dict, Any, Optional
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
    1. **上传文件**: 选择.docx格式的招标文件
    2. **设置预算**: 输入项目预算金额
    3. **开始分析**: 点击分析按钮等待结果
    4. **查看结果**: 浏览风险分析报告
    5. **导出报告**: 下载分析结果
    """)
    
    st.markdown("---")
    
    # 分析历史
    if st.session_state.analysis_history:
        st.header("📚 分析历史")
        for i, record in enumerate(reversed(st.session_state.analysis_history[-5:])):
            with st.expander(f"{record['filename']} - {record['timestamp']}"):
                st.write(f"风险评分: {record['risk_score']:.2f}")
                st.write(f"风险等级: {format_risk_level(record['risk_level'])}")
                st.write(f"发现问题: {record['total_hits']} 个")

# 主界面布局
tab1, tab2, tab3 = st.tabs(["📄 文件分析", "📊 分析结果", "🔧 系统管理"])

with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📁 文件上传")
        uploaded_file = st.file_uploader(
            "选择招标文件",
            type=["docx"],
            help="请上传.docx格式的招标文件，文件大小不超过10MB"
        )
        
        if uploaded_file:
            st.success(f"✅ 已选择文件: {uploaded_file.name}")
            st.info(f"📏 文件大小: {uploaded_file.size / 1024:.1f} KB")
    
    with col2:
        st.header("💰 项目信息")
        budget = st.number_input(
            "项目预算（万元）",
            min_value=0.0,
            value=100.0,
            step=10.0,
            format="%.1f",
            help="请输入项目预算金额（万元）"
        )
        
        # 其他元数据
        with st.expander("📋 其他信息（可选）"):
            project_location = st.text_input("项目地点", placeholder="如：北京市")
            company_location = st.text_input("公司地点", placeholder="如：上海市")
            registered_capital = st.number_input("注册资本（万元）", min_value=0.0, value=0.0)
    
    # 分析按钮
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        analyze_button = st.button(
            "🔍 开始分析",
            type="primary",
            disabled=uploaded_file is None,
            use_container_width=True
        )

with tab2:
    st.header("📊 分析结果")
    
    if 'current_result' in st.session_state:
        result = st.session_state.current_result
        
        # 风险概览卡片
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "风险评分", 
                f"{result['risk_score']:.2f}",
                delta=None
            )
        
        with col2:
            st.metric(
                "风险等级", 
                format_risk_level(result['risk_level'])
            )
        
        with col3:
            st.metric(
                "发现问题", 
                f"{len(result['rule_hits'])} 个"
            )
        
        with col4:
            st.metric(
                "处理时间", 
                f"{result['processing_time']:.2f}s"
            )
        
        # 风险分布图表
        if result['rule_hits']:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                chart = create_risk_chart(result['rule_hits'])
                if chart:
                    st.plotly_chart(chart, use_container_width=True)
            
            with col2:
                # 风险标签统计
                tags = []
                for hit in result['rule_hits']:
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
        
        if result['rule_hits']:
            for i, hit in enumerate(result['rule_hits'], 1):
                risk_level = hit.get('level', 'medium').lower()
                
                with st.expander(
                    f"风险项 {i}: {hit.get('rule_id', 'Unknown')} - {format_risk_level(risk_level)}",
                    expanded=(risk_level == 'high')
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
                        if risk_level == 'high':
                            st.error("🔴 高风险")
                        elif risk_level == 'medium':
                            st.warning("🟡 中风险")
                        else:
                            st.success("🟢 低风险")
                        
                        # 匹配位置
                        if 'match_start' in hit:
                            st.caption(f"位置: {hit['match_start']}-{hit.get('match_end', 'N/A')}")
        
        # LLM分析结果
        if result.get('llm_results'):
            st.markdown("---")
            st.header("🤖 AI深度分析")
            
            for i, llm_result in enumerate(result['llm_results'], 1):
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
                report = {
                    "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "文件名": result['file_info']['filename'],
                    "风险评分": result['risk_score'],
                    "风险等级": result['risk_level'],
                    "发现问题数": len(result['rule_hits']),
                    "详细结果": result
                }
                
                st.download_button(
                    label="下载JSON报告",
                    data=json.dumps(report, ensure_ascii=False, indent=2),
                    file_name=f"risk_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
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
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("清空分析历史", type="secondary"):
            st.session_state.analysis_history = []
            st.success("✅ 分析历史已清空")
    
    with col2:
        if st.button("清空当前结果", type="secondary"):
            if 'current_result' in st.session_state:
                del st.session_state.current_result
                st.success("✅ 当前结果已清空")

# 分析处理逻辑
if analyze_button and uploaded_file:
    with st.spinner("🔄 正在分析文件，请稍候..."):
        try:
            # 准备请求数据
            files = {
                "file": (uploaded_file.name, uploaded_file.getvalue(), 
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            }
            
            # 准备元数据
            form_data = {
                "budget": int(budget * 10000)  # 转换为元
            }
            
            # 添加可选元数据
            if project_location:
                form_data["project_location"] = project_location
            if company_location:
                form_data["company_location"] = company_location
            if registered_capital > 0:
                form_data["registered_capital"] = int(registered_capital * 10000)
            
            # 发送请求
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("📤 上传文件...")
            progress_bar.progress(25)
            
            response = requests.post(
                f"{api_url}/analyze",
                files=files,
                data=form_data,
                timeout=300
            )
            
            progress_bar.progress(75)
            status_text.text("🔍 分析中...")
            
            if response.status_code == 200:
                result = response.json()
                progress_bar.progress(100)
                status_text.text("✅ 分析完成！")
                
                # 保存结果
                st.session_state.current_result = result
                
                # 添加到历史记录
                history_record = {
                    "filename": uploaded_file.name,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "risk_score": result['risk_score'],
                    "risk_level": result['risk_level'],
                    "total_hits": len(result['rule_hits'])
                }
                st.session_state.analysis_history.append(history_record)
                
                # 显示成功消息
                st.success("🎉 分析完成！请查看'分析结果'标签页")
                
                # 自动切换到结果标签页
                time.sleep(1)
                st.rerun()
                
            else:
                progress_bar.empty()
                status_text.empty()
                error_detail = "未知错误"
                try:
                    error_info = response.json()
                    error_detail = error_info.get('detail', response.text)
                except:
                    error_detail = response.text
                
                st.error(f"❌ 分析失败 ({response.status_code}): {error_detail}")
                
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