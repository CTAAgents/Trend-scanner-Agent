# TqSdk 技术指标集成设计文档

> 版本：v1.0 | 创建日期：2026-06-17
> 状态：进行中

## 一、TqSdk 技术指标完整列表（70 个）

### 1.1 均线类（9 个）

| 指标 | 函数 | 参数 | 说明 |
|------|------|------|------|
| MA | `ta.MA(df, n)` | n=周期 | 简单移动平均 |
| EMA | `ta.EMA(df, n)` | n=周期 | 指数移动平均 |
| EMA2 | `ta.EMA2(df, n)` | n=周期 | 二阶指数移动平均 |
| SMA | `ta.SMA(df, n, m)` | n=周期, m=权重 | 加权移动平均 |
| BBI | `ta.BBI(df, n1, n2, n3, n4)` | 3,6,12,24 | 多空指标：MA3+MA6+MA12+MA24)/4 |
| DMA | `ta.DMA(df, n1, n2)` | 10,50 | 平行线差：MA(n1)-MA(n2) |
| EXPMA | `ta.EXPMA(df, n1, n2)` | 12,50 | 指数平均数 |
| TRMA | `ta.TRMA(df, n)` | n=周期 | 三角移动平均 |
| DKX | `ta.DKX(df, n)` | n=周期 | 多空线 |

### 1.2 趋势类（6 个）

| 指标 | 函数 | 参数 | 说明 |
|------|------|------|------|
| DMI | `ta.DMI(df, n, m)` | 14,6 | 趋向指标：PDI/MDI/ADX/ADXR |
| SAR | `ta.SAR(df, n, step, maxp)` | 4,0.02,0.2 | 抛物线转向 |
| ENV | `ta.ENV(df, n, k)` | 14,6% | 邮 envelope：MA±k% |
| MIKE | `ta.MIKE(df, n)` | n=周期 | 麦克指标 |
| PUBU | `ta.PUBU(df, n)` | n=周期 | 瀑布线 |
| QHLSR | `ta.QHLSR(df, n)` | n=周期 | 强弱量值 |

### 1.3 震荡类（12 个）

| 指标 | 函数 | 参数 | 说明 |
|------|------|------|------|
| RSI | `ta.RSI(df, n)` | 14 | 相对强弱 |
| KDJ | `ta.KDJ(df, n, m1, m2)` | 9,3,3 | 随机指标 |
| KD | `ta.KD(df, n, m1, m2)` | 9,3,3 | 随机指标（无J值） |
| WR | `ta.WR(df, n)` | 14 | 威廉指标 |
| CCI | `ta.CCI(df, n)` | 14 | 商品通道指数 |
| BIAS | `ta.BIAS(df, n)` | 12 | 乖离率 |
| PSY | `ta.PSY(df, n)` | 12 | 心理线 |
| LWR | `ta.LWR(df, n1, n2)` | 14,6 | LWR 指标 |
| SLOWKD | `ta.SLOWKD(df, n1, n2, n3, n4)` | 9,3,3,3 | 慢速 KD |
| VRSI | `ta.VRSI(df, n)` | 14 | 量相对强弱 |
| DPO | `ta.DPO(df, n)` | 20 | 去趋势价格振荡器 |
| CDP | `ta.CDP(df)` | - | 逆势操作 |

### 1.4 动量类（10 个）

| 指标 | 函数 | 参数 | 说明 |
|------|------|------|------|
| MACD | `ta.MACD(df, fast, slow, signal)` | 12,26,9 | 指数平滑异同 |
| ROC | `ta.ROC(df, n, m)` | 10,1 | 变动率 |
| MTM | `ta.MTM(df, n, m)` | 12,6 | 动量指标 |
| MI | `ta.MI(df, n)` | n=周期 | MI 指标 |
| MICD | `ta.MICD(df, n1, n2, n3)` | 3,10,20 | MICD 指标 |
| DBCD | `ta.DBCD(df, n1, n2, n3)` | 10,20,5 | 异同离差乖离率 |
| SRDM | `ta.SRDM(df, n)` | n=周期 | SRDM 指标 |
| SRMI | `ta.SRMI(df, n)` | n=周期 | SRMI 指标 |
| DDI | `ta.DDI(df, n, n1)` | 13,5 | 方向标准离差 |
| ADTM | `ta.ADTM(df, n, n1)` | 23,8 | 动态买卖气 |

### 1.5 波动率类（5 个）

| 指标 | 函数 | 参数 | 说明 |
|------|------|------|------|
| ATR | `ta.ATR(df, n)` | 14 | 平均真实波幅 |
| BOLL | `ta.BOLL(df, n, k)` | 20,2 | 布林带 |
| BBIBOLL | `ta.BBIBOLL(df, n, k)` | 10,3 | BBI 布林带 |
| PRICEOSC | `ta.PRICEOSC(df, n1, n2)` | 10,20 | 价格振荡器 |
| VOSC | `ta.VOSC(df, n1, n2)` | 5,10 | 量振荡器 |

### 1.6 成交量类（18 个）

