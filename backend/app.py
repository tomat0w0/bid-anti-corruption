import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 导入自定义模块
from config import get_config, Config
from utils_doc import extract_text, DocumentProcessError
from run_rules import run_rules, get_rules_stats, reload_rules
from llm_client import llm_eval, DifyClientError, test_connection

# 获取配置
config = get_config()

# 设置日志
config.setup_logging()
config.create_directories()

import logging
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title=config.app_name,
    description="基于AI的招标文件风险分析系统",
    version=config.app_version,
    debug=config.debug
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.security.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisResult(BaseModel):
    """分析结果模型"""
    risk_score: float
    risk_level: str
    rule_hits: List[Dict[str, Any]]
    llm_results: List[Dict[str, Any]]
    processing_time: float
    file_info: Dict[str, Any]
    error_messages: List[str] = []
    system_info: Dict[str, Any] = {}

def get_current_config() -> Config:
    """依赖注入：获取当前配置"""
    return config

def validate_file(file: UploadFile, config: Config = Depends(get_current_config)) -> None:
    """验证上传的文件"""
    # 检查文件大小
    if file.size and file.size > config.file.max_file_size:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过限制 ({config.file.max_file_size / 1024 / 1024:.1f}MB)"
        )
    
    # 检查文件扩展名
    if file.filename:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in config.file.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {file_ext}. 支持的类型: {', '.join(config.file.allowed_extensions)}"
            )
    
    # 检查文件名
    if not file.filename or len(file.filename.strip()) == 0:
        raise HTTPException(
            status_code=400,
            detail="文件名不能为空"
        )

def doc_risk_score(items: List[Dict[str, Any]]) -> float:
    """计算文档风险评分"""
    if not items:
        return 0.0
    
    weight = {"high": 5, "medium": 2, "low": 0.5}
    total_weight = sum(weight.get(item.get("level", "low"), 0.5) for item in items)
    
    # 考虑风险项数量的影响
    risk_factor = min(len(items) / 10, 1.0)  # 最多10个风险项达到满分
    base_score = total_weight / len(items) if items else 0
    
    return round(base_score * (1 + risk_factor), 2)

