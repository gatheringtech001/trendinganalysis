from __future__ import annotations

from collections import Counter, defaultdict


def _target_pairs(report):
    images = {row["image_id"]: row for row in report.get("images", [])}
    observations = {
        row["image_id"]: row for row in report.get("image_observations", [])
    }
    return [
        (image, observations.get(image_id, {}))
        for image_id, image in images.items()
        if image.get("store_id") == "aloruh_shein"
    ]


def _distribution(items, labels):
    counts = Counter(name for name, _image_id in items)
    ids = defaultdict(list)
    for name, image_id in items:
        ids[name].append(image_id)
    total = sum(counts.values())
    return [
        {
            "label": label,
            "count": counts[key],
            "share": counts[key] / total if total else 0,
            "image_ids": ids[key],
        }
        for key, label in labels
        if counts[key]
    ]


def first_image_profile(report):
    labels = (
        ("studio", "标准棚拍 / 电商商品图"),
        ("lifestyle", "户外或室内生活方式图"),
        ("selfie", "自拍 / 镜面图"),
        ("collage", "拼接 / 图文信息图"),
        ("detail", "近景 / 局部细节图"),
        ("other", "其他首图"),
    )
    items = []
    for image, observation in _target_pairs(report):
        if int(image.get("position") or 0) != 1:
            continue
        observable = observation.get("observable", {})
        text = " ".join(str(observable.get(key, "")) for key in (
            "first_image_type", "scene", "framing", "text_overlay",
        ))
        if any(word in text for word in ("自拍", "镜面")):
            kind = "selfie"
        elif any(word in text for word in ("拼接", "信息图", "图文", "双栏")):
            kind = "collage"
        elif any(word in text for word in ("近景", "局部", "细节", "特写")):
            kind = "detail"
        elif any(word in text for word in (
            "海滩", "街", "户外", "咖啡", "卧室", "建筑", "生活方式",
            "度假", "场景", "墙面光影",
        )):
            kind = "lifestyle"
        elif any(word in text for word in (
            "影棚", "棚拍", "纯背景", "电商", "中性背景", "商品图",
        )):
            kind = "studio"
        else:
            kind = "other"
        items.append((kind, image["image_id"]))
    return _distribution(items, labels)


def scene_profile(report):
    labels = (
        ("neutral", "浅灰 / 米白 / 纯色棚景"),
        ("indoor", "室内生活方式场景"),
        ("street", "街道 / 建筑场景"),
        ("vacation", "海滩 / 度假场景"),
        ("mirror", "镜面 / 自拍场景"),
        ("other", "其他或无法归类"),
    )
    items = []
    for image, observation in _target_pairs(report):
        text = str(observation.get("observable", {}).get("scene", ""))
        if any(word in text for word in ("镜面", "自拍", "镜子")):
            kind = "mirror"
        elif any(word in text for word in ("海滩", "沙滩", "海边", "度假")):
            kind = "vacation"
        elif any(word in text for word in ("街道", "街景", "建筑", "入口", "户外")):
            kind = "street"
        elif any(word in text for word in ("卧室", "咖啡", "室内", "房间", "沙发")):
            kind = "indoor"
        elif any(word in text for word in (
            "浅灰", "米白", "纯白", "纯色", "无缝", "影棚", "棚拍",
        )):
            kind = "neutral"
        else:
            kind = "other"
        items.append((kind, image["image_id"]))
    return _distribution(items, labels)


def _face_kind(text):
    if not text or any(word in text for word in ("不可观察", "完全不可见", "面部不可见", "不在画面")):
        return "none"
    if any(word in text for word in ("完整可见", "完整面部可见", "完全可见")):
        return "complete"
    return "partial"


def _gaze_kind(text):
    if not text or any(word in text for word in ("不可观察", "不可见")):
        return "unknown"
    if any(word in text for word in ("直视", "正视", "朝向镜头", "看向镜头")):
        return "camera"
    if any(word in text for word in ("低头", "向下")):
        return "down"
    return "away"


def model_profile(report):
    pairs = []
    for image, observation in _target_pairs(report):
        observable = observation.get("observable", {})
        presence = str(observable.get("model_presence", ""))
        if any(word in presence for word in ("0人", "无模特")):
            continue
        pairs.append((image, observable))
    total = len(pairs)
    face = Counter(_face_kind(str(row.get("face_visibility", ""))) for _, row in pairs)
    gaze = Counter(_gaze_kind(str(row.get("expression_gaze", ""))) for _, row in pairs)
    single = sum(
        "1" in str(row.get("model_presence", ""))
        and "2" not in str(row.get("model_presence", ""))
        for _, row in pairs
    )
    hair_visible = [
        str(row.get("hairstyle", "")) for _, row in pairs
        if row.get("hairstyle") and "不可观察" not in str(row.get("hairstyle"))
    ]
    dark_long = sum(
        any(word in text for word in ("深色", "深棕", "黑色"))
        and any(word in text for word in ("长发", "中长发"))
        for text in hair_visible
    )
    makeup_visible = sum(
        row.get("makeup_presentation")
        and not any(word in str(row.get("makeup_presentation")) for word in (
            "不可观察", "无法完整观察", "不可充分观察",
        ))
        for _, row in pairs
    )
    rows = [
        ("单人实穿", single, total),
        ("完整面部可见", face["complete"], total),
        ("局部面部 / 遮挡 / 裁切", face["partial"], total),
        ("面部不可见", face["none"], total),
        ("深色中长或长发（可见发型中）", dark_long, len(hair_visible)),
        ("妆容至少部分可见", makeup_visible, total),
        ("直视或正视镜头", gaze["camera"], total),
        ("侧看 / 低头 / 视线移开", gaze["away"] + gaze["down"], total),
    ]
    representative = [
        image["image_id"] for image, observable in pairs
        if _face_kind(str(observable.get("face_visibility", ""))) == "complete"
        and not any(word in " ".join(map(str, observable.values())) for word in (
            "太阳镜", "墨镜", "手机遮挡",
        ))
    ][:8]
    return {
        "sample_count": total,
        "rows": [
            {"label": label, "count": count, "denominator": denominator,
             "share": count / denominator if denominator else 0}
            for label, count, denominator in rows
        ],
        "representative_image_ids": representative,
    }
