import os, requests, json, time, logging
from typing import Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# 配置参数
APP_ID = os.getenv("DIFY_APPID")
TOKEN = os.getenv("DIFY_TOKEN")
URL = os.getenv("DIFY_URL")  # 形如 `http://dify.internal/v1/chat-messages`
TIMEOUT = int(os.getenv("DIFY_TIMEOUT", 40))
MAX_RETRIES = int(os.getenv("DIFY_MAX_RETRIES", 3))
RETRY_DELAY = float(os.getenv("DIFY_RETRY_DELAY", 1.0))

class DifyClientError(Exception):
    """Dify客户端异常"""
    pass

class DifyConfigError(Exception):
    """Dify配置异常"""
    pass

def validate_config() -> None:
    """验证Dify配置"""
    missing_configs = []
    if not APP_ID:
        missing_configs.append("DIFY_APPID")
    if not TOKEN:
        missing_configs.append("DIFY_TOKEN")
    if not URL:
        missing_configs.append("DIFY_URL")
    
    if missing_configs:
        raise DifyConfigError(f"缺少必要的环境变量: {', '.join(missing_configs)}")
    
    # 验证URL格式
    if not URL.startswith(("http://", "https://")):
        raise DifyConfigError(f"DIFY_URL格式错误: {URL}")

# 初始化时验证配置
try:
    validate_config()
except DifyConfigError as e:
    logger.error(f"Dify配置错误: {e}")
    # 在生产环境中可能需要退出程序
    # raise

# 配置请求会话和重试策略
session = requests.Session()
retry_strategy = Retry(
    total=MAX_RETRIES,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "POST"],
    backoff_factor=RETRY_DELAY
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# 请求头
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "X-API-Key": APP_ID,
    "Content-Type": "application/json",
    "User-Agent": "BidAntiCorruption/1.0"
}

def create_prompt(snippet: str, meta: dict) -> str:
    """创建LLM提示词"""
    budget_info = f"{meta.get('budget', '未知')}元" if meta.get('budget') else "未知"
    filename_info = f"文件名：{meta.get('filename', '未知')}" if meta.get('filename') else ""
    
    prompt = f"""项目预算：{budget_info}
{filename_info}

请根据《招标投标法》及相关法规判断下列条款的廉政风险等级，并提供具体分析。

要求严格按照以下JSON格式输出：
{{
    "level": "high|medium|low",
    "issue_tags": ["具体问题标签"],
    "law_refs": ["相关法条引用"],
    "suggest": "改进建议"
}}

待分析条款：
{snippet}"""
    
    return prompt

def parse_llm_response(response_text: str) -> Dict[str, Any]:
    """解析LLM响应"""
    try:
        # 尝试直接解析JSON
        return json.loads(response_text)
    except json.JSONDecodeError:
        # 如果直接解析失败，尝试提取JSON部分
        try:
            # 查找JSON块
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                raise ValueError("未找到有效的JSON格式")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"LLM响应解析失败: {e}, 原始响应: {response_text[:200]}...")
            # 返回默认结构
            return {
                "level": "medium",
                "issue_tags": ["解析失败"],
                "law_refs": [],
                "suggest": "LLM响应格式异常，建议人工审核"
            }

def llm_eval(snippet: str, meta: dict) -> Dict[str, Any]:
    """调用LLM评估风险"""
    if not snippet or not snippet.strip():
        return {
            "level": "low",
            "issue_tags": [],
            "law_refs": [],
            "suggest": "内容为空"
        }
    
    # 检查配置
    if not all([APP_ID, TOKEN, URL]):
        logger.error("Dify配置不完整，跳过LLM分析")
        return {
            "level": "medium",
            "issue_tags": ["配置错误"],
            "law_refs": [],
            "suggest": "LLM服务配置不完整"
        }
    
    payload = {
        "inputs": {},
        "query": create_prompt(snippet, meta),
        "response_mode": "blocking",
        "user": meta.get('filename', 'anonymous')
    }
    
    start_time = time.time()
    
    try:
        logger.debug(f"发送LLM请求，片段长度: {len(snippet)}")
        
        response = session.post(
            URL,
            json=payload,
            headers=HEADERS,
            timeout=TIMEOUT
        )
        
        # 检查HTTP状态码
        if response.status_code == 401:
            raise DifyClientError("认证失败，请检查DIFY_TOKEN和DIFY_APPID")
        elif response.status_code == 403:
            raise DifyClientError("权限不足，请检查API权限配置")
        elif response.status_code == 429:
            raise DifyClientError("请求频率超限，请稍后重试")
        elif response.status_code >= 500:
            raise DifyClientError(f"Dify服务器错误: {response.status_code}")
        
        response.raise_for_status()
        
        # 解析响应
        response_data = response.json()
        
        if "answer" not in response_data:
            raise DifyClientError(f"响应格式异常: {response_data}")
        
        answer = response_data["answer"]
        result = parse_llm_response(answer)
        
        # 验证结果格式
        if not isinstance(result, dict):
            raise ValueError("LLM返回结果不是字典格式")
        
        # 确保必要字段存在
        result.setdefault("level", "medium")
        result.setdefault("issue_tags", [])
        result.setdefault("law_refs", [])
        result.setdefault("suggest", "")
        
        # 验证level字段
        if result["level"] not in ["high", "medium", "low"]:
            logger.warning(f"无效的风险等级: {result['level']}，设置为medium")
            result["level"] = "medium"
        
        elapsed_time = time.time() - start_time
        logger.debug(f"LLM分析完成，耗时: {elapsed_time:.2f}秒")
        
        return result
        
    except requests.exceptions.Timeout:
        logger.error(f"LLM请求超时 (>{TIMEOUT}秒)")
        return {
            "level": "medium",
            "issue_tags": ["请求超时"],
            "law_refs": [],
            "suggest": "LLM服务响应超时，建议人工审核"
        }
    
    except requests.exceptions.ConnectionError:
        logger.error("LLM服务连接失败")
        return {
            "level": "medium",
            "issue_tags": ["连接失败"],
            "law_refs": [],
            "suggest": "无法连接到LLM服务"
        }
    
    except DifyClientError as e:
        logger.error(f"Dify客户端错误: {e}")
        return {
            "level": "medium",
            "issue_tags": ["服务错误"],
            "law_refs": [],
            "suggest": f"LLM服务错误: {str(e)}"
        }
    
    except Exception as e:
        logger.error(f"LLM分析发生未知错误: {e}")
        return {
            "level": "medium",
            "issue_tags": ["未知错误"],
            "law_refs": [],
            "suggest": "LLM分析失败，建议人工审核"
        }

def test_connection() -> bool:
    """测试Dify连接"""
    try:
        test_payload = {
            "inputs": {},
            "query": "测试连接",
            "response_mode": "blocking",
            "user": "test"
        }
        
        response = session.post(
            URL,
            json=test_payload,
            headers=HEADERS,
            timeout=10
        )
        
        return response.status_code == 200
    except Exception as e:
        logger.error(f"连接测试失败: {e}")
        return False