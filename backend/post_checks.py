import logging
import re
from typing import Dict, Any, Union, Optional
from datetime import datetime, timedelta
import math

logger = logging.getLogger(__name__)

class PostCheckResult:
    """后处理检查结果"""
    def __init__(self, level: str, confidence: float = 1.0, reason: str = "", details: Dict[str, Any] = None):
        self.level = level
        self.confidence = confidence
        self.reason = reason
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'level': self.level,
            'confidence': self.confidence,
            'reason': self.reason,
            'details': self.details
        }

def capital_vs_budget(match, meta) -> Union[str, Dict[str, Any]]:
    """注册资本与项目预算比较"""
    try:
        capital = meta.get("registered_capital", 0)
        budget = meta.get("project_budget", 0)
        
        # 数据验证
        if not isinstance(capital, (int, float)) or not isinstance(budget, (int, float)):
            logger.warning("注册资本或项目预算数据类型错误")
            return PostCheckResult("medium", 0.5, "数据类型错误").to_dict()
        
        if capital <= 0 or budget <= 0:
            logger.info(f"注册资本({capital})或项目预算({budget})为零或负数")
            return PostCheckResult("medium", 0.6, "缺少有效的资本或预算数据").to_dict()
        
        ratio = capital / budget
        
        # 风险评估逻辑
        if ratio < 0.05:  # 注册资本小于预算的5%
            level = "high"
            confidence = 0.9
            reason = f"注册资本({capital:,.0f})仅为项目预算({budget:,.0f})的{ratio:.1%}，存在履约能力不足风险"
        elif ratio < 0.1:  # 注册资本小于预算的10%
            level = "high"
            confidence = 0.8
            reason = f"注册资本({capital:,.0f})为项目预算({budget:,.0f})的{ratio:.1%}，履约能力可能不足"
        elif ratio < 0.3:  # 注册资本小于预算的30%
            level = "medium"
            confidence = 0.7
            reason = f"注册资本({capital:,.0f})为项目预算({budget:,.0f})的{ratio:.1%}，需关注履约能力"
        elif ratio < 0.5:  # 注册资本小于预算的50%
            level = "medium"
            confidence = 0.6
            reason = f"注册资本({capital:,.0f})为项目预算({budget:,.0f})的{ratio:.1%}，履约能力一般"
        else:
            level = "low"
            confidence = 0.5
            reason = f"注册资本({capital:,.0f})为项目预算({budget:,.0f})的{ratio:.1%}，履约能力充足"
        
        details = {
            'capital': capital,
            'budget': budget,
            'ratio': ratio,
            'ratio_percentage': f"{ratio:.1%}"
        }
        
        return PostCheckResult(level, confidence, reason, details).to_dict()
        
    except Exception as e:
        logger.error(f"资本预算检查失败: {e}")
        return PostCheckResult("medium", 0.3, f"检查过程出错: {str(e)}").to_dict()

def company_age_check(match, meta) -> Union[str, Dict[str, Any]]:
    """公司成立时间检查"""
    try:
        establishment_date = meta.get("establishment_date")
        if not establishment_date:
            return PostCheckResult("medium", 0.5, "缺少公司成立时间信息").to_dict()
        
        # 解析日期
        if isinstance(establishment_date, str):
            try:
                establishment_date = datetime.strptime(establishment_date, "%Y-%m-%d")
            except ValueError:
                try:
                    establishment_date = datetime.strptime(establishment_date, "%Y/%m/%d")
                except ValueError:
                    return PostCheckResult("medium", 0.4, "日期格式无法解析").to_dict()
        
        # 计算公司年龄
        company_age = (datetime.now() - establishment_date).days / 365.25
        
        if company_age < 0.5:  # 成立不到半年
            level = "high"
            confidence = 0.9
            reason = f"公司成立仅{company_age:.1f}年，经营历史过短"
        elif company_age < 1:  # 成立不到1年
            level = "high"
            confidence = 0.8
            reason = f"公司成立{company_age:.1f}年，经营历史较短"
        elif company_age < 2:  # 成立不到2年
            level = "medium"
            confidence = 0.7
            reason = f"公司成立{company_age:.1f}年，经营历史一般"
        else:
            level = "low"
            confidence = 0.5
            reason = f"公司成立{company_age:.1f}年，经营历史充足"
        
        details = {
            'establishment_date': establishment_date.strftime("%Y-%m-%d"),
            'company_age_years': round(company_age, 1)
        }
        
        return PostCheckResult(level, confidence, reason, details).to_dict()
        
    except Exception as e:
        logger.error(f"公司年龄检查失败: {e}")
        return PostCheckResult("medium", 0.3, f"检查过程出错: {str(e)}").to_dict()