def merge_results(rule_hits: List[Dict], llm_jsons: List[Dict]) -> List[Dict]:
    """
    合并规则检测结果和LLM分析结果
    """
    # 创建snippet到LLM结果的映射
    llm_map = {}
    for llm_result in llm_jsons:
        if isinstance(llm_result, dict) and "snippet" in llm_result:
            key = llm_result["snippet"][:80]
            llm_map[key] = llm_result
    
    # 合并结果
    merged = []
    for hit in rule_hits:
        key = hit["snippet"][:80]
        if key in llm_map:
            # 合并LLM结果，保留原有字段
            llm_data = llm_map[key]
            merged_item = {**hit}
            
            # 更新level（以LLM结果为准）
            if "level" in llm_data:
                merged_item["level"] = llm_data["level"]
            
            # 添加LLM特有字段
            for field in ["issue_tags", "law_refs", "suggest"]:
                if field in llm_data:
                    merged_item[field] = llm_data[field]
            
            merged.append(merged_item)
        else:
            merged.append(hit)
    
    return merged

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/analyze", response_model=AnalysisResult)
async def analyze(
    file: UploadFile = File(...),
    budget: int = Form(0),
    config: Config = Depends(get_current_config)
):
    """分析招标文件的廉政风险"""
    start_time = time.time()
    
    try:
        # 验证文件
        validate_file(file, config)
        logger.info(f"开始分析文件: {file.filename}, 预算: {budget}")
        
        # 提取文本
        try:
            text = extract_text(file)
            if not text.strip():
                raise HTTPException(status_code=400, detail="文件内容为空或无法提取文本")
        except Exception as e:
            logger.error(f"文本提取失败: {str(e)}")
            raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
        
        # 运行规则检测
        meta = {"budget": budget, "filename": file.filename}
        try:
            hits = run_rules(text, meta)
            logger.info(f"规则检测完成，发现 {len(hits)} 个风险点")
        except Exception as e:
            logger.error(f"规则检测失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"规则检测失败: {str(e)}")
        
        # 准备LLM分析
        high_snips = [h["snippet"] for h in hits if h["level"] == "high"]
        medium_snips = [h["snippet"] for h in hits if h["level"] == "medium"]
        all_snips = high_snips + medium_snips
        
        # 限制并发数量
        if len(all_snips) > config.processing.max_concurrent_llm:
            logger.warning(f"风险点数量 ({len(all_snips)}) 超过并发限制 ({config.processing.max_concurrent_llm})，将处理前 {config.processing.max_concurrent_llm} 个")
            all_snips = all_snips[:config.processing.max_concurrent_llm]
        
        # 异步LLM分析
        llm_results = []
        if all_snips:
            try:
                llm_results = await process_llm_batch(all_snips, budget, config)
                logger.info(f"LLM分析完成，成功处理 {len(llm_results)} 个片段")
                
            except Exception as e:
                logger.error(f"LLM分析失败: {str(e)}")
                llm_results = []  # 继续处理，不中断流程
        
        # 合并结果
        merged = merge_results(hits, llm_results)
        
        # 计算评分
        score = doc_risk_score(merged)
        
        analysis_time = time.time() - start_time
        logger.info(f"分析完成，耗时: {analysis_time:.2f}秒，风险评分: {score}")
        
        return AnalysisResult(
            risk_score=score,
            risk_level=get_risk_level(score),
            rule_hits=hits,
            llm_results=llm_results,
            processing_time=analysis_time,
            file_info={
                "filename": file.filename,
                "size": file.size,
                "content_length": len(text)
            },
            system_info={
                "total_hits": len(merged),
                "llm_processed": len(llm_results),
                "rules_applied": len(hits)
            }
        )
        
    except HTTPException:
        raise
    except DocumentProcessError as e:
        logger.error(f"文档处理错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"文档处理错误: {str(e)}")
    except DifyClientError as e:
        logger.error(f"Dify客户端错误: {str(e)}")
        raise HTTPException(status_code=503, detail=f"AI服务暂时不可用: {str(e)}")
    except Exception as e:
        logger.error(f"分析过程发生未知错误: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")

async def process_llm_batch(snippets: List[str], budget: float, config: Config) -> List[Dict[str, Any]]:
    """批量处理LLM评估"""
    if not snippets:
        return []
    
    semaphore = asyncio.Semaphore(config.processing.max_concurrent_llm)
    
    async def process_single_snippet(snippet: str) -> Optional[Dict[str, Any]]:
        async with semaphore:
            try:
                # 使用asyncio.wait_for添加超时控制
                result = await asyncio.wait_for(
                    asyncio.to_thread(llm_eval, snippet, {"budget": budget}),
                    timeout=config.dify.timeout
                )
                
                if result and "error" not in result:
                    result["snippet"] = snippet[:100] + "..." if len(snippet) > 100 else snippet
                    return result
                else:
                    logger.warning(f"LLM评估失败: {result}")
                    return {
                        "snippet": snippet[:100] + "..." if len(snippet) > 100 else snippet,
                        "error": "LLM评估返回错误结果",
                        "level": "medium",
                        "confidence": 0.3
                    }
            except asyncio.TimeoutError:
                logger.error(f"LLM评估超时: {snippet[:50]}...")
                return {
                    "snippet": snippet[:100] + "..." if len(snippet) > 100 else snippet,
                    "error": "LLM评估超时",
                    "level": "medium",
                    "confidence": 0.2
                }
            except Exception as e:
                logger.error(f"LLM评估异常: {e}")
                return {
                    "snippet": snippet[:100] + "..." if len(snippet) > 100 else snippet,
                    "error": f"LLM评估异常: {str(e)}",
                    "level": "medium",
                    "confidence": 0.1
                }
    
    # 并发处理所有片段
    tasks = [process_single_snippet(snippet) for snippet in snippets]
    
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=config.processing.timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.error("批量LLM处理超时")
        return [{
            "error": "批量LLM处理超时",
            "level": "medium",
            "confidence": 0.1
        }]
    
    # 过滤和处理结果
    valid_results = []
    for result in results:
        if isinstance(result, dict) and result is not None:
            valid_results.append(result)
        elif isinstance(result, Exception):
            logger.error(f"LLM处理异常: {result}")
            valid_results.append({
                "error": f"处理异常: {str(result)}",
                "level": "medium",
                "confidence": 0.1
            })
    
    return valid_results

def get_risk_level(score: float) -> str:
    """根据评分获取风险等级"""
    if score >= 4.0:
        return "high"
    elif score >= 2.0:
        return "medium"
    else:
        return "low"

@app.get("/stats")
async def get_stats(config: Config = Depends(get_current_config)):
    """获取系统统计信息"""
    try:
        rules_stats = get_rules_stats()
        return {
            "file_limits": {
                "max_file_size_mb": config.file.max_file_size // 1024 // 1024,
                "allowed_extensions": config.file.allowed_extensions
            },
            "processing": {
                "max_concurrent_llm": config.processing.max_concurrent_llm,
                "timeout_seconds": config.processing.timeout_seconds
            },
            "rules": rules_stats,
            "dify": {
                "api_url": config.dify.api_url,
                "timeout": config.dify.timeout,
                "connected": await test_dify_connection(config)
            },
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail="获取统计信息失败")

async def test_dify_connection(config: Config) -> bool:
    """测试Dify连接"""
    try:
        return await asyncio.to_thread(test_connection)
    except Exception as e:
        logger.error(f"测试Dify连接失败: {e}")
        return False

@app.post("/reload-rules")
async def reload_rules_endpoint():
    """重新加载规则"""
    try:
        result = reload_rules()
        logger.info("规则重新加载成功")
        return {
            "success": True,
            "message": "规则重新加载成功",
            "rules_loaded": result.get("rules_loaded", 0),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"重新加载规则失败: {e}")
        raise HTTPException(status_code=500, detail=f"重新加载规则失败: {str(e)}")