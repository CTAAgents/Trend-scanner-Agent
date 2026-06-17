#!/usr/bin/env python3
"""
因子溯源图可视化工具

生成因子溯源图的交互式HTML可视化页面。

用法：
    python tools/factor_graph_viz.py                    # 生成可视化页面
    python tools/factor_graph_viz.py --output viz.html  # 指定输出文件
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from trend_scanner.factor_lifecycle import FactorAsset, FactorLifecycleManager, LifecycleState
from trend_scanner.factor_graph import FactorProvenanceGraph, NodeType, EdgeType


def load_sample_data() -> FactorProvenanceGraph:
    """加载示例数据"""
    graph = FactorProvenanceGraph()

    # 添加论文节点
    papers = [
        ("arxiv_2605_01300", "Visibility Graphs Can Make Money", {"arxiv_id": "2605.01300"}),
        ("arxiv_2604_26747", "AlphaCrafter", {"arxiv_id": "2604.26747"}),
        ("arxiv_2507_23392", "FinClaw", {"arxiv_id": "2507.23392"}),
    ]
    for pid, name, attrs in papers:
        graph.add_node(graph.create_node(NodeType.PAPER, pid, name, attrs))

    # 添加因子节点
    factors = [
        ("VGRSI_A0", "VGRSI均值聚合", {"category": "momentum", "state": "S4_released"}),
        ("VGRSI_A1", "VGRSI比率聚合", {"category": "momentum", "state": "S4_released"}),
        ("VGRSI_Multi", "多周期VGRSI一致性", {"category": "momentum", "state": "S3_verified"}),
        ("adaptive_momentum", "自适应动量", {"category": "momentum", "state": "S4_released"}),
        ("volatility_adjusted_trend", "波动率调整趋势", {"category": "trend", "state": "S5_degraded"}),
        ("volume_breakout", "成交量突破", {"category": "volume", "state": "S2_draft"}),
    ]
    for fid, name, attrs in factors:
        graph.add_node(graph.create_node(NodeType.FACTOR, fid, name, attrs))

    # 添加策略节点
    strategies = [
        ("trend_strategy_001", "EMA20+MA60多时间框架", {"timeframes": ["M1", "M5", "M30"]}),
    ]
    for sid, name, attrs in strategies:
        graph.add_node(graph.create_node(NodeType.STRATEGY, sid, name, attrs))

    # 添加关系
    relations = [
        ("arxiv_2605_01300", "VGRSI_A0", EdgeType.INSPIRED_BY),
        ("arxiv_2605_01300", "VGRSI_A1", EdgeType.INSPIRED_BY),
        ("VGRSI_A0", "VGRSI_Multi", EdgeType.COMPOSED_WITH),
        ("VGRSI_A1", "VGRSI_Multi", EdgeType.COMPOSED_WITH),
        ("VGRSI_Multi", "trend_strategy_001", EdgeType.DEPENDS_ON),
        ("adaptive_momentum", "volatility_adjusted_trend", EdgeType.EVOLVED_FROM),
    ]
    for src, tgt, etype in relations:
        graph.add_edge(graph.create_edge(src, tgt, etype))

    return graph


def generate_html(graph: FactorProvenanceGraph) -> str:
    """生成HTML可视化页面"""
    export_data = graph.export_for_visualization()
    stats = graph.get_statistics()

    # 节点颜色映射
    node_colors = {
        "paper": "#4A90D9",
        "factor": "#7B68EE",
        "strategy": "#2ECC71",
        "backtest": "#F39C12",
        "market": "#E74C3C",
    }

    # 边颜色映射
    edge_colors = {
        "inspired_by": "#4A90D9",
        "evolved_from": "#7B68EE",
        "composed_with": "#2ECC71",
        "validated_by": "#F39C12",
        "degraded_in": "#E74C3C",
        "depends_on": "#95A5A6",
        "replaces": "#E67E22",
    }

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>因子溯源知识图 - Factor Provenance Graph</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 24px;
            margin-bottom: 5px;
        }}
        .header p {{
            opacity: 0.8;
            font-size: 14px;
        }}
        .container {{
            display: flex;
            height: calc(100vh - 80px);
        }}
        #graph {{
            flex: 1;
            background: #16213e;
        }}
        .sidebar {{
            width: 300px;
            background: #1a1a2e;
            border-left: 1px solid #333;
            overflow-y: auto;
            padding: 20px;
        }}
        .legend {{
            margin-bottom: 20px;
        }}
        .legend h3 {{
            margin-bottom: 10px;
            color: #667eea;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            font-size: 13px;
        }}
        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 10px;
        }}
        .stats {{
            background: #16213e;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }}
        .stats h3 {{
            margin-bottom: 10px;
            color: #667eea;
        }}
        .stat-item {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            font-size: 13px;
        }}
        .node-info {{
            background: #16213e;
            border-radius: 8px;
            padding: 15px;
        }}
        .node-info h3 {{
            margin-bottom: 10px;
            color: #667eea;
        }}
        .info-row {{
            margin-bottom: 8px;
            font-size: 13px;
        }}
        .info-label {{
            color: #888;
        }}
        .info-value {{
            color: #fff;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>因子溯源知识图</h1>
        <p>Factor Provenance Graph - 基于 SkillWiki 论文的因子关系网络</p>
    </div>
    <div class="container">
        <div id="graph"></div>
        <div class="sidebar">
            <div class="legend">
                <h3>节点类型</h3>
                <div class="legend-item">
                    <div class="legend-color" style="background: {node_colors['paper']}"></div>
                    <span>论文 (Paper)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: {node_colors['factor']}"></div>
                    <span>因子 (Factor)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: {node_colors['strategy']}"></div>
                    <span>策略 (Strategy)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: {node_colors['backtest']}"></div>
                    <span>回测 (Backtest)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: {node_colors['market']}"></div>
                    <span>市场状态 (Market)</span>
                </div>
            </div>

            <div class="legend">
                <h3>关系类型</h3>
                <div class="legend-item">
                    <div class="legend-color" style="background: {edge_colors['inspired_by']}; width: 12px; height: 3px; border-radius: 2px;"></div>
                    <span>inspired_by</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: {edge_colors['evolved_from']}; width: 12px; height: 3px; border-radius: 2px;"></div>
                    <span>evolved_from</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: {edge_colors['composed_with']}; width: 12px; height: 3px; border-radius: 2px;"></div>
                    <span>composed_with</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: {edge_colors['depends_on']}; width: 12px; height: 3px; border-radius: 2px;"></div>
                    <span>depends_on</span>
                </div>
            </div>

            <div class="stats">
                <h3>图统计</h3>
                <div class="stat-item">
                    <span class="info-label">节点总数</span>
                    <span class="info-value">{stats['total_nodes']}</span>
                </div>
                <div class="stat-item">
                    <span class="info-label">边总数</span>
                    <span class="info-value">{stats['total_edges']}</span>
                </div>
                <div class="stat-item">
                    <span class="info-label">论文</span>
                    <span class="info-value">{stats['node_types'].get('paper', 0)}</span>
                </div>
                <div class="stat-item">
                    <span class="info-label">因子</span>
                    <span class="info-value">{stats['node_types'].get('factor', 0)}</span>
                </div>
                <div class="stat-item">
                    <span class="info-label">策略</span>
                    <span class="info-value">{stats['node_types'].get('strategy', 0)}</span>
                </div>
            </div>

            <div class="node-info" id="nodeInfo">
                <h3>节点详情</h3>
                <p style="color: #888; font-size: 13px;">点击节点查看详细信息</p>
            </div>
        </div>
    </div>

    <script>
        // 节点数据
        const nodes = [
            {chr(10).join([f'{{id: "{n["id"]}", label: "{n["label"]}", color: node_colors["{n["type"]}"], shape: "dot", size: 20, font: {{color: "#fff", size: 12}}}}' for n in export_data['nodes']])}
        ];

        // 边数据
        const edges = [
            {chr(10).join([f'{{from: "{e["source"]}", to: "{e["target"]}", color: {{color: edge_colors["{e["type"]}"]}}, arrows: "to", label: "{e["type"]}", font: {{size: 10, color: "#888"}}}}' for e in export_data['edges']])}
        ];

        // 节点颜色映射
        const node_colors = {json.dumps(node_colors)};

        // 边颜色映射
        const edge_colors = {json.dumps(edge_colors)};

        // 节点数据（JSON格式）
        const nodesData = {json.dumps(export_data['nodes'])};

        // 创建网络
        const container = document.getElementById('graph');
        const data = {{
            nodes: new vis.DataSet(nodes),
            edges: new vis.DataSet(edges)
        }};

        const options = {{
            physics: {{
                enabled: true,
                barnesHut: {{
                    gravitationalConstant: -3000,
                    centralGravity: 0.3,
                    springLength: 150,
                    springConstant: 0.04
                }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 200
            }},
            edges: {{
                smooth: {{
                    type: 'continuous'
                }}
            }}
        }};

        const network = new vis.Network(container, data, options);

        // 点击节点显示详情
        network.on('click', function(params) {{
            if (params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                const nodeData = nodesData.find(n => n.id === nodeId);
                if (nodeData) {{
                    const infoDiv = document.getElementById('nodeInfo');
                    let html = '<h3>节点详情</h3>';
                    html += '<div class="info-row"><span class="info-label">ID:</span> <span class="info-value">' + nodeData.id + '</span></div>';
                    html += '<div class="info-row"><span class="info-label">名称:</span> <span class="info-value">' + nodeData.label + '</span></div>';
                    html += '<div class="info-row"><span class="info-label">类型:</span> <span class="info-value">' + nodeData.type + '</span></div>';
                    if (nodeData.attributes && Object.keys(nodeData.attributes).length > 0) {{
                        html += '<div class="info-row"><span class="info-label">属性:</span></div>';
                        for (const [key, value] of Object.entries(nodeData.attributes)) {{
                            html += '<div class="info-row" style="padding-left: 20px;"><span class="info-label">' + key + ':</span> <span class="info-value">' + value + '</span></div>';
                        }}
                    }}
                    infoDiv.innerHTML = html;
                }}
            }}
        }});
    </script>
</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="因子溯源图可视化工具")
    parser.add_argument("--output", type=str, default="factor_graph_viz.html", help="输出HTML文件路径")
    parser.add_argument("--sample", action="store_true", help="使用示例数据")

    args = parser.parse_args()

    # 加载数据
    if args.sample:
        graph = load_sample_data()
    else:
        # 尝试从文件加载
        graph_path = project_root / "data" / "factor_graph.json"
        if graph_path.exists():
            with open(graph_path, encoding="utf-8") as f:
                data = json.load(f)
            graph = FactorProvenanceGraph.from_dict(data)
        else:
            print("未找到因子图数据文件，使用示例数据", file=sys.stderr)
            graph = load_sample_data()

    # 生成HTML
    html = generate_html(graph)

    # 保存文件
    output_path = project_root / args.output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"可视化页面已生成: {output_path}")
    print(f"在浏览器中打开即可查看因子溯源图")


if __name__ == "__main__":
    main()
