"""
多因子组合模型

将多个单因子的截面预测值组合为综合信号。
基于 LightGBM 梯度提升树实现非线性因子组合。

核心思想：
- 单因子 ICIR 普遍 < 0.5，预测力弱
- 多因子组合可以捕捉因子间的非线性交互
- LightGBM 自动学习因子权重和交互模式

版本：v1.0
创建日期：2026-06-16
"""

import json
import logging
import os
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ModelResult:
    """模型训练结果"""
    model_name: str
    feature_importance: Dict[str, float]
    train_ic: float
    train_icir: float
    oos_ic: float           # 样本外 IC
    oos_icir: float         # 样本外 ICIR
    oos_sharpe: float       # 样本外多空 Sharpe
    n_features: int
    n_train_days: int
    n_oos_days: int

    def to_dict(self) -> Dict:
        return {
            'model_name': self.model_name,
            'feature_importance': self.feature_importance,
            'train_ic': self.train_ic,
            'train_icir': self.train_icir,
            'oos_ic': self.oos_ic,
            'oos_icir': self.oos_icir,
            'oos_sharpe': self.oos_sharpe,
            'n_features': self.n_features,
            'n_train_days': self.n_train_days,
            'n_oos_days': self.n_oos_days,
        }


class MultiFactorModel:
    """
    多因子组合模型

    使用 LightGBM 将多个因子的截面预测值组合为综合信号。

    使用方式：
        model = MultiFactorModel()

        # 准备因子值矩阵
        factor_data = {
            'momentum_20d': factor_values_1,  # DataFrame, index=date, columns=symbol
            'rsi_14d': factor_values_2,
            'volatility_20d': factor_values_3,
        }

        # 训练模型
        result = model.train(factor_data, returns)

        # 预测
        signal = model.predict(new_factor_data)
    """

    def __init__(self, model_type: str = 'lightgbm', **model_params):
        """
        初始化模型

        Args:
            model_type: 模型类型 ('lightgbm', 'ridge', 'equal_weight')
            **model_params: 模型参数
        """
        self.model_type = model_type
        self.model_params = model_params
        self.model = None
        self.feature_names: List[str] = []
        self._trained = False

    def train(self, factor_data: Dict[str, pd.DataFrame],
              returns: pd.DataFrame,
              train_ratio: float = 0.7) -> ModelResult:
        """
        训练多因子组合模型

        Args:
            factor_data: {factor_name: DataFrame(index=date, columns=symbol)}
            returns: DataFrame(index=date, columns=symbol)，次日收益率
            train_ratio: 训练集比例

        Returns:
            ModelResult
        """
        # 1. 构建特征矩阵
        X, y, dates = self._build_feature_matrix(factor_data, returns)

        if X is None or len(X) < 30:
            logger.warning("数据不足，无法训练模型")
            return self._empty_result()

        # 2. 训练/测试集分割（时间序列分割，不打乱）
        split_idx = int(len(X) * train_ratio)
        X_train, X_oos = X[:split_idx], X[split_idx:]
        y_train, y_oos = y[:split_idx], y[split_idx:]
        dates_train, dates_oos = dates[:split_idx], dates[split_idx:]

        # 3. 训练模型
        self._train_model(X_train, y_train)

        # 4. 评估
        train_pred = self._predict_raw(X_train)
        oos_pred = self._predict_raw(X_oos)

        train_ic = self._compute_ic_series(train_pred, y_train)
        oos_ic = self._compute_ic_series(oos_pred, y_oos)

        # 5. 特征重要性
        importance = self._get_feature_importance()

        result = ModelResult(
            model_name=self.model_type,
            feature_importance=importance,
            train_ic=float(train_ic.mean()) if len(train_ic) > 0 else 0,
            train_icir=float(train_ic.mean() / train_ic.std()) if len(train_ic) > 0 and train_ic.std() > 0 else 0,
            oos_ic=float(oos_ic.mean()) if len(oos_ic) > 0 else 0,
            oos_icir=float(oos_ic.mean() / oos_ic.std()) if len(oos_ic) > 0 and oos_ic.std() > 0 else 0,
            oos_sharpe=self._compute_long_short_sharpe(oos_pred, y_oos),
            n_features=X.shape[1],
            n_train_days=len(X_train),
            n_oos_days=len(X_oos),
        )

        self._trained = True
        logger.info(
            f"模型训练完成: OOS ICIR={result.oos_icir:.2f}, "
            f"OOS Sharpe={result.oos_sharpe:.2f}, "
            f"特征数={result.n_features}"
        )

        return result

    def predict(self, factor_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        用训练好的模型预测综合信号

        Args:
            factor_data: {factor_name: DataFrame(index=date, columns=symbol)}

        Returns:
            DataFrame(index=date, columns=symbol)，综合信号值
        """
        if not self._trained:
            logger.error("模型未训练")
            return pd.DataFrame()

        # 构建特征矩阵（不需要 returns）
        X, _, dates = self._build_feature_matrix(factor_data, returns=None)

        if X is None or len(X) == 0:
            logger.warning("预测数据为空")
            return pd.DataFrame()

        # 预测
        pred = self._predict_raw(X)

        # 重塑为 DataFrame
        symbols = sorted(list(factor_data.values())[0].columns)
        n_symbols = len(symbols)
        n_dates = len(X) // n_symbols

        if n_dates == 0:
            return pd.DataFrame()

        result = pd.DataFrame(
            pred[:n_dates * n_symbols].reshape(n_dates, n_symbols),
            index=dates[:n_dates],
            columns=symbols
        )

        return result

    def _build_feature_matrix(self, factor_data: Dict[str, pd.DataFrame],
                               returns: pd.DataFrame = None) -> Tuple:
        """
        构建特征矩阵

        Args:
            factor_data: {factor_name: DataFrame(index=date, columns=symbol)}
            returns: 收益率矩阵

        Returns:
            (X, y, dates) 或 (X, None, dates)
        """
        if not factor_data:
            return None, None, None

        self.feature_names = sorted(factor_data.keys())

        # 找到所有因子共有的日期
        common_dates = None
        for name, df in factor_data.items():
            if common_dates is None:
                common_dates = set(df.index)
            else:
                common_dates &= set(df.index)

        if common_dates is None or len(common_dates) < 30:
            return None, None, None

        common_dates = sorted(common_dates)

        # 构建展平的特征矩阵
        X_rows = []
        y_rows = []
        date_rows = []

        for date in common_dates:
            # 获取每个品种在该日的所有因子值
            for symbol in list(factor_data.values())[0].columns:
                features = []
                valid = True
                for name in self.feature_names:
                    df = factor_data[name]
                    if date in df.index and symbol in df.columns:
                        val = df.loc[date, symbol]
                        if pd.isna(val) or np.isinf(val):
                            valid = False
                            break
                        features.append(val)
                    else:
                        valid = False
                        break

                if valid:
                    X_rows.append(features)
                    date_rows.append(date)

                    if returns is not None and date in returns.index and symbol in returns.columns:
                        y_rows.append(returns.loc[date, symbol])
                    else:
                        y_rows.append(np.nan)

        if not X_rows:
            return None, None, None

        X = np.array(X_rows)
        y = np.array(y_rows) if y_rows and returns is not None else None

        # 处理 NaN 收益率（仅在有 returns 时过滤）
        if y is not None and len(y) > 0:
            valid_mask = ~np.isnan(y)
            if valid_mask.any():
                X = X[valid_mask]
                y = y[valid_mask]
                date_rows = [d for d, v in zip(date_rows, valid_mask) if v]

        return X, y, date_rows

    def _train_model(self, X: np.ndarray, y: np.ndarray):
        """训练模型"""
        if self.model_type == 'lightgbm':
            import lightgbm as lgb

            default_params = {
                'n_estimators': 100,
                'max_depth': 4,
                'learning_rate': 0.05,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'reg_lambda': 0.1,
                'min_child_samples': 10,
                'verbose': -1,
                'random_state': 42,
            }
            default_params.update(self.model_params)

            self.model = lgb.LGBMRegressor(**default_params)
            self.model.fit(X, y)

        elif self.model_type == 'ridge':
            from sklearn.linear_model import Ridge
            alpha = self.model_params.get('alpha', 1.0)
            self.model = Ridge(alpha=alpha)
            self.model.fit(X, y)

        elif self.model_type == 'equal_weight':
            # 等权模型，不需要训练
            self.model = None

        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

    def _predict_raw(self, X: np.ndarray) -> np.ndarray:
        """原始预测"""
        if self.model_type == 'equal_weight':
            return X.mean(axis=1)
        elif self.model is not None:
            return self.model.predict(X)
        else:
            return X.mean(axis=1)

    def _get_feature_importance(self) -> Dict[str, float]:
        """获取特征重要性"""
        if self.model_type == 'lightgbm' and self.model is not None:
            importance = self.model.feature_importances_
            total = importance.sum()
            if total > 0:
                return {
                    name: float(imp / total)
                    for name, imp in zip(self.feature_names, importance)
                }
        elif self.model_type == 'ridge' and self.model is not None:
            coef = np.abs(self.model.coef_)
            total = coef.sum()
            if total > 0:
                return {
                    name: float(c / total)
                    for name, c in zip(self.feature_names, coef)
                }

        # 等权
        n = len(self.feature_names)
        return {name: 1.0 / n for name in self.feature_names} if n > 0 else {}

    def _compute_ic_series(self, pred: np.ndarray, y: np.ndarray) -> pd.Series:
        """计算 IC 序列（按日期分组）"""
        from scipy import stats

        # 简化：计算整体 IC
        if len(pred) < 10:
            return pd.Series(dtype=float)

        # 按日期分组计算 IC
        # 这里 pred 和 y 已经展平了，需要按日期重新分组
        # 简化处理：计算整体 Spearman 相关
        if np.std(pred) == 0 or np.std(y) == 0:
            return pd.Series([0.0])

        corr, _ = stats.spearmanr(pred, y)
        return pd.Series([corr])

    def _compute_long_short_sharpe(self, pred: np.ndarray, y: np.ndarray,
                                    quantile: float = 0.2) -> float:
        """计算多空 Sharpe"""
        if len(pred) < 20:
            return 0.0

        n = len(pred)
        top_n = max(1, int(n * quantile))
        bottom_n = max(1, int(n * quantile))

        # 按预测值排序
        sorted_idx = np.argsort(pred)
        short_idx = sorted_idx[:bottom_n]
        long_idx = sorted_idx[-top_n:]

        long_ret = y[long_idx].mean()
        short_ret = y[short_idx].mean()
        ls_ret = long_ret - short_ret

        # 简化：返回单期多空收益
        return float(ls_ret / (np.std(y) + 1e-10))

    def _empty_result(self) -> ModelResult:
        """返回空结果"""
        return ModelResult(
            model_name=self.model_type,
            feature_importance={},
            train_ic=0, train_icir=0,
            oos_ic=0, oos_icir=0, oos_sharpe=0,
            n_features=0, n_train_days=0, n_oos_days=0,
        )

    def save_model(self, path: str = None):
        """保存模型"""
        if path is None:
            path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'data', 'multi_factor_model.json'
            )

        data = {
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'trained': self._trained,
            'feature_importance': self._get_feature_importance(),
        }

        # 保存 LightGBM 模型
        if self.model_type == 'lightgbm' and self.model is not None:
            model_path = path.replace('.json', '.lgb')
            self.model.booster_.save_model(model_path)
            data['model_file'] = os.path.basename(model_path)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"模型已保存到 {path}")

    def load_model(self, path: str = None):
        """加载模型"""
        if path is None:
            path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'data', 'multi_factor_model.json'
            )

        if not os.path.exists(path):
            logger.error(f"模型文件不存在: {path}")
            return

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.model_type = data.get('model_type', 'lightgbm')
        self.feature_names = data.get('feature_names', [])
        self._trained = data.get('trained', False)

        # 加载 LightGBM 模型
        if self.model_type == 'lightgbm' and 'model_file' in data:
            import lightgbm as lgb
            model_path = os.path.join(os.path.dirname(path), data['model_file'])
            if os.path.exists(model_path):
                self.model = lgb.Booster(model_file=model_path)

        logger.info(f"模型已加载: {self.model_type}, 特征数={len(self.feature_names)}")


def generate_report(result: ModelResult) -> str:
    """生成模型评估报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("多因子组合模型评估报告")
    lines.append("=" * 60)
    lines.append(f"模型类型: {result.model_name}")
    lines.append(f"特征数量: {result.n_features}")
    lines.append(f"训练天数: {result.n_train_days}")
    lines.append(f"测试天数: {result.n_oos_days}")
    lines.append("")
    lines.append("--- 训练集 ---")
    lines.append(f"  IC: {result.train_ic:.4f}")
    lines.append(f"  ICIR: {result.train_icir:.2f}")
    lines.append("")
    lines.append("--- 样本外 ---")
    lines.append(f"  IC: {result.oos_ic:.4f}")
    lines.append(f"  ICIR: {result.oos_icir:.2f}")
    lines.append(f"  多空 Sharpe: {result.oos_sharpe:.2f}")
    lines.append("")
    lines.append("--- 特征重要性 ---")
    for name, imp in sorted(result.feature_importance.items(), key=lambda x: -x[1]):
        bar = "#" * int(imp * 40)
        lines.append(f"  {name:25s} {imp:.3f} {bar}")
    lines.append("=" * 60)
    return '\n'.join(lines)
