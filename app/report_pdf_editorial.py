from report_pdf_layout import DeckBase, INK, PAGE, PAPER, SAND, STONE, WHITE, SECTION_LABELS
from report_pdf_insights import first_image_profile, model_profile, scene_profile


class EditorialDeck(DeckBase):
    def _draw_cover(self, _spec):
        self._text("ALORUH", 680, 565, 84, 700, INK, True)
        self.canvas.setStrokeColor(INK)
        self.canvas.line(650, 535, 1265, 535)

    def _draw_divider(self, spec):
        self._text("A", 45, 1010, 18, 40, INK, True)
        self._text("\n".join(spec["title"].split()), 48, 720, 70, 850, INK, True, 1.04, 4)
        self._text(SECTION_LABELS[spec["section"]], 1150, 620, 62, 600, INK, max_lines=2)

    def _draw_statement(self, spec):
        claim = self._claim(spec)
        self._text("品牌名称", 830, 940, 24, 300, INK, True)
        self._text("Brand Name", 835, 890, 17, 300, STONE)
        self._text("ALORUH", 650, 700, 58, 700, INK, True)
        self._text("allure / aura / soft sensuality", 650, 625, 22, 750, STONE)
        self._text(claim["conclusion"], 390, 450, 22, 1160, INK, max_lines=4)

    def _key_analysis(self):
        analysis = self.report.get("scope", {}).get("key_category_analysis")
        if not analysis:
            raise ValueError("PDF缺少重点品类分析范围")
        return analysis

    def _draw_store_profile(self, spec):
        self._header(spec)
        profile = self.report.get("scope", {}).get("store_profile") or {}
        metrics = [
            ("店铺", profile.get("store_name")),
            ("平台 / 市场", " / ".join(filter(None, [profile.get("platform"), profile.get("market")]))),
            ("商品总数", f"{int(profile.get('product_count') or 0):,}"),
            ("图片索引", f"{int(profile.get('image_count') or 0):,}"),
            ("品类数量", str(profile.get("category_count") or "—")),
            ("数据更新时间", str(profile.get("data_updated_at") or "未记录")[:19]),
        ]
        for index, (label, value) in enumerate(metrics):
            x = 70 + (index % 3) * 600
            y = 760 - (index // 3) * 330
            self.canvas.setFillColor(PAPER)
            self.canvas.roundRect(x, y - 185, 550, 235, 12, fill=1, stroke=0)
            self._text(label, x + 30, y, 17, 480, STONE, True)
            self._text(value or "未记录", x + 30, y - 78, 31, 480, INK, True, max_lines=2)

    def _draw_category_overview(self, spec):
        self._header(spec)
        analysis = self._key_analysis()
        selected = analysis.get("key_categories", []) + analysis.get(
            "supplementary_categories", [],
        )
        selected_names = [row["category"] for row in selected]
        distribution = {
            row["category"]: row for row in analysis.get("distribution", [])
        }
        rows = [distribution[name] for name in selected_names if name in distribution]
        rows = rows or analysis.get("distribution", [])[:8]
        if not rows:
            raise ValueError("PDF缺少全量品类分布")
        maximum = max(row["products"] for row in rows)
        key_names = set(selected_names)
        step = min(96, 720 / max(len(rows), 1))
        for index, row in enumerate(rows):
            y = 835 - index * step
            self._text(row["category"], 70, y, 18, 300, INK, row["category"] in key_names)
            self.canvas.setFillColor(SAND if row["category"] in key_names else PAPER)
            self.canvas.roundRect(390, y - 4, 1120 * row["products"] / maximum, 30, 8, fill=1, stroke=0)
            self._text(f"{row['products']:,} · {row.get('share', 0):.1%}", 1540, y, 18, 300, STONE, True)

    def _dimension_values(self, dimension):
        raw = self._key_analysis().get("dimension_distributions", {}).get(dimension, [])
        return raw.get("values", []) if isinstance(raw, dict) else raw

    def _draw_style_split(self, spec):
        self._header(spec)
        modules = [
            ("极简精致", ["浅灰", "米白", "纯白", "棚拍", "简洁"]),
            ("度假浪漫", ["海滩", "沙滩", "度假", "藤编", "拱形"]),
            ("晚装魅力", ["亮片", "缎面", "晚装", "夜间", "派对", "硬光", "金属"]),
            ("柔和通勤", ["通勤", "西装", "衬衫", "白裤", "深棕"]),
        ]
        for index, (label, keywords) in enumerate(modules):
            x = 45 + index * 465
            image_id = self._take(spec, 1, {
                "scope": "store", "include_any": keywords,
            })[0]
            self._photo(image_id, x, 235, 430, 640, slot=label)
            self._text(label, x, 180, 22, 430, INK, True)
        self._text(
            "四类模块可以在同一商品或同一图片中重叠；本页用于解释视觉方向，不代表互斥份额。",
            45, 95, 16, 1800, STONE,
        )

    def _draw_product_codes(self, spec):
        self._header(spec)
        dimensions = [
            ("廓形", "silhouette"), ("色彩 / 图案", "palette"),
            ("设计元素", "design_details"), ("材质", "material_texture"),
            ("使用场合", "scene"),
        ]
        for index, (label, field) in enumerate(dimensions):
            x = 45 + index * 370
            image_id = self._take(spec, 1, {
                "semantic_fields": [field], "allow_repeat": False,
            })[0]
            value = self._semantic_fields(image_id).get(field, "未观察到")
            self._photo(image_id, x, 390, 340, 500, slot=label)
            self._text(label, x, 335, 20, 340, INK, True)
            self._text(value, x, 270, 14, 340, STONE, max_lines=6)

    def _draw_dark_collage(self, spec):
        self._grid(self._take(spec, 8), 565, 80, 1305, 920, 4, 8, .12)
        self._text(spec["title"], 50, 990, 22, 450, WHITE, True, max_lines=2)
        self._text(spec["subtitle"], 50, 250, 22, 430, WHITE, True, max_lines=3)
        self._text(self._body(spec), 50, 160, 15, 430, SAND, max_lines=5)

    def _draw_mosaic(self, spec):
        self._header(spec)
        requirements = {"allow_fewer": True}
        if spec.get("store"):
            requirements["scope"] = "store"
        if spec.get("pool_scope"):
            requirements["scope"] = spec["pool_scope"]
        if spec.get("occasion_tags"):
            requirements.update({"scope": "store", "tags": spec["occasion_tags"]})
        ids = self._take(spec, 12, requirements)
        self._grid(ids, 50, 55, 1820, 840, min(6, len(ids)), 8)

    def _draw_dense_mosaic(self, spec):
        self._header(spec)
        requirements = {"allow_fewer": True}
        if spec.get("store"):
            requirements["scope"] = "store"
        if spec.get("pool_scope"):
            requirements["scope"] = spec["pool_scope"]
        if spec.get("semantic_include_any"):
            requirements.update({
                "scope": "store",
                "include_any": spec["semantic_include_any"],
            })
        ids = self._take(spec, 20, requirements)
        self._grid(ids, 50, 45, 1820, 860, min(10, len(ids)), 6)

    def _draw_scope(self, spec):
        scope = self.report["scope"]
        self._grid(self._take(spec, 9), 790, 0, 1130, 1080, 3, 6, .25)
        self._text(spec["title"], 50, 990, 34, 660, WHITE, True, max_lines=4)
        self._text(self._body(spec), 50, 790, 19, 650, SAND, max_lines=7)
        metrics = [
            (scope.get("target_products", scope["target_images"]), f"ALORUH 商品 · {scope['target_images']:,}张多视角"),
            (len(self.report["image_observations"]), "逐图观察"),
            (scope["competitor_population_images"], "竞品12维可比分母"),
        ]
        for index, (value, label) in enumerate(metrics):
            y = 430 - index * 110
            self._text(f"{value:,}", 50, y, 42, 250, WHITE, True)
            self._text(label, 285, y - 2, 16, 360, SAND)

    def _draw_category_sample(self, spec):
        analysis = self._key_analysis()
        categories = analysis.get("key_categories", [])
        index = spec.get("category_index", 0)
        if index >= len(categories):
            raise ValueError(f"PDF缺少第 {index + 1} 个重点品类")
        row = categories[index]
        category = row["category"]
        ids = self._take(spec, 10, {
            "scope": "store", "category": category, "allow_fewer": True,
        })
        self._grid(ids, 0, 0, 1920, 1080, 5, 0, .08)
        self.canvas.setFillColorRGB(0, 0, 0, alpha=.65)
        self.canvas.rect(0, 0, 690, 1080, fill=1, stroke=0)
        self._text(category, 52, 920, 42, 570, WHITE, True, max_lines=2)
        sampling = analysis.get("sampling", {})
        self._text(
            f"全量 {row['population_products']:,} 个商品 · 随机抽取 {row['sample_selected']} 个商品\n"
            f"成功读取 {row.get('downloaded_images', row['sample_selected'])} 张图 · "
            f"复现种子 {sampling.get('seed', '未记录')}",
            52, 815, 17, 570, SAND, max_lines=3,
        )
        self._text(self._body(spec), 52, 700, 18, 560, WHITE, max_lines=8)

    def _draw_method(self, spec):
        self._header(spec)
        roles = [
            ("标准正面", "回答：整体比例、正面领口与腰线是否清楚。"),
            ("背面结构", "回答：露背、系带、闭合与后腰结构是什么。"),
            ("局部细节", "回答：面料纹理、工艺与装饰是否可核验。"),
            ("场景氛围", "回答：商品属于什么场合；不能替代结构图。"),
        ]
        for index, (label, explanation) in enumerate(roles):
            x = 55 + index * 455
            self.canvas.setFillColor(PAPER)
            self.canvas.roundRect(x, 165, 420, 650, 12, fill=1, stroke=0)
            self._text(f"0{index + 1}", x + 25, 760, 24, 80, SAND, True)
            self._text(label, x + 25, 675, 29, 360, INK, True, max_lines=2)
            self._text(explanation, x + 25, 560, 18, 360, STONE, max_lines=8)

    def _draw_traits(self, spec):
        self._header(spec)
        labels = ["设计点前置", "身体线条清楚", "完整搭配", "结构可核对"]
        for index, (image_id, label) in enumerate(zip(self._take(spec, 4), labels)):
            x = 50 + index * 458
            self._photo(image_id, x, 185, 420, 650)
            self._text(label, x + 15, 135, 17, 380, INK, True)

    def _draw_feature(self, spec):
        self._header(spec)
        self._text(self._body(spec), 55, 860, 23, 1810, INK, max_lines=3)
        for index, image_id in enumerate(self._take(spec, 3)):
            x = 55 + index * 610
            self._photo(image_id, x, 85, 575, 640)
            self.canvas.setFillColor(INK)
            self.canvas.rect(x, 85, 575, 48, fill=1, stroke=0)
            observation = self.observations.get(image_id, {})
            reason = (observation.get("weaknesses") or ["图位职责需进一步明确"])[0]
            self._text(f"需提升：{reason}", x + 18, 101, 13, 535, WHITE, True, max_lines=2)

    def _draw_matrix(self, spec):
        self._header(spec)
        categories = self._key_analysis().get("key_categories", [])[:3]
        claims = self._section(spec)["claims"]
        for index, row in enumerate(categories):
            category = row["category"]
            source = {**spec, "claim": min(index, len(claims) - 1)}
            ids = self._take(source, 2, {
                "scope": "store", "category": category, "allow_fewer": True,
            })
            x = 45 + index * 620
            for image_index, image_id in enumerate(ids[:2]):
                self._photo(image_id, x + image_index * 285, 450, 265, 420,
                            slot=f"{category} 证据{image_index + 1}")
            self._text(category, x, 390, 22, 570, INK, True)
            fields = [
                ("构图", "framing"), ("动作", "pose_action"),
                ("卖点", "design_details"), ("场景", "scene"),
                ("搭配", "styling"),
            ]
            lines = []
            for label, field in fields:
                values = [self._semantic_fields(image_id).get(field, "") for image_id in ids]
                value = next((value for value in values if value), "未观察到")
                lines.append(f"{label}：{value[:34]}{'…' if len(value) > 34 else ''}")
            self._text("\n".join(lines), x, 335, 14, 570, STONE,
                       leading=1.45, max_lines=10)

    def _draw_scene_overview(self, spec):
        self._header(spec)
        rows = scene_profile(self.report)
        maximum = max((row["count"] for row in rows), default=1)
        for index, row in enumerate(rows):
            y = 830 - index * 125
            self._text(row["label"], 55, y, 18, 390, INK, True)
            self.canvas.setFillColor(SAND)
            self.canvas.roundRect(480, y - 2, 950 * row["count"] / maximum, 30,
                                  7, fill=1, stroke=0)
            self._text(f"{row['count']}张 · {row['share']:.1%}", 1470, y, 18, 300, STONE, True)
            if row["image_ids"]:
                self._photo(row["image_ids"][0], 1745, y - 50, 110, 90,
                            slot=row["label"])

    def _draw_model_portrait(self, spec):
        self._header(spec)
        profile = model_profile(self.report)
        ids = profile["representative_image_ids"]
        if not ids:
            raise ValueError("可见模特画像没有可复核图片")
        self._grid(ids, 55, 245, 1050, 650, min(4, len(ids)), 8)
        for index, row in enumerate(profile["rows"]):
            column, line = index % 2, index // 2
            x, y = 1170 + column * 350, 845 - line * 165
            self._text(row["label"], x, y, 14, 320, STONE, True, max_lines=2)
            self._text(f"{row['count']}/{row['denominator']} · {row['share']:.1%}",
                       x, y - 62, 21, 320, INK, True)
        self._text(
            f"样本：{profile['sample_count']}张含模特的目标图。代表图仅选完整露脸且无眼镜/手机遮挡的画面。",
            55, 125, 15, 1800, STONE,
        )
        self._text("不推断年龄、种族、国籍、身高、体型尺寸、健康或吸引力。", 55, 85, 15, 1800, STONE)

    def _draw_first_image_types(self, spec):
        self._header(spec)
        rows = first_image_profile(self.report)
        maximum = max((row["count"] for row in rows), default=1)
        for index, row in enumerate(rows):
            y = 830 - index * 125
            self._text(row["label"], 55, y, 18, 430, INK, True)
            self.canvas.setFillColor(PAPER)
            self.canvas.roundRect(510, y - 2, 900, 30, 7, fill=1, stroke=0)
            self.canvas.setFillColor(SAND)
            self.canvas.roundRect(510, y - 2, 900 * row["count"] / maximum, 30,
                                  7, fill=1, stroke=0)
            self._text(f"{row['count']}张 · {row['share']:.1%}", 1450, y, 18, 260, STONE, True)
            if row["image_ids"]:
                self._photo(row["image_ids"][0], 1725, y - 50, 125, 90,
                            slot=row["label"])

    def _draw_logic(self, spec):
        self._header(spec)
        labels = ["场景入口分散", "模板重复", "信息层级不统一"]
        for index, label in enumerate(labels):
            source = {**spec, "claim": index}
            image_id = self._take(source, 1, {"evidence": "support"})[0]
            x = 75 + index * 610
            self._photo(image_id, x, 210, 535, 650, slot=label)
            self._text(label, x, 165, 18, 530, INK, True)
        self._text(self._body(spec), 75, 105, 16, 1750, STONE, max_lines=2)

    def _draw_quote(self, spec):
        self._text(spec["title"], 190, 690, 50, 1500, WHITE, True, 1.12, 4)
        self.canvas.setStrokeColor(SAND)
        self.canvas.setLineWidth(3)
        self.canvas.line(190, 540, 1740, 540)
        self._text(self._body(spec), 190, 455, 22, 1450, SAND, max_lines=5)

    def _draw_three_compare(self, spec):
        self._header(spec)
        for index, image_id in enumerate(self._take(spec, 3)):
            self._photo(image_id, index * 640, 0, 640, 900, .12 if index != 1 else 0)
        self._text(self._body(spec), 55, 820, 19, 550, WHITE, True, max_lines=5)

    def _draw_four_compare(self, spec):
        self._header(spec)
        if spec.get("alternating_evidence"):
            roles = ["counter", "support", "counter", "support"]
            ids = [self._take(spec, 1, {"evidence": role})[0] for role in roles]
        else:
            ids = self._take(spec, 4)
        for index, image_id in enumerate(ids):
            label = "现状" if index % 2 == 0 else "规则参考"
            self._photo(
                image_id, index * 480, 0, 480, 905,
                .22 if index % 2 == 0 else 0,
                slot=f"{label} {index // 2 + 1}",
            )
            self._text(label, index * 480 + 35, 55, 17, 170, WHITE, True)

    def _draw_brand_codes(self, spec):
        self._header(spec)
        source_specs = [
            {"section": "brand_positioning", "page": spec["page"]},
            {**spec, "store": "princess_polly"},
            {**spec, "store": "motel"},
            {**spec, "store": "prettylittlething"},
        ]
        motel_pair = self._take(source_specs[2], 2)
        ids = [
            self._take(source_specs[0], 1)[0],
            self._take(source_specs[1], 1)[0],
            motel_pair[1],
            self._take(source_specs[3], 1)[0],
        ]
        labels = ["ALORUH", "PRINCESS POLLY", "MOTEL ROCKS", "PRETTYLITTLETHING"]
        claims = self._section(spec)["claims"]
        for index, (image_id, label) in enumerate(zip(ids, labels)):
            x = 50 + index * 455
            self._photo(image_id, x, 405, 420, 480, .2, slot=label)
            self._text(label, x, 355, 17, 420, INK, True)
            body = self.sections["brand_positioning"]["summary"] if index == 0 else claims[index - 1]["conclusion"]
            self._text(body, x, 300, 14, 405, STONE, max_lines=7)
        self._photo(motel_pair[0], 1240, 430, 115, 150)
        note = self._competitor_coverage_note()
        if note:
            self._text(note, 50, 105, 15, 1810, STONE, True, max_lines=2)

    def _competitor_coverage_note(self):
        categories = self.report.get("scope", {}).get("categories", [])
        stores = self.report.get("competitor_evidence", {}).get("stores", {})
        if not categories or not stores:
            return ""
        available = set(categories)
        for plan in stores.values():
            available &= {
                category for category, row in plan.get("categories", {}).items()
                if row.get("status") == "available"
            }
        comparable = [category for category in categories if category in available]
        unavailable = [category for category in categories if category not in available]
        parts = [
            "三家竞品共同12维可比范围："
            + (" / ".join(comparable) if comparable else "无共同覆盖品类"),
        ]
        if unavailable:
            parts.append(f"{' / '.join(unavailable)} 尚无三家完整覆盖，不纳入竞品结论")
        return "；".join(parts) + "。"

    def _draw_brand_feature(self, spec):
        ids = self._take(spec, 4)
        self._photo(ids[0], 810, 0, 1110, 1080, .08)
        for index, image_id in enumerate(ids[1:]):
            self._photo(image_id, 50 + index * 235, 65, 215, 285, .12)
        self._text(spec["title"], 50, 940, 44, 690, WHITE, True, max_lines=2)
        self._text(spec.get("subtitle", ""), 50, 825, 24, 650, SAND, True, max_lines=3)
        self._text(self._body(spec), 50, 670, 18, 650, WHITE, max_lines=8)

    def _draw_roadmap(self, spec):
        self._text(spec["title"], 95, 900, 44, 1500, WHITE, True, max_lines=2)
        phases = [("PHASE 01", "统一底层拍摄逻辑"), ("PHASE 02", "根据商品决定首图拍法"), ("PHASE 03", "建立分品类主图模板")]
        for index, (phase, label) in enumerate(phases):
            x = 95 + index * 600
            self._text(phase, x, 580, 20, 300, SAND, True)
            self._text(label, x, 500, 30, 500, WHITE, True, max_lines=3)

    def _draw_four_series(self, spec):
        self._header(spec)
        slots = [
            ("CASUAL OUTING", ["休闲", "街头", "日常", "通勤"]),
            ("ROMANTIC DATE", ["约会", "浪漫"]),
            ("VACATION SUN-KISSED", ["度假", "海边", "沙滩", "海景"]),
            ("PARTY NIGHT OUT", ["派对", "夜间", "晚宴", "酒吧"]),
        ]
        for index, (label, keywords) in enumerate(slots):
            requirements = {"scope": "store", "include_any": keywords}
            image_id = self._take(spec, 1, requirements)[0]
            x = index * 480
            self._photo(image_id, x, 0, 480, 900, .12, slot=label)
            self._text(label, x + 24, 120, 17, 420, WHITE, True, max_lines=2)

    def _draw_flow(self, spec):
        self._header(spec)
        self._text("趋势提取  ->  搭配转译  ->  首图更新", 55, 865, 28, 1200, INK, True)
        for index, image_id in enumerate(self._take(spec, 5)):
            x = 55 + index * 365
            self._photo(image_id, x, 140, 330, 620)
            if index < 4:
                self._text("->", x + 337, 470, 20, 35, STONE, True)

    def _draw_grid_compare(self, spec):
        self._text(spec["title"], 30, 1010, 22, 180, INK, True)
        requirements = {"scope": "section", "evidence": spec["evidence"]}
        self._grid(self._take(spec, 8, requirements), 500, 30, 1360, 1000, 4, 10)

    def _draw_plan(self, spec):
        self._text(spec["title"], 110, 800, 30, 240, INK, True)
        self._text(spec["subtitle"], 110, 450, 22, 260, STONE, True, max_lines=3)
        rules = (
            "首图/结构图：浅灰米白背景 + 柔和均匀光\n"
            "固定正面全貌、背面结构、材质近景三个职责"
            if spec["title"] == "PLAN A" else
            "后置氛围图：海滩/街道/夜间等场景\n"
            "硬光或直闪只服务材质与场合，不替代结构说明"
        )
        self._text(rules, 70, 300, 15, 300, INK, max_lines=7)
        requirements = {
            "scope": "store",
            "allow_fewer": True,
            "allow_repeat": False,
            "exclude_image_ids": self.plan_used_image_ids,
            "semantic_fields": spec.get("semantic_fields"),
            "include_any": spec.get("include_any", []),
            "exclude_any": spec.get("exclude_any", []),
        }
        ids = self._take(spec, 8, requirements)
        self.plan_used_image_ids.update(ids)
        columns = 3 if len(ids) in {5, 6} else min(4, len(ids))
        self._grid(ids, 390, 35, 1460, 1000, columns, 10)