| 指标 | 函数 | 参数 | 说明 |
|------|------|------|------|
| OBV | `ta.OBV(df)` | - | 能量潮 |
| AD | `ta.AD(df)` | - | 聚散指标 |
| MFI | `ta.MFI(df, n)` | 14 | 资金流量指标 |
| VR | `ta.VR(df, n)` | 26 | 成交量比率 |
| VROC | `ta.VROC(df, n)` | 12 | 量变动率 |
| ARBR | `ta.ARBR(df, n)` | 26 | 人气意愿 |
| ASI | `ta.ASI(df, n, m)` | 6,1 | 累积摆动 |
| WVAD | `ta.WVAD(df, n, m)` | 24,6 | 威廉变异离散量 |
| PVT | `ta.PVT(df)` | - | 量价趋势 |
| WAD | `ta.WAD(df)` | - | 威廉聚散 |
| CJL | `ta.CJL(df)` | - | 成交量 |
| CCL | `ta.CCL(df)` | - | 持仓量 |
| OPI | `ta.OPI(df)` | - | 持仓量 |
| CR | `ta.CR(df, n)` | 26 | CR 指标 |
| RC | `ta.RC(df, n)` | 50 | RC 指标 |
| RCCD | `ta.RCCD(df, n1, n2, n3)` | 5,10,20 | RCCD 指标 |
| LON | `ta.LON(df, n1, n2)` | 10,10 | LON 指标 |
| ZDZB | `ta.ZDZB(df, n1, n2, n3, n4)` | 3,6,12,24 | 筹码指标 |

### 1.7 通道类（2 个）

| 指标 | 函数 | 参数 | 说明 |
|------|------|------|------|
| HCL | `ta.HCL(df, n)` | 20 | HCL 通道 |
| B3612 | `ta.B3612(df, n)` | 36 | B3612 通道 |

### 1.8 其他（8 个）

| 指标 | 函数 | 参数 | 说明 |
|------|------|------|------|
| MASS | `ta.MASS(df, n1, n2)` | 9,25 | 梅斯线 |
| MV | `ta.MV(df, n)` | n=周期 | 均量线 |
| SHORT | `ta.SHORT(df, n, m)` | n,m | 做空指标 |
| BS_VALUE | `ta.BS_VALUE(df, n, m)` | n,m | 买卖价值 |
| OPTION_GREEKS | - | - | 期权希腊字母 |
| OPTION_IMPV | - | - | 期权隐含波动率 |
| OPTION_VALUE | - | - | 期权价值 |
| VOLATILITY_CURVE | - | - | 波动率曲线 |

---

## 二、系统集成方案

### 2.1 数据流

```
TqSdk K线 → sync_indicators.py → DuckDB indicators 表
                                        ↓
                              scan_opportunities.py (读取预计算指标)
                                        ↓
                              IndicatorEngine (仅计算高级指标)
```

### 2.2 指标分类

**A类：TqSdk 直接提供（12 个基础指标）**
- 均线：MA, EMA, SMA
- 趋势：DMI(+DI/-DI/ADX)
- 震荡：RSI, KDJ, WR, CCI
- 动量：MACD, ROC
- 波动率：ATR, BOLL

**B类：TqSdk 提供但系统未使用（58 个新增指标）**
- 均线：EMA2, BBI, DMA, EXPMA, TRMA, DKX
- 趋势：SAR, ENV, MIKE, PUBU, QHLSR
- 震荡：KD, BIAS, PSY, LWR, SLOWKD, VRSI, DPO, CDP
- 动量：MTM, MI, MICD, DBCD, SRDM, SRMI, DDI, ADTM
- 波动率：BBIBOLL, PRICEOSC, VOSC
- 成交量：OBV, AD, MFI, VR, VROC, ARBR, ASI, WVAD, PVT, WAD, CR, RC, RCCD, LON, ZDZB
- 通道：HCL, B3612
- 其他：MASS, MV

**C类：系统自行计算的高级指标（~15 个）**
- ER, R², Hurst, TSI, ADXR, ADX分位数, STOCHRSI, Ultimate Oscillator
- ATR比率, EMA斜率强度, 均线间距/斜率/趋势方向
- Swing Structure, 七维复合趋势强度, Donchian Channel

### 2.3 实施步骤

1. **升级 sync_indicators.py** — 计算所有 70 个指标
2. **升级 scan_opportunities.py** — 从 indicators 表读取预计算指标
3. **新增多维度信号筛选** — 综合使用趋势+动量+成交量+波动率指标
4. **更新 IndicatorEngine** — 添加 B 类指标作为可选指标

---

## 三、多维度信号筛选框架

### 3.1 信号维度

| 维度 | 指标 | 权重 |
|------|------|------|
| 趋势 | ADX, DMI, SAR, EMA斜率 | 30% |
| 动量 | MACD, ROC, MTM, RSI | 25% |
| 成交量 | OBV, MFI, VR, AD | 20% |
| 波动率 | ATR, BOLL, 布林宽度 | 15% |
| 通道 | Donchian, HCL, B3612 | 10% |

### 3.2 综合评分

```
综合得分 = Σ(维度得分 × 维度权重)
```

每个维度内取多个指标的均值作为维度得分。

---

*本文档是 TqSdk 技术指标集成的设计规范。*
