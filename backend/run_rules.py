import regex as re
import yaml
import importlib
import pathlib
import logging
import time
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)

@dataclass
class RuleMatch:
    """规则匹配结果"""
    rule_id: str
    level: str
    tags: List[str]
    snippet: str
    match_start: int
    match_end: int
    confidence: float = 1.0
    context: str = ""

class RuleEngine:
    """规则引擎类"""
    
    def __init__(self, rules_file: str = None):
        self.rules_file = rules_file or pathlib.Path(__file__).with_name("rules.yaml")
        self.rules = []
        self.last_modified = 0
        self.pc_mod = None
        self._lock = Lock()
        self.load_rules()
        self.load_post_checks()
    
    def load_post_checks(self):
        """加载后处理检查模块"""
        try:
            self.pc_mod = importlib.import_module("backend.post_checks")
            logger.info("后处理检查模块加载成功")
        except ImportError as e:
            logger.warning(f"后处理检查模块加载失败: {e}")
            self.pc_mod = None
    
    def load_rules(self, force_reload: bool = False) -> bool:
        """加载或重新加载规则"""
        try:
            if not self.rules_file.exists():
                logger.error(f"规则文件不存在: {self.rules_file}")
                return False
            
            current_modified = self.rules_file.stat().st_mtime
            
            # 检查是否需要重新加载
            if not force_reload and current_modified <= self.last_modified:
                return True
            
            with self._lock:
                # 读取并解析规则文件
                rules_text = self.rules_file.read_text(encoding='utf-8')
                new_rules = yaml.safe_load(rules_text)
                
                if not isinstance(new_rules, list):
                    logger.error("规则文件格式错误：应该是规则列表")
                    return False
                
                # 验证规则格式
                validated_rules = []
                for i, rule in enumerate(new_rules):
                    if self.validate_rule(rule, i):
                        validated_rules.append(self.normalize_rule(rule))
                
                self.rules = validated_rules
                self.last_modified = current_modified
                
                logger.info(f"成功加载 {len(self.rules)} 条规则")
                return True
                
        except yaml.YAMLError as e:
            logger.error(f"规则文件YAML格式错误: {e}")
            return False
        except Exception as e:
            logger.error(f"加载规则文件失败: {e}")
            return False
    
    def validate_rule(self, rule: dict, index: int) -> bool:
        """验证单个规则的格式"""
        required_fields = ['id', 'level', 'include']
        
        for field in required_fields:
            if field not in rule:
                logger.error(f"规则 {index} 缺少必需字段: {field}")
                return False
        
        # 验证level字段
        if rule['level'] not in ['high', 'medium', 'low']:
            logger.error(f"规则 {rule.get('id', index)} 的level字段无效: {rule['level']}")
            return False
        
        # 验证include字段
        if not isinstance(rule['include'], list) or not rule['include']:
            logger.error(f"规则 {rule.get('id', index)} 的include字段必须是非空列表")
            return False
        
        # 验证正则表达式
        for pattern in rule['include']:
            try:
                re.compile(pattern)
            except re.error as e:
                logger.error(f"规则 {rule.get('id', index)} 的正则表达式无效: {pattern}, 错误: {e}")
                return False
        
        return True
    
    def normalize_rule(self, rule: dict) -> dict:
        """标准化规则格式"""
        normalized = rule.copy()
        
        # 设置默认值
        normalized.setdefault('tags', [])
        normalized.setdefault('exclude', [])
        normalized.setdefault('priority', 1.0)
        normalized.setdefault('enabled', True)
        normalized.setdefault('description', '')
        
        return normalized
    
    def run_rules(self, text: str, meta: dict) -> List[Dict[str, Any]]:
        """运行规则检测"""
        if not text or not text.strip():
            return []
        
        # 检查是否需要重新加载规则
        self.load_rules()
        
        if not self.rules:
            logger.warning("没有可用的规则")
            return []
        
        hits = []
        start_time = time.time()
        
        # 按优先级排序规则
        sorted_rules = sorted(self.rules, key=lambda r: r.get('priority', 1.0), reverse=True)
        
        for rule in sorted_rules:
            if not rule.get('enabled', True):
                continue
                
            try:
                rule_hits = self._process_single_rule(rule, text, meta)
                hits.extend(rule_hits)
            except Exception as e:
                logger.error(f"处理规则 {rule['id']} 时发生错误: {e}")
                continue
        
        # 去重和排序
        hits = self._deduplicate_hits(hits)
        hits = sorted(hits, key=lambda h: (h['match_start'], -len(h['snippet'])))
        
        elapsed_time = time.time() - start_time
        logger.info(f"规则检测完成，耗时: {elapsed_time:.3f}秒，发现 {len(hits)} 个匹配")
        
        return [hit.__dict__ if isinstance(hit, RuleMatch) else hit for hit in hits]
    
    def _process_single_rule(self, rule: dict, text: str, meta: dict) -> List[RuleMatch]:
        """处理单个规则"""
        hits = []
        
        for pattern in rule['include']:
            try:
                for match in re.finditer(pattern, text, flags=re.I | re.MULTILINE):
                    # 检查排除模式
                    if self._should_exclude(rule, match, text):
                        continue
                    
                    # 创建匹配结果
                    hit = self._create_rule_match(rule, match, text, meta)
                    if hit:
                        hits.append(hit)
                        
            except re.error as e:
                logger.error(f"规则 {rule['id']} 的正则表达式执行失败: {pattern}, 错误: {e}")
                continue
        
        return hits
    
    def _should_exclude(self, rule: dict, match: re.Match, text: str) -> bool:
        """检查是否应该排除此匹配"""
        exclude_patterns = rule.get('exclude', [])
        if not exclude_patterns:
            return False
        
        # 扩展上下文范围进行排除检查
        context_start = max(0, match.start() - 50)
        context_end = min(len(text), match.end() + 50)
        context = text[context_start:context_end]
        
        for exclude_pattern in exclude_patterns:
            try:
                if re.search(exclude_pattern, context, flags=re.I):
                    logger.debug(f"匹配被排除模式过滤: {exclude_pattern}")
                    return True
            except re.error as e:
                logger.warning(f"排除模式正则表达式错误: {exclude_pattern}, {e}")
                continue
        
        return False
    
    def _create_rule_match(self, rule: dict, match: re.Match, text: str, meta: dict) -> Optional[RuleMatch]:
        """创建规则匹配结果"""
        try:
            # 获取匹配片段和上下文
            snippet_start = max(0, match.start() - 30)
            snippet_end = min(len(text), match.end() + 30)
            snippet = text[snippet_start:snippet_end]
            
            # 获取更大的上下文
            context_start = max(0, match.start() - 100)
            context_end = min(len(text), match.end() + 100)
            context = text[context_start:context_end]
            
            # 初始风险等级
            level = rule['level']
            confidence = 1.0
            
            # 执行后处理检查
            if rule.get('post_check') and self.pc_mod:
                try:
                    post_check_func = getattr(self.pc_mod, rule['post_check'])
                    result = post_check_func(match, meta)
                    
                    if isinstance(result, str):
                        level = result
                    elif isinstance(result, dict):
                        level = result.get('level', level)
                        confidence = result.get('confidence', confidence)
                    
                except AttributeError:
                    logger.warning(f"后处理函数不存在: {rule['post_check']}")
                except Exception as e:
                    logger.error(f"后处理检查失败: {rule['post_check']}, 错误: {e}")
            
            return RuleMatch(
                rule_id=rule['id'],
                level=level,
                tags=rule.get('tags', []),
                snippet=snippet,
                match_start=match.start(),
                match_end=match.end(),
                confidence=confidence,
                context=context
            )
            
        except Exception as e:
            logger.error(f"创建规则匹配结果失败: {e}")
            return None
    
    def _deduplicate_hits(self, hits: List[RuleMatch]) -> List[RuleMatch]:
        """去除重复的匹配结果"""
        if not hits:
            return hits
        
        # 按位置和内容去重
        seen = set()
        unique_hits = []
        
        for hit in hits:
            # 创建去重键：位置范围 + 规则ID
            dedup_key = (hit.match_start, hit.match_end, hit.rule_id)
            
            if dedup_key not in seen:
                seen.add(dedup_key)
                unique_hits.append(hit)
        
        return unique_hits
    
    def get_rule_stats(self) -> Dict[str, Any]:
        """获取规则统计信息"""
        if not self.rules:
            return {}
        
        stats = {
            'total_rules': len(self.rules),
            'enabled_rules': len([r for r in self.rules if r.get('enabled', True)]),
            'rules_by_level': {},
            'rules_by_tags': {},
            'last_modified': self.last_modified
        }
        
        # 按级别统计
        for rule in self.rules:
            level = rule['level']
            stats['rules_by_level'][level] = stats['rules_by_level'].get(level, 0) + 1
        
        # 按标签统计
        for rule in self.rules:
            for tag in rule.get('tags', []):
                stats['rules_by_tags'][tag] = stats['rules_by_tags'].get(tag, 0) + 1
        
        return stats

# 全局规则引擎实例
_rule_engine = None
_engine_lock = Lock()

def get_rule_engine() -> RuleEngine:
    """获取规则引擎单例"""
    global _rule_engine
    if _rule_engine is None:
        with _engine_lock:
            if _rule_engine is None:
                _rule_engine = RuleEngine()
    return _rule_engine

def run_rules(text: str, meta: dict) -> List[Dict[str, Any]]:
    """运行规则检测（向后兼容的接口）"""
    engine = get_rule_engine()
    return engine.run_rules(text, meta)

def reload_rules() -> bool:
    """重新加载规则"""
    engine = get_rule_engine()
    return engine.load_rules(force_reload=True)

def get_rules_stats() -> Dict[str, Any]:
    """获取规则统计信息"""
    engine = get_rule_engine()
    return engine.get_rule_stats()