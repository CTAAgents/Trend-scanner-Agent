"""
因子生成器模块

基于 FactorEngine 论文思想，实现 LLM 引导的因子生成。
核心原则：
1. 因子即代码：因子是 LLM 生成的可执行 Python 代码
2. 三大分离：逻辑修订 vs 参数优化、LLM 引导搜索 vs 贝叶斯优化、LLM 使用 vs 本地计算
3. 知识注入闭环：研报 → 多 Agent 提取 → 验证 → 可执行因子程序

版本：v1.0
创建日期：2026-06-15
"""

import json
import logging
import re
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FactorResult:
    """因子生成结果"""
    code: str
    metadata: Dict[str, Any]
    validation: Dict[str, Any]
    source: str  # 'market_context' 或 'research_report'


@dataclass
class FactorMetadata:
    """因子元数据"""
    name: str
    description: str
    logic: str
    source: str
    created_at: str


class FactorGenerator:
    """
    LLM 引导的因子生成器
    
    基于 FactorEngine 论文思想，实现：
    1. 因子即代码：生成可执行的 Python 因子函数
    2. 知识注入：从研报中提取因子逻辑
    3. 验证机制：确保因子代码质量和有效性
    """
    
    def __init__(self, llm_client=None, validator=None, knowledge_manager=None):
        """
        初始化因子生成器
        
        Args:
            llm_client: LLM 客户端，用于生成因子代码
            validator: 因子验证器，用于验证因子代码
            knowledge_manager: 因子知识管理器，用于管理因子知识库
        """
        self.llm_client = llm_client
        self.validator = validator
        self.knowledge_manager = knowledge_manager
        
        # 因子知识库路径
        self.knowledge_base_path = Path("data/factor_knowledge.json")
        
        # 加载因子知识库
        self.factor_knowledge = self._load_factor_knowledge()
        
        logger.info("FactorGenerator 初始化完成")
    
    def generate_factor(self, market_context: str, research_report: str = None) -> FactorResult:
        """
        生成可执行的因子代码
        
        当 LLM 客户端可用时，调用 LLM 生成因子代码。
        当 LLM 客户端不可用时，降级为规则模式（使用预置因子）。
        
        Args:
            market_context: 市场上下文，描述当前市场状态
            research_report: 研报内容，可选
            
        Returns:
            FactorResult: 因子生成结果
        """
        logger.info(f"开始生成因子，市场上下文长度: {len(market_context)}")
        
        # LLM 客户端不可用时，降级为规则模式
        if self.llm_client is None:
            logger.info("LLM 客户端未配置，使用规则模式（预置因子）")
            return self._generate_factor_by_rules(market_context)
        
        # 1. 构建 prompt
        prompt = self._build_generation_prompt(market_context, research_report)
        
        # 2. 调用 LLM 生成因子代码
        factor_code = self.llm_client.generate(prompt)
        
        # 3. 提取因子代码（从 markdown 代码块中提取）
        factor_code = self._extract_code_from_response(factor_code)
        
        # 4. 验证因子代码
        validation_result = self._validate_factor(factor_code)
        
        # 5. 如果验证失败，尝试修正
        if not validation_result.get('is_valid', False):
            logger.warning("因子代码验证失败，尝试修正")
            factor_code = self._refine_factor(factor_code, validation_result.get('errors', []))
            validation_result = self._validate_factor(factor_code)
        
        # 6. 提取因子元数据
        metadata = self._extract_metadata(factor_code, market_context, research_report)
        
        # 7. 构建结果
        result = FactorResult(
            code=factor_code,
            metadata=metadata,
            validation=validation_result,
            source='research_report' if research_report else 'market_context'
        )
        
        logger.info(f"因子生成完成，验证结果: {validation_result.get('is_valid', False)}")
        
        return result
    
    def _build_generation_prompt(self, market_context: str, research_report: str = None) -> str:
        """
        构建因子生成 prompt
        
        Args:
            market_context: 市场上下文
            research_report: 研报内容
            
        Returns:
            str: 构建好的 prompt
        """
        prompt = """你是一个量化因子挖掘专家，擅长从市场数据和研报中提取有效的交易因子。

## 任务
根据以下市场上下文，生成一个可执行的因子代码。

## 市场上下文
{market_context}

## 因子要求
1. 因子必须是 Python 函数，接收 pandas DataFrame 作为输入
2. 因子返回 pandas Series，值建议在 [-1, 1] 之间（或可归一化到此范围）
3. 因子逻辑必须清晰，可解释
4. 优先使用技术指标和价量数据
5. 因子应具有一定的预测能力

## 输出格式
请严格按照以下格式输出：

```python
def factor(df: pd.DataFrame) -> pd.Series:
    \"\"\"
    因子名称：[因子名称]
    因子描述：[简要描述因子逻辑和作用]
    逻辑：[详细说明因子的计算逻辑]
    
    Args:
        df: 包含 OHLCV 数据的 DataFrame
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - volume: 成交量
        
    Returns:
        pd.Series: 因子值，index 与输入 df 相同
    \"\"\"
    # 因子实现代码
    # ...
    
    return result
```

## 注意事项
1. 不要使用未来数据（如用 t+1 的收盘价）
2. 确保代码可执行，无语法错误
3. 处理好 NaN 值
4. 如果需要使用特定库，请在函数内导入
"""
        
        if research_report:
            prompt += f"""

## 研报参考
以下研报内容可能包含有用的因子逻辑，请参考：

{research_report}
"""
        
        return prompt.format(market_context=market_context)
    
    def _extract_code_from_response(self, response: str) -> str:
        """
        从 LLM 响应中提取 Python 代码
        
        Args:
            response: LLM 的响应文本
            
        Returns:
            str: 提取的 Python 代码
        """
        # 尝试从 markdown 代码块中提取
        code_block_pattern = r'```python\s*\n(.*?)```'
        match = re.search(code_block_pattern, response, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # 如果没有代码块，尝试提取整个响应
        # 查找 def factor 开始的代码
        factor_pattern = r'(def factor\(.*\n(?:.*\n)*?return .*)'
        match = re.search(factor_pattern, response, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # 如果都找不到，返回整个响应
        logger.warning("无法从响应中提取因子代码，返回完整响应")
        return response.strip()
    
    def _validate_factor(self, factor_code: str) -> Dict[str, Any]:
        """
        验证因子代码
        
        Args:
            factor_code: 因子代码
            
        Returns:
            dict: 验证结果
        """
        if self.validator is None:
            # 如果没有验证器，进行基本验证
            return self._basic_validation(factor_code)
        
        return self.validator.validate(factor_code)
    
    def _basic_validation(self, factor_code: str) -> Dict[str, Any]:
        """
        基本验证（当没有验证器时使用）
        
        Args:
            factor_code: 因子代码
            
        Returns:
            dict: 验证结果
        """
        errors = []
        warnings = []
        
        # 检查是否包含 factor 函数定义
        if 'def factor(' not in factor_code:
            errors.append("代码中未找到 factor 函数定义")
        
        # 检查是否有 return 语句
        if 'return ' not in factor_code:
            errors.append("代码中未找到 return 语句")
        
        # 检查是否有基本的 DataFrame 操作
        if 'df[' not in factor_code and 'df.' not in factor_code:
            warnings.append("代码中未发现 DataFrame 操作")
        
        # 检查是否有未来数据使用
        future_data_patterns = ['shift(-', 'iloc[1:]', 'lead(']
        for pattern in future_data_patterns:
            if pattern in factor_code:
                errors.append(f"代码可能使用了未来数据: {pattern}")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _refine_factor(self, factor_code: str, errors: List[str]) -> str:
        """
        修正因子代码
        
        Args:
            factor_code: 原始因子代码
            errors: 验证错误列表
            
        Returns:
            str: 修正后的因子代码
        """
        if self.llm_client is None:
            logger.warning("LLM 客户端未初始化，无法修正因子代码")
            return factor_code
        
        refine_prompt = f"""因子代码存在以下问题，请修正：

## 问题
{chr(10).join(f'- {error}' for error in errors)}

## 原始代码
```python
{factor_code}
```

## 要求
1. 修正所有问题
2. 保持因子的核心逻辑
3. 确保代码可执行
4. 输出修正后的完整代码

请输出修正后的代码：
"""
        
        refined_code = self.llm_client.generate(refine_prompt)
        refined_code = self._extract_code_from_response(refined_code)
        
        return refined_code
    
    def _extract_metadata(self, factor_code: str, market_context: str, research_report: str = None) -> Dict[str, Any]:
        """
        提取因子元数据
        
        Args:
            factor_code: 因子代码
            market_context: 市场上下文
            research_report: 研报内容
            
        Returns:
            dict: 因子元数据
        """
        metadata = {
            'name': '未命名因子',
            'description': '',
            'logic': '',
            'source': 'research_report' if research_report else 'market_context',
            'created_at': self._get_current_timestamp()
        }
        
        # 尝试从 docstring 中提取信息
        docstring_pattern = r'"""(.*?)"""'
        match = re.search(docstring_pattern, factor_code, re.DOTALL)
        
        if match:
            docstring = match.group(1).strip()
            
            # 提取因子名称
            name_match = re.search(r'因子名称[：:]\s*(.+)', docstring)
            if name_match:
                metadata['name'] = name_match.group(1).strip()
            
            # 提取因子描述
            desc_match = re.search(r'因子描述[：:]\s*(.+)', docstring)
            if desc_match:
                metadata['description'] = desc_match.group(1).strip()
            
            # 提取逻辑
            logic_match = re.search(r'逻辑[：:]\s*(.+)', docstring)
            if logic_match:
                metadata['logic'] = logic_match.group(1).strip()
        
        return metadata
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _load_factor_knowledge(self) -> Dict[str, Any]:
        """
        加载因子知识库
        
        Returns:
            dict: 因子知识库
        """
        if self.knowledge_base_path.exists():
            try:
                with open(self.knowledge_base_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载因子知识库失败: {e}")
        
        # 返回默认结构
        return {
            'factors': [],
            'metadata': {
                'version': '1.0',
                'total_factors': 0,
                'last_updated': self._get_current_timestamp()
            }
        }
    
    def save_factor_to_knowledge_base(self, factor_result: FactorResult) -> bool:
        """
        将因子保存到知识库
        
        Args:
            factor_result: 因子生成结果
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 构建因子记录
            factor_record = {
                'id': f"factor_{len(self.factor_knowledge['factors']) + 1:03d}",
                'name': factor_result.metadata.get('name', '未命名因子'),
                'code': factor_result.code,
                'description': factor_result.metadata.get('description', ''),
                'logic': factor_result.metadata.get('logic', ''),
                'source': factor_result.source,
                'performance': {},  # 需要后续计算
                'regime_effectiveness': {},  # 需要后续计算
                'created_at': factor_result.metadata.get('created_at', self._get_current_timestamp()),
                'last_updated': self._get_current_timestamp()
            }
            
            # 添加到知识库
            self.factor_knowledge['factors'].append(factor_record)
            self.factor_knowledge['metadata']['total_factors'] = len(self.factor_knowledge['factors'])
            self.factor_knowledge['metadata']['last_updated'] = self._get_current_timestamp()
            
            # 保存到文件
            self._save_factor_knowledge()
            
            logger.info(f"因子已保存到知识库: {factor_record['id']}")
            return True
            
        except Exception as e:
            logger.error(f"保存因子到知识库失败: {e}")
            return False
    
    def _save_factor_knowledge(self):
        """保存因子知识库到文件"""
        try:
            # 确保目录存在
            self.knowledge_base_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.knowledge_base_path, 'w', encoding='utf-8') as f:
                json.dump(self.factor_knowledge, f, ensure_ascii=False, indent=2)
            
            logger.info(f"因子知识库已保存到: {self.knowledge_base_path}")
            
        except Exception as e:
            logger.error(f"保存因子知识库失败: {e}")
    
    def get_factors_from_knowledge_base(self, regime: str = None) -> List[Dict[str, Any]]:
        """
        从知识库中获取因子
        
        Args:
            regime: 市场状态，可选
            
        Returns:
            list: 因子列表
        """
        factors = self.factor_knowledge.get('factors', [])
        
        if regime:
            # 根据市场状态筛选因子
            filtered_factors = []
            for factor in factors:
                regime_effectiveness = factor.get('regime_effectiveness', {})
                if regime in regime_effectiveness and regime_effectiveness[regime] > 0.5:
                    filtered_factors.append(factor)
            return filtered_factors
        
        return factors


class FactorValidator:
    """
    因子验证器
    
    验证因子代码的质量和有效性
    """
    
    def __init__(self):
        """初始化因子验证器"""
        logger.info("FactorValidator 初始化完成")
    
    def validate(self, factor_code: str) -> Dict[str, Any]:
        """
        验证因子代码
        
        Args:
            factor_code: 因子代码
            
        Returns:
            dict: 验证结果
        """
        errors = []
        warnings = []
        
        # 1. 语法检查
        syntax_result = self._check_syntax(factor_code)
        if not syntax_result['is_valid']:
            errors.extend(syntax_result['errors'])
        
        # 2. 结构检查
        structure_result = self._check_structure(factor_code)
        if not structure_result['is_valid']:
            errors.extend(structure_result['errors'])
        warnings.extend(structure_result.get('warnings', []))
        
        # 3. 未来数据检查
        future_data_result = self._check_future_data(factor_code)
        if not future_data_result['is_valid']:
            errors.extend(future_data_result['errors'])
        
        # 4. 最佳实践检查
        best_practices_result = self._check_best_practices(factor_code)
        warnings.extend(best_practices_result.get('warnings', []))
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _check_syntax(self, factor_code: str) -> Dict[str, Any]:
        """
        检查代码语法
        
        Args:
            factor_code: 因子代码
            
        Returns:
            dict: 检查结果
        """
        errors = []
        
        try:
            compile(factor_code, '<string>', 'exec')
        except SyntaxError as e:
            errors.append(f"语法错误: {e}")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }
    
    def _check_structure(self, factor_code: str) -> Dict[str, Any]:
        """
        检查代码结构
        
        Args:
            factor_code: 因子代码
            
        Returns:
            dict: 检查结果
        """
        errors = []
        warnings = []
        
        # 检查是否包含 factor 函数定义
        if 'def factor(' not in factor_code:
            errors.append("代码中未找到 factor 函数定义")
        
        # 检查是否有 return 语句
        if 'return ' not in factor_code:
            errors.append("代码中未找到 return 语句")
        
        # 检查是否有 docstring
        if '"""' not in factor_code and "'''" not in factor_code:
            warnings.append("建议添加 docstring 描述因子逻辑")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _check_future_data(self, factor_code: str) -> Dict[str, Any]:
        """
        检查是否使用未来数据
        
        Args:
            factor_code: 因子代码
            
        Returns:
            dict: 检查结果
        """
        errors = []
        
        # 检查是否使用了 shift(-n) 或其他未来数据模式
        future_data_patterns = [
            (r'shift\(-\d+\)', '使用了 shift(-n)，可能是未来数据'),
            (r'iloc\[\d+:\]', '使用了 iloc[n:]，可能是未来数据'),
            (r'lead\(', '使用了 lead()，可能是未来数据'),
        ]
        
        for pattern, message in future_data_patterns:
            if re.search(pattern, factor_code):
                errors.append(f"代码可能使用了未来数据: {message}")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }
    
    def _check_best_practices(self, factor_code: str) -> Dict[str, Any]:
        """
        检查最佳实践
        
        Args:
            factor_code: 因子代码
            
        Returns:
            dict: 检查结果
        """
        warnings = []
        
        # 检查是否有 NaN 处理
        if 'dropna()' not in factor_code and 'fillna(' not in factor_code:
            warnings.append("建议添加 NaN 值处理")
        
        # 检查是否有异常值处理
        if 'clip(' not in factor_code and 'winsorize' not in factor_code:
            warnings.append("建议添加异常值处理")
        
        return {
            'warnings': warnings
        }
    
    def calculate_performance_metrics(self, factor_func, data: pd.DataFrame) -> Dict[str, float]:
        """
        计算因子性能指标
        
        Args:
            factor_func: 因子函数
            data: 历史数据
            
        Returns:
            dict: 性能指标
        """
        try:
            import pandas as pd
            import numpy as np
            
            # 计算因子值
            factor_values = factor_func(data)
            
            # 计算收益率（假设使用下一期收益率）
            returns = data['close'].pct_change().shift(-1)
            
            # 对齐数据
            aligned_data = pd.DataFrame({
                'factor': factor_values,
                'returns': returns
            }).dropna()
            
            if len(aligned_data) < 10:
                return {'error': '数据不足'}
            
            # 计算 IC (Information Coefficient)
            ic = aligned_data['factor'].corr(aligned_data['returns'])
            
            # 计算 ICIR (Information Coefficient Information Ratio)
            # 滚动计算 IC
            rolling_ic = aligned_data['factor'].rolling(20).corr(aligned_data['returns'])
            icir = rolling_ic.mean() / rolling_ic.std() if rolling_ic.std() > 0 else 0
            
            # 计算稳定性
            stability = 1 - (rolling_ic.std() / abs(rolling_ic.mean())) if abs(rolling_ic.mean()) > 0 else 0
            
            return {
                'ic': float(ic),
                'icir': float(icir),
                'stability': float(stability),
                'sample_count': len(aligned_data)
            }
            
        except Exception as e:
            logger.error(f"计算因子性能指标失败: {e}")
            return {'error': str(e)}


class FactorKnowledgeManager:
    """
    因子知识管理器
    
    管理因子知识库，支持因子的增删改查
    """
    
    def __init__(self, knowledge_base_path: str = "data/factor_knowledge.json"):
        """
        初始化因子知识管理器
        
        Args:
            knowledge_base_path: 因子知识库路径
        """
        self.knowledge_base_path = Path(knowledge_base_path)
        self.knowledge_base = self._load_knowledge_base()
        
        logger.info("FactorKnowledgeManager 初始化完成")
    
    def _load_knowledge_base(self) -> Dict[str, Any]:
        """
        加载知识库
        
        Returns:
            dict: 知识库
        """
        if self.knowledge_base_path.exists():
            try:
                with open(self.knowledge_base_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载知识库失败: {e}")
        
        # 返回默认结构
        return {
            'factors': [],
            'metadata': {
                'version': '1.0',
                'total_factors': 0,
                'last_updated': self._get_current_timestamp()
            }
        }
    
    def _save_knowledge_base(self):
        """保存知识库到文件"""
        try:
            self.knowledge_base_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.knowledge_base_path, 'w', encoding='utf-8') as f:
                json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)
            
            logger.info(f"知识库已保存到: {self.knowledge_base_path}")
            
        except Exception as e:
            logger.error(f"保存知识库失败: {e}")
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def add_factor(self, factor_result: FactorResult) -> str:
        """
        添加因子到知识库
        
        Args:
            factor_result: 因子生成结果
            
        Returns:
            str: 因子 ID
        """
        factor_id = f"factor_{len(self.knowledge_base['factors']) + 1:03d}"
        
        factor_record = {
            'id': factor_id,
            'name': factor_result.metadata.get('name', '未命名因子'),
            'code': factor_result.code,
            'description': factor_result.metadata.get('description', ''),
            'logic': factor_result.metadata.get('logic', ''),
            'source': factor_result.source,
            'performance': {},
            'regime_effectiveness': {},
            'created_at': factor_result.metadata.get('created_at', self._get_current_timestamp()),
            'last_updated': self._get_current_timestamp()
        }
        
        self.knowledge_base['factors'].append(factor_record)
        self.knowledge_base['metadata']['total_factors'] = len(self.knowledge_base['factors'])
        self.knowledge_base['metadata']['last_updated'] = self._get_current_timestamp()
        
        self._save_knowledge_base()
        
        logger.info(f"因子已添加到知识库: {factor_id}")
        return factor_id
    
    def get_factor(self, factor_id: str) -> Optional[Dict[str, Any]]:
        """
        获取因子
        
        Args:
            factor_id: 因子 ID
            
        Returns:
            dict: 因子记录
        """
        for factor in self.knowledge_base['factors']:
            if factor['id'] == factor_id:
                return factor
        return None
    
    def get_all_factors(self) -> List[Dict[str, Any]]:
        """
        获取所有因子
        
        Returns:
            list: 因子列表
        """
        return self.knowledge_base['factors']
    
    def get_factors_by_regime(self, regime: str) -> List[Dict[str, Any]]:
        """
        根据市场状态获取因子
        
        Args:
            regime: 市场状态
            
        Returns:
            list: 因子列表
        """
        filtered_factors = []
        for factor in self.knowledge_base['factors']:
            regime_effectiveness = factor.get('regime_effectiveness', {})
            if regime in regime_effectiveness and regime_effectiveness[regime] > 0.5:
                filtered_factors.append(factor)
        return filtered_factors
    
    def update_factor_performance(self, factor_id: str, performance: Dict[str, float]) -> bool:
        """
        更新因子性能指标
        
        Args:
            factor_id: 因子 ID
            performance: 性能指标
            
        Returns:
            bool: 是否更新成功
        """
        for factor in self.knowledge_base['factors']:
            if factor['id'] == factor_id:
                factor['performance'] = performance
                factor['last_updated'] = self._get_current_timestamp()
                self._save_knowledge_base()
                logger.info(f"因子性能指标已更新: {factor_id}")
                return True
        
        logger.warning(f"未找到因子: {factor_id}")
        return False
    
    def delete_factor(self, factor_id: str) -> bool:
        """
        删除因子
        
        Args:
            factor_id: 因子 ID
            
        Returns:
            bool: 是否删除成功
        """
        for i, factor in enumerate(self.knowledge_base['factors']):
            if factor['id'] == factor_id:
                del self.knowledge_base['factors'][i]
                self.knowledge_base['metadata']['total_factors'] = len(self.knowledge_base['factors'])
                self.knowledge_base['metadata']['last_updated'] = self._get_current_timestamp()
                self._save_knowledge_base()
                logger.info(f"因子已删除: {factor_id}")
                return True
        
        logger.warning(f"未找到因子: {factor_id}")
        return False


# 示例用法
if __name__ == "__main__":
    # 这里可以添加测试代码
    pass
