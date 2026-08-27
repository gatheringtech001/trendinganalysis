from report_pdf_layout import DeckBase, INK, PAGE, PAPER, SAND, STONE, WHITE, SECTION_LABELS


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
        categories = self._key_analysis().get("key_categories", [])
        for index, row in enumerate(categories[:3]):
            x = 55 + index * 610
            image_id = self._take(spec, 1, {
                "scope": "store", "category": row["category"],
            })[0]
            self._photo(image_id, x, 300, 560, 570, slot=row["category"])
            self._text(row["category"], x, 245, 22, 560, INK, True)
            self._text(
                f"全量 {row['population_products']:,} 件 · 随机复核 {row['sample_selected']} 张",
                x, 200, 15, 560, STONE,
            )
        tags = self._dimension_values("visual_language")[:4]
        summary = " / ".join(row["tag"] for row in tags) or "风格标签覆盖不足，以随机样本视觉观察为准"
        self._text(f"视觉语言：{summary}", 55, 105, 17, 1780, STONE, max_lines=2)

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
            (scope.get("target_products", scope["target_images"]), f"ALORUH 商品 / {scope['target_images']:,}张多视角"),
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
            f"全量 {row['population_products']:,} 件 · 随机抽取 {row['sample_selected']} 张\n"
            f"复现种子 {sampling.get('seed', '未记录')}",
            52, 815, 17, 570, SAND, max_lines=3,
        )
        self._text(self._body(spec), 52, 700, 18, 560, WHITE, max_lines=8)

    def _draw_method(self, spec):
        self._header(spec)
        labels = ["标准正面", "氛围首图", "结构证据", "局部细节"]
        for index, label in enumerate(labels):
            x = 55 + index * 455
            self.canvas.setFillColor(PAPER)
            self.canvas.roundRect(x, 165, 420, 650, 12, fill=1, stroke=0)
            self._text(f"0{index + 1}", x + 25, 760, 24, 80, SAND, True)
            self._text(label, x + 25, 675, 29, 360, INK, True, max_lines=2)
            claim = self._section(spec)["claims"][index % 3]
            self._text(claim["conclusion"], x + 25, 560, 18, 360, STONE, max_lines=8)

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
            self._text("重点提升", x + 18, 101, 15, 200, WHITE, True)

    def _draw_matrix(self, spec):
        self._header(spec)
        categories = [
            row["category"] for row in self._key_analysis().get("key_categories", [])
        ]
        near_category = "TOPS" if "TOPS" in categories else categories[0]
        full_candidates = [row for row in categories if row != near_category]
        full_category = "SKIRTS" if "SKIRTS" in full_candidates else full_candidates[0]
        detail_candidates = [
            row for row in categories if row not in {near_category, full_category}
        ]
        detail_category = detail_candidates[0] if detail_candidates else full_category
        display_fields = [
            "framing", "pose_action", "garment_display",
            "design_details", "material_texture",
        ]
        slots = [
            ({**spec, "claim": 0}, {"scope": "store", "category": near_category, "semantic_fields": display_fields, "include_any": ["近景", "近距离", "躯干", "上半身"]}, f"{near_category} 近景"),
            ({**spec, "claim": 1}, {"scope": "store", "category": full_category, "semantic_fields": display_fields, "include_groups": [["全长", "全身", "腰头"], ["下摆", "完整"]]}, f"{full_category} 全长"),
            ({**spec, "claim": 2}, {"scope": "store", "category": detail_category, "semantic_fields": ["pose_action", "framing", "garment_display"], "include_any": ["正面", "正向", "面向镜头", "正对镜头"], "exclude_any": ["背对镜头", "模特背对", "仅背面", "正面不可见", "未展示正面", "正面不清楚"]}, "正面"),
            ({**spec, "claim": 2}, {"scope": "store", "category": detail_category, "semantic_fields": ["pose_action", "framing", "garment_display"], "include_any": ["背面", "背对", "后侧", "后背"], "exclude_any": ["背面不可见", "未展示背面", "背面不清楚", "无法核验背面", "不能核验背面", "后背不可见"]}, "背面"),
            ({**spec, "claim": 2}, {"scope": "store", "category": detail_category, "semantic_fields": display_fields, "include_any": ["局部", "近景", "特写", "近距离"]}, "局部"),
        ]
        for index, (source, requirements, label) in enumerate(slots):
            image_id = self._take(source, 1, requirements)[0]
            x = 50 + index * 364
            self._photo(image_id, x, 360, 330, 500, slot=label)
            self._text(label, x, 315, 18, 330, INK, True)
            self._text("构图 / 动作 / 卖点 / 场景", x, 265, 14, 330, STONE)
        self._text(self._body(spec), 50, 145, 21, 1780, INK, max_lines=3)

    def _draw_model_portrait(self, spec):
        self._header(spec)
        fields = (
            "model_presence", "face_visibility", "hairstyle",
            "makeup_presentation", "expression_gaze",
        )
        ids = []
        for image_id, observation in self.observations.items():
            if self.images.get(image_id, {}).get("store_id") != "aloruh_shein":
                continue
            values = [observation.get("observable", {}).get(field) for field in fields]
            if any(value and "不可观察" not in value for value in values):
                ids.append(image_id)
        if not ids:
            raise ValueError("可见模特画像没有可复核图片")
        self._grid(ids[:8], 55, 390, 1160, 500, min(4, len(ids)), 8)
        labels = {
            "model_presence": "模特在场", "face_visibility": "面部可见性",
            "hairstyle": "可见发型", "makeup_presentation": "可见妆容",
            "expression_gaze": "表情与视线",
        }
        for index, field in enumerate(fields):
            values = []
            for image_id in ids:
                value = self.observations[image_id].get("observable", {}).get(field)
                if value and value not in values:
                    values.append(value)
            self._text(labels[field], 1280, 855 - index * 150, 16, 530, STONE, True)
            self._text(" / ".join(values[:3]) or "不可观察", 1280, 805 - index * 150, 19, 560, INK, max_lines=3)
        self._text("不推断年龄、种族、国籍、身高、体型尺寸、健康或吸引力。", 55, 90, 16, 1800, STONE)

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
        requirements = {
            "scope": "claims",
            "evidence": "support",
            "allow_fewer": True,
            "allow_repeat": False,
            "exclude_image_ids": self.plan_used_image_ids,
            "include_any": spec.get("include_any", []),
            "exclude_any": spec.get("exclude_any", []),
        }
        ids = self._take(spec, 8, requirements)
        self.plan_used_image_ids.update(ids)
        columns = 3 if len(ids) in {5, 6} else min(4, len(ids))
        self._grid(ids, 390, 35, 1460, 1000, columns, 10)