def qualification_level_check(match, meta) -> Union[str, Dict[str, Any]]:
    """资质等级检查"""
    try:
        required_qualification = meta.get("required_qualification", "")
        company_qualification = meta.get("company_qualification", "")
        
        if not required_qualification or not company_qualification:
            return PostCheckResult("medium", 0.5, "缺少资质信息").to_dict()
        
        # 资质等级映射
        qualification_levels = {
            "特级": 5, "一级": 4, "二级": 3, "三级": 2, "四级": 1,
            "甲级": 4, "乙级": 3, "丙级": 2, "丁级": 1
        }
        
        required_level = 0
        company_level = 0
        
        # 解析要求的资质等级
        for level, score in qualification_levels.items():
            if level in required_qualification:
                required_level = max(required_level, score)
        
        # 解析公司的资质等级
        for level, score in qualification_levels.items():
            if level in company_qualification:
                company_level = max(company_level, score)
        
        if required_level == 0 or company_level == 0:
            return PostCheckResult("medium", 0.4, "无法解析资质等级").to_dict()
        
        if company_level < required_level:
            level = "high"
            confidence = 0.9
            reason = f"公司资质等级({company_qualification})低于要求({required_qualification})"
        elif company_level == required_level:
            level = "low"
            confidence = 0.8
            reason = f"公司资质等级({company_qualification})符合要求({required_qualification})"
        else:
            level = "low"
            confidence = 0.7
            reason = f"公司资质等级({company_qualification})高于要求({required_qualification})"
        
        details = {
            'required_qualification': required_qualification,
            'company_qualification': company_qualification,
            'required_level_score': required_level,
            'company_level_score': company_level
        }
        
        return PostCheckResult(level, confidence, reason, details).to_dict()
        
    except Exception as e:
        logger.error(f"资质等级检查失败: {e}")
        return PostCheckResult("medium", 0.3, f"检查过程出错: {str(e)}").to_dict()

def geographic_restriction_check(match, meta) -> Union[str, Dict[str, Any]]:
    """地域限制检查"""
    try:
        project_location = meta.get("project_location", "")
        company_location = meta.get("company_location", "")
        
        if not project_location or not company_location:
            return PostCheckResult("medium", 0.5, "缺少地理位置信息").to_dict()
        
        # 检查是否存在地域限制表述
        match_text = match.group(0).lower()
        restriction_keywords = ["本地", "当地", "本市", "本省", "本区", "本县", "就近"]
        
        has_restriction = any(keyword in match_text for keyword in restriction_keywords)
        
        if has_restriction:
            # 检查公司是否在项目所在地
            same_location = any(loc in company_location for loc in project_location.split()) or \
                           any(loc in project_location for loc in company_location.split())
            
            if same_location:
                level = "medium"
                confidence = 0.6
                reason = f"存在地域限制要求，公司位于项目所在地({project_location})"
            else:
                level = "high"
                confidence = 0.8
                reason = f"存在地域限制要求，公司({company_location})不在项目所在地({project_location})"
        else:
            level = "low"
            confidence = 0.5
            reason = "未发现明显的地域限制要求"
        
        details = {
            'project_location': project_location,
            'company_location': company_location,
            'has_restriction': has_restriction,
            'restriction_keywords_found': [kw for kw in restriction_keywords if kw in match_text]
        }
        
        return PostCheckResult(level, confidence, reason, details).to_dict()
        
    except Exception as e:
        logger.error(f"地域限制检查失败: {e}")
        return PostCheckResult("medium", 0.3, f"检查过程出错: {str(e)}").to_dict()

def price_reasonableness_check(match, meta) -> Union[str, Dict[str, Any]]:
    """价格合理性检查"""
    try:
        bid_price = meta.get("bid_price", 0)
        budget = meta.get("project_budget", 0)
        market_price = meta.get("market_reference_price", 0)
        
        if bid_price <= 0 or budget <= 0:
            return PostCheckResult("medium", 0.5, "缺少有效的价格信息").to_dict()
        
        budget_ratio = bid_price / budget
        
        # 价格异常判断
        if budget_ratio < 0.5:  # 投标价格低于预算50%
            level = "high"
            confidence = 0.9
            reason = f"投标价格({bid_price:,.0f})过低，仅为预算({budget:,.0f})的{budget_ratio:.1%}"
        elif budget_ratio < 0.7:  # 投标价格低于预算70%
            level = "medium"
            confidence = 0.7
            reason = f"投标价格({bid_price:,.0f})较低，为预算({budget:,.0f})的{budget_ratio:.1%}"
        elif budget_ratio > 1.1:  # 投标价格超过预算10%
            level = "high"
            confidence = 0.8
            reason = f"投标价格({bid_price:,.0f})超预算，为预算({budget:,.0f})的{budget_ratio:.1%}"
        else:
            level = "low"
            confidence = 0.6
            reason = f"投标价格({bid_price:,.0f})合理，为预算({budget:,.0f})的{budget_ratio:.1%}"
        
        details = {
            'bid_price': bid_price,
            'budget': budget,
            'budget_ratio': budget_ratio,
            'budget_ratio_percentage': f"{budget_ratio:.1%}"
        }
        
        # 如果有市场参考价，进行额外检查
        if market_price > 0:
            market_ratio = bid_price / market_price
            details['market_price'] = market_price
            details['market_ratio'] = market_ratio
            details['market_ratio_percentage'] = f"{market_ratio:.1%}"
            
            if market_ratio < 0.6 or market_ratio > 1.4:
                if level == "low":
                    level = "medium"
                details['market_deviation_warning'] = True
        
        return PostCheckResult(level, confidence, reason, details).to_dict()
        
    except Exception as e:
        logger.error(f"价格合理性检查失败: {e}")
        return PostCheckResult("medium", 0.3, f"检查过程出错: {str(e)}").to_dict()

def technical_specification_check(match, meta) -> Union[str, Dict[str, Any]]:
    """技术规格检查"""
    try:
        match_text = match.group(0)
        
        # 检查是否包含品牌指定性语言
        brand_indicators = ["品牌", "型号", "或同等产品", "或相当", "同等性能"]
        specification_indicators = ["技术参数", "性能指标", "规格要求"]
        
        has_brand_mention = any(indicator in match_text for indicator in brand_indicators)
        has_specification = any(indicator in match_text for indicator in specification_indicators)
        
        # 检查是否有"或同等"等开放性表述
        openness_indicators = ["或同等", "或相当", "或类似", "同等产品", "同等性能"]
        has_openness = any(indicator in match_text for indicator in openness_indicators)
        
        if has_brand_mention and not has_openness:
            level = "high"
            confidence = 0.8
            reason = "技术规格中存在品牌指定，缺少开放性表述"
        elif has_brand_mention and has_openness:
            level = "medium"
            confidence = 0.6
            reason = "技术规格中提及品牌但包含开放性表述"
        elif has_specification:
            level = "low"
            confidence = 0.7
            reason = "技术规格描述相对客观"
        else:
            level = "medium"
            confidence = 0.5
            reason = "技术规格描述不够明确"
        
        details = {
            'has_brand_mention': has_brand_mention,
            'has_specification': has_specification,
            'has_openness': has_openness,
            'brand_indicators_found': [ind for ind in brand_indicators if ind in match_text],
            'openness_indicators_found': [ind for ind in openness_indicators if ind in match_text]
        }
        
        return PostCheckResult(level, confidence, reason, details).to_dict()
        
    except Exception as e:
        logger.error(f"技术规格检查失败: {e}")
        return PostCheckResult("medium", 0.3, f"检查过程出错: {str(e)}").to_dict()

# 后处理检查函数注册表
POST_CHECK_FUNCTIONS = {
    'capital_vs_budget': capital_vs_budget,
    'company_age_check': company_age_check,
    'qualification_level_check': qualification_level_check,
    'geographic_restriction_check': geographic_restriction_check,
    'price_reasonableness_check': price_reasonableness_check,
    'technical_specification_check': technical_specification_check
}

def get_available_post_checks() -> Dict[str, str]:
    """获取可用的后处理检查函数列表"""
    return {
        'capital_vs_budget': '注册资本与项目预算比较',
        'company_age_check': '公司成立时间检查',
        'qualification_level_check': '资质等级检查',
        'geographic_restriction_check': '地域限制检查',
        'price_reasonableness_check': '价格合理性检查',
        'technical_specification_check': '技术规格检查'
    }

def run_post_check(check_name: str, match, meta) -> Union[str, Dict[str, Any]]:
    """运行指定的后处理检查"""
    if check_name not in POST_CHECK_FUNCTIONS:
        logger.error(f"未知的后处理检查函数: {check_name}")
        return PostCheckResult("medium", 0.3, f"未知的检查函数: {check_name}").to_dict()
    
    try:
        return POST_CHECK_FUNCTIONS[check_name](match, meta)
    except Exception as e:
        logger.error(f"后处理检查 {check_name} 执行失败: {e}")
        return PostCheckResult("medium", 0.3, f"检查执行失败: {str(e)}").to_dict()