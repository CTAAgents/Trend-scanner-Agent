"""
期货交易 Gym 环境

提供标准化的期货交易环境，支持：
1. Gymnasium 兼容接口
2. 多品种并行（VecEnv）
3. 真实的交易成本建模
4. 灵活的状态/奖励函数配置

版本：v1.0
创建日期：2026-06-17
"""

import gymnasium as gym
import numpy as np
from typing import Tuple, Dict, Any, Optional, List
from dataclasses import dataclass

from ..trend_scanner_config import RLConfig


@dataclass
class TradeCost:
    """交易成本"""
    commission_rate: float = 0.00012  # 手续费率（万1.2）
    slippage_points: float = 1.0      # 滑点（点）
    margin_rate: float = 0.10         # 保证金率（10%）


class FuturesTradingEnv(gym.Env):
    """
    期货交易 Gym 环境
    
    状态空间：
    - 技术指标（由 rl_interface_designer 设计）
    - 当前持仓状态
    
    动作空间：
    - [-1, 1] 表示仓位方向和大小
    - -1: 满仓做空
    - 0: 空仓
    - 1: 满仓做多
    
    奖励函数：
    - 基于持仓收益
    - 扣除交易成本
    - 可配置的风险调整
    """
    
    metadata = {'render_modes': ['human', 'log']}
    
    def __init__(self,
                 data: np.ndarray,
                 state_dim: int = 10,
                 trade_cost: Optional[TradeCost] = None,
                 rl_config: Optional[RLConfig] = None,
                 render_mode: Optional[str] = None):
        """
        初始化环境
        
        Args:
            data: K线数据，shape=(n_steps, n_features)
                  特征顺序: [open, high, low, close, volume, ...]
            state_dim: 状态维度（技术指标数量）
            trade_cost: 交易成本配置
            rl_config: RL 配置
            render_mode: 渲染模式
        """
        super().__init__()
        
        self.data = data
        self.n_steps = len(data)
        self.state_dim = state_dim
        self.trade_cost = trade_cost or TradeCost()
        self.render_mode = render_mode
        
        # 状态空间：技术指标 + 持仓状态 + 收益率
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(state_dim + 2,),  # +2 for position and unrealized_pnl
            dtype=np.float32
        )
        
        # 动作空间：[-1, 1] 表示仓位方向和大小
        self.action_space = gym.spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(1,),
            dtype=np.float32
        )
        
        # 状态变量
        self.current_step = 0
        self.position = 0.0  # 当前仓位 [-1, 1]
        self.entry_price = 0.0
        self.total_reward = 0.0
        self.peak_reward = 0.0  # 历史最高收益（用于计算回撤）
        self.holding_steps = 0  # 当前持仓步数
        self.trades = []
        
        # 技术指标缓存（需要外部填充）
        self.indicators = None
    
    def set_indicators(self, indicators: np.ndarray):
        """
        设置技术指标
        
        Args:
            indicators: 技术指标数组，shape=(n_steps, state_dim)
        """
        assert len(indicators) == self.n_steps, "技术指标长度必须与数据长度一致"
        self.indicators = indicators
    
    def reset(self, 
              seed: Optional[int] = None,
              options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        """
        重置环境
        
        Returns:
            (初始状态, 信息字典)
        """
        super().reset(seed=seed)
        
        # 随机选择起始点（避免从头开始）
        if options and 'start_step' in options:
            self.current_step = options['start_step']
        else:
            # 确保至少有 10 步可用于训练
            max_start = max(0, self.n_steps - 10)
            self.current_step = self.np_random.integers(0, max(1, max_start))
        
        self.position = 0.0
        self.entry_price = 0.0
        self.total_reward = 0.0
        self.peak_reward = 0.0
        self.holding_steps = 0
        self.trades = []
        
        return self._get_observation(), self._get_info()
    
    def step(self, action: float) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        执行一步
        
        Args:
            action: 目标仓位 [-1, 1]
        
        Returns:
            (next_state, reward, terminated, truncated, info)
        """
        # 裁剪动作到有效范围
        if isinstance(action, np.ndarray):
            target_position = np.clip(float(action.item()), -1.0, 1.0)
        else:
            target_position = np.clip(float(action), -1.0, 1.0)
        
        # 获取当前价格
        current_price = self.data[self.current_step, 3]  # close price
        
        # 计算交易成本
        position_change = abs(target_position - self.position)
        commission = position_change * self.trade_cost.commission_rate * current_price
        slippage = position_change * self.trade_cost.slippage_points
        total_cost = commission + slippage
        
        # 更新持仓
        old_position = self.position
        self.position = target_position
        
        # 如果开仓，记录入场价格
        if old_position == 0 and target_position != 0:
            self.entry_price = current_price
        # 如果平仓，记录交易
        elif old_position != 0 and target_position == 0:
            self.trades.append({
                'entry_price': self.entry_price,
                'exit_price': current_price,
                'position': old_position,
                'pnl': old_position * (current_price - self.entry_price) / self.entry_price
            })
        
        # 移动到下一步
        self.current_step += 1
        
        # 计算收益
        if self.current_step < self.n_steps:
            next_price = self.data[self.current_step, 3]
            
            # 持仓收益
            if self.position != 0:
                price_return = (next_price - current_price) / current_price
                position_return = self.position * price_return
            else:
                position_return = 0.0
            
            # 基础收益 = 持仓收益 - 交易成本
            base_reward = position_return - total_cost / current_price
            
            # 确保 base_reward 是有效数值
            if np.isnan(base_reward) or np.isinf(base_reward):
                base_reward = 0.0
            
            # 风险调整：最大回撤惩罚
            self.total_reward += base_reward
            peak_reward = max(self.peak_reward, self.total_reward)
            
            # 计算回撤（避免除零）
            if abs(peak_reward) > 1e-8:
                current_drawdown = (peak_reward - self.total_reward) / abs(peak_reward)
            else:
                current_drawdown = 0.0
            
            # 确保 current_drawdown 是有效数值
            if np.isnan(current_drawdown) or np.isinf(current_drawdown):
                current_drawdown = 0.0
            
            self.peak_reward = peak_reward
            
            # 最大回撤惩罚（回撤超过 10% 开始惩罚，更宽松）
            drawdown_penalty = 0.0
            if current_drawdown > 0.10:
                drawdown_penalty = -0.005 * (current_drawdown - 0.10)  # 降低惩罚力度
            
            # 持仓时间惩罚（鼓励及时平仓）
            holding_penalty = 0.0
            if self.position != 0:
                self.holding_steps += 1
                if self.holding_steps > 20:  # 持仓超过 20 步开始惩罚（更宽松）
                    holding_penalty = -0.0005 * (self.holding_steps - 20)  # 降低惩罚力度
            else:
                self.holding_steps = 0
            
            # 总收益 = 基础收益 + 回撤惩罚 + 持仓惩罚
            reward = base_reward + drawdown_penalty + holding_penalty
        else:
            # 最后一步，强制平仓
            reward = -total_cost / current_price if self.position != 0 else 0.0
            self.position = 0.0
        
        self.total_reward += reward
        
        # 检查是否结束
        terminated = self.current_step >= self.n_steps - 1
        truncated = False
        
        return self._get_observation(), reward, terminated, truncated, self._get_info()
    
    def _get_observation(self) -> np.ndarray:
        """获取当前观察"""
        obs = np.zeros(self.state_dim + 2, dtype=np.float32)
        
        # 技术指标
        if self.indicators is not None:
            obs[:self.state_dim] = self.indicators[self.current_step]
        
        # 持仓状态
        obs[self.state_dim] = self.position
        
        # 未实现盈亏
        if self.position != 0 and self.entry_price > 0:
            current_price = self.data[self.current_step, 3]
            unrealized_pnl = self.position * (current_price - self.entry_price) / self.entry_price
            obs[self.state_dim + 1] = unrealized_pnl
        
        return obs
    
    def _get_info(self) -> Dict[str, Any]:
        """获取信息字典"""
        return {
            'current_step': self.current_step,
            'position': self.position,
            'entry_price': self.entry_price,
            'total_reward': self.total_reward,
            'n_trades': len(self.trades),
            'current_price': self.data[self.current_step, 3] if self.current_step < self.n_steps else 0,
        }
    
    def render(self):
        """渲染环境状态"""
        if self.render_mode == 'human':
            info = self._get_info()
            print(f"Step: {info['current_step']}, "
                  f"Position: {info['position']:.2f}, "
                  f"Price: {info['current_price']:.2f}, "
                  f"Reward: {info['total_reward']:.4f}")
    
    def get_trade_summary(self) -> Dict[str, Any]:
        """获取交易摘要"""
        if not self.trades:
            return {
                'n_trades': 0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
                'total_pnl': 0.0,
            }
        
        pnls = [t['pnl'] for t in self.trades]
        wins = [p for p in pnls if p > 0]
        
        return {
            'n_trades': len(self.trades),
            'win_rate': len(wins) / len(self.trades) if self.trades else 0,
            'avg_pnl': np.mean(pnls),
            'total_pnl': sum(pnls),
            'max_win': max(pnls) if pnls else 0,
            'max_loss': min(pnls) if pnls else 0,
        }


class MultiAssetVecEnv:
    """
    多品种向量化环境
    
    借鉴 ElegantRL 的 VecEnv 设计，支持多个品种并行训练。
    """
    
    def __init__(self,
                 envs: List[FuturesTradingEnv]):
        """
        初始化向量化环境
        
        Args:
            envs: 环境列表
        """
        self.envs = envs
        self.num_envs = len(envs)
        
        # 统一状态和动作空间
        self.observation_space = envs[0].observation_space
        self.action_space = envs[0].action_space
    
    def reset(self) -> Tuple[np.ndarray, List[Dict]]:
        """
        重置所有环境
        
        Returns:
            (批量状态, 信息列表)
        """
        observations = []
        infos = []
        
        for env in self.envs:
            obs, info = env.reset()
            observations.append(obs)
            infos.append(info)
        
        return np.stack(observations), infos
    
    def step(self, actions: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[Dict]]:
        """
        在所有环境中执行动作
        
        Args:
            actions: 动作数组，shape=(num_envs,)
        
        Returns:
            (observations, rewards, terminateds, truncateds, infos)
        """
        observations = []
        rewards = []
        terminateds = []
        truncateds = []
        infos = []
        
        for i, env in enumerate(self.envs):
            obs, reward, terminated, truncated, info = env.step(actions[i])
            observations.append(obs)
            rewards.append(reward)
            terminateds.append(terminated)
            truncateds.append(truncated)
            infos.append(info)
        
        return (
            np.stack(observations),
            np.array(rewards, dtype=np.float32),
            np.array(terminateds, dtype=bool),
            np.array(truncateds, dtype=bool),
            infos,
        )
