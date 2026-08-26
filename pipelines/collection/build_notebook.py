"""Build and execute the reproducible first-loop analysis notebook without Jupyter dependencies."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]
OUTPUT = BASE / "output" / "analysis" / "first_loop_analysis.ipynb"


def markdown(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def execute(cells: list[dict]) -> None:
    namespace: dict = {}
    execution_count = 0
    for cell in cells:
        if cell["cell_type"] != "code":
            continue
        execution_count += 1
        stream = io.StringIO()
        source = "".join(cell["source"])
        with contextlib.redirect_stdout(stream):
            exec(compile(source, f"cell-{execution_count}", "exec"), namespace)
        cell["execution_count"] = execution_count
        output = stream.getvalue()
        if output:
            cell["outputs"] = [{"name": "stdout", "output_type": "stream", "text": output.splitlines(keepends=True)}]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    cells = [
        markdown("# 第一闭环：三家店铺外部自我画像研究\n\n**快照日：2026-08-14｜市场：美国｜近期窗口：2026-05-16 至 2026-08-14**"),
        markdown("## tl;dr\n\n本Notebook复算三家店铺的目录、150款分层样本、评论/UGC覆盖和QA。三店分别成像，不做横向排名；销量仅使用公开代理指标。"),
        code("""import json
from pathlib import Path
BASE = Path.cwd()
analysis = json.loads((BASE / 'output' / 'analysis' / 'analysis_summary.json').read_text(encoding='utf-8'))
qa = json.loads((BASE / 'output' / 'analysis' / 'qa_results.json').read_text(encoding='utf-8'))
for key, row in analysis.items():
    c, r, u = row['catalog'], row['reviews'], row['ugc']
    print(f\"{row['store_name']}: catalog={c['row_count']:,}, sample=150, reviews={r['count']}, UGC={u['count']}\")
"""),
        markdown("## Context & Methods\n\n目录来自官方商品接口或官网实际使用的产品索引；样本按 New、Best/Trending、Sale/长尾各50款去重抽取。评论与UGC均按公开可得量交付。目录解析覆盖率表示已观察官方索引记录的标准化成功率，不等同于未知真实SKU总量覆盖率。"),
        code("""for key, checks in qa['stores'].items():
    assert checks['duplicate_product_ids'] == 0
    assert checks['duplicate_sample_product_ids'] == 0
    assert checks['sample_target_met']
    print(key, checks['sample_bucket_counts'], 'parse_coverage=', checks['observed_index_parse_coverage'])
"""),
        markdown("## Data\n\n数据层包括商品目录、150款样本、全量图片URL哈希、72张下载图片内容哈希、评论/UGC、来源日志、视觉页面截图和覆盖率QA。"),
        code("""for key, row in analysis.items():
    c, s = row['catalog'], row['sample']
    print(f\"\\n{row['store_name']}\")
    print('catalog price P25/median/P75:', c['price_p25_usd'], c['price_median_usd'], c['price_p75_usd'])
    print('catalog available/sold-out/sale:', c['available_rate'], c['sold_out_rate'], c['on_sale_rate'])
    print('sample price P25/median/P75:', s['price_p25_usd'], s['price_median_usd'], s['price_p75_usd'])
    print('top categories:', [(x['label'], x['count']) for x in c['top_categories'][:5]])
"""),
        markdown("## Results\n\n以下只描述店内结构和证据覆盖。售罄率、折扣率、评论量、互动量和站内排序均为代理指标，不解释为销量。"),
        code("""for key, row in analysis.items():
    print(f\"\\n{row['store_name']}\")
    print('reviews:', row['reviews']['count'], 'avg_rating:', row['reviews']['average_rating'])
    print('review themes:', [(x['label'], x['count']) for x in row['reviews']['top_themes'][:5]])
    print('UGC platforms:', [(x['label'], x['count']) for x in row['ugc']['platforms']])
    print('recent-window UGC:', row['ugc']['recent_window_count'])
"""),
        markdown("## Takeaways\n\n- Princess Polly拥有可用于实证客群与场合分析的500条匿名商品评论；Motel与PLT的公开评论仅为摘要级记录，结论置信度更低。\n- PLT公开首页和New In页面在采集环境返回CloudFront 403，页面视觉判断留空，不绕过限制。\n- 商品目录中的高售罄或长期折扣可能包含长尾/历史在售状态，必须与150款当前层级样本并读。\n- 所有优化假设仍需内部销售、转化和利润数据验证。"),
    ]
    execute(cells)
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    loaded = json.loads(OUTPUT.read_text(encoding="utf-8"))
    executed = [cell for cell in loaded["cells"] if cell["cell_type"] == "code"]
    assert all(cell["execution_count"] for cell in executed)
    print(json.dumps({"path": str(OUTPUT), "cells": len(cells), "executed_code_cells": len(executed)}))


if __name__ == "__main__":
    main()
