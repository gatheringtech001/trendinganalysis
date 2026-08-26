from __future__ import annotations

from database_builder import STORES


MANUAL_VISUAL_REVIEW = {
    "princess_polly": {
        "场景": "冷白或灰调棚拍为主，穿插户外、镜面自拍与居家场景。",
        "构图": "全身与半身并用，局部裁切用于突出廓形、面料或鞋履。",
        "模特": "模特呈现占主导，姿态从正面商品展示延伸到更动态的生活方式表达。",
        "视觉语言": "快速趋势、夜出与度假语汇并存，首图变化度较高。",
        "风险": "丰富度高，但跨品类首图的一致性需要继续用更大样本验证。",
    },
    "motel": {
        "场景": "浅灰白棚拍和简洁室内为主，少量复古木色与蓝灰背景。",
        "构图": "半身和特写较多，重点落在上装、领口、首饰和面部附近。",
        "模特": "模特呈现占主导，镜头距离整体比标准全身电商图更近。",
        "视觉语言": "低饱和、复古 Y2K 与轻颗粒感共同形成更亲密的编辑氛围。",
        "风险": "近景强化风格，但完整搭配与下装比例信息覆盖相对有限。",
    },
    "prettylittlething": {
        "场景": "暖米灰无缝背景为骨架，街拍、校园或居家场景作为主题补充。",
        "构图": "标准全身电商图与半身编辑图并用，也出现单品静物图。",
        "模特": "模特图占主导；样本中有 1 张官方占位图，已从量化统计排除。",
        "视觉语言": "高商业化、高频主题切换和较宽色彩覆盖，适合快速上新。",
        "风险": "不同主题线的场景跨度大，整体一致性需按系列而非全店判断。",
    },
    "aloruh_local": {
        "场景": "居家、书房、庭院与旧室内叙事场景占主导，几乎不使用纯棚背景。",
        "构图": "半身与全身交替，近景常用于强调褶裥、蕾丝与印花面料。",
        "模特": "模特图几乎全覆盖，自然姿态、侧视与环境互动较多。",
        "视觉语言": "暖色、自然环境色、复古田园与柔光叙事形成清晰辨识度。",
        "风险": "视觉风格集中，但样本仅 19 款，且缺少评论和热度证据校验。",
    },
    "aloruh_shein": {
        "场景": "SHEIN SG 图片已建立独立索引，尚未形成可复算的下载样本。",
        "构图": "150 款商品详情图已入索引，但尚未完成独立接触表复核。",
        "模特": "当前不把 Aloruh 自有站的模特样本外推到 SHEIN SG 渠道。",
        "视觉语言": "证据不足；需对 SHEIN SG 图片独立下载、量化与人工复核。",
        "风险": "没有独立有效主图样本，暂不输出 SHEIN 渠道视觉结论。",
    },
}


def _confidence(valid_images: int) -> str:
    if valid_images >= 15:
        return "Medium"
    if valid_images >= 5:
        return "Low-Medium"
    return "Low"


def _rounded(row: dict, key: str) -> float:
    return round(float(row.get(key) or 0), 3)


def build_visual_profile(store, store_id: str) -> dict:
    aggregate = store._one(
        """
        SELECT COUNT(*) sample_size, SUM(valid) valid_images,
               AVG(CASE WHEN valid THEN brightness END) brightness,
               AVG(CASE WHEN valid THEN saturation END) saturation,
               AVG(CASE WHEN valid THEN warmth END) warmth,
               AVG(CASE WHEN valid THEN edge_density END) edge_density,
               AVG(CASE WHEN valid THEN border_brightness END) border_brightness,
               AVG(CASE WHEN valid THEN border_saturation END) border_saturation,
               AVG(CASE WHEN valid THEN height > width END) portrait_rate,
               AVG(CASE WHEN valid THEN border_brightness >= 0.65
                        AND border_saturation <= 0.18 END) neutral_border_rate
        FROM visual_features WHERE store_id = ?
        """,
        [store_id],
    )
    sample_size = int(aggregate["sample_size"] or 0)
    valid_images = int(aggregate["valid_images"] or 0)
    palettes = store._all(
        "SELECT dominant_family label, COUNT(*) count FROM visual_features "
        "WHERE store_id = ? AND valid = 1 GROUP BY dominant_family "
        "ORDER BY count DESC, label LIMIT 4",
        [store_id],
    )
    samples = store._all(
        """
        SELECT p.product_id, p.title, p.category_group category, p.price_usd,
               p.primary_image_url image_url, p.source_url
        FROM visual_features v JOIN products p
          ON p.store_id = v.store_id AND p.product_id = v.product_id
        WHERE v.store_id = ? AND v.valid = 1
        ORDER BY COALESCE(p.catalog_rank, 999999), p.product_id LIMIT 6
        """,
        [store_id],
    )
    return {
        "sample_size": sample_size,
        "valid_images": valid_images,
        "excluded_images": sample_size - valid_images,
        "confidence": _confidence(valid_images),
        "metrics": {
            key: _rounded(aggregate, key)
            for key in (
                "brightness", "saturation", "warmth", "edge_density",
                "border_brightness", "border_saturation", "portrait_rate",
                "neutral_border_rate",
            )
        },
        "palette": palettes,
        "manual_review": MANUAL_VISUAL_REVIEW[store_id],
        "samples": samples,
        "method": (
            "对已下载主图计算 HSV 亮度/饱和度、RGB 冷暖、Canny 边缘密度、"
            "边框明暗与中性背景比例，并对接触表人工复核场景、构图和模特表达。"
        ),
    }


def visual_comparison_rows(profiles: list[dict]) -> list[dict]:
    rows = []
    for profile in profiles:
        visual = profile["visual"]
        rows.append({
            "store_id": profile["store_id"],
            "store_name": STORES[profile["store_id"]],
            "sample_size": visual["sample_size"],
            "valid_images": visual["valid_images"],
            "confidence": visual["confidence"],
            **visual["metrics"],
            "scene": visual["manual_review"]["场景"],
            "composition": visual["manual_review"]["构图"],
            "visual_language": visual["manual_review"]["视觉语言"],
        })
    return rows


def visual_comparison_insight(profiles: list[dict]) -> dict | None:
    eligible = [profile for profile in profiles if profile["visual"]["valid_images"]]
    if not eligible:
        return None
    darkest = min(eligible, key=lambda item: item["visual"]["metrics"]["brightness"])
    brightest = max(eligible, key=lambda item: item["visual"]["metrics"]["brightness"])
    return {
        "title": "主图明暗差异",
        "finding": (
            f"当前有效样本中，{darkest['store_name']} 平均亮度最低，"
            f"{brightest['store_name']} 最高；这是主图样本特征，不代表全量视觉资产。"
        ),
        "confidence": "Medium",
    }
