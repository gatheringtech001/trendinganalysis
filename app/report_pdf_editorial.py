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
        if spec["page"] == 6:
            requirements["scope"] = "section"
        occasion_tags = {
            32: ["CASUAL"],
            33: ["DATE_NIGHT", "GOING_OUT", "PARTY"],
            34: ["BEACH", "SWIM_COVERUP"],
        }
        if spec["page"] in occasion_tags:
            requirements.update({"scope": "store", "tags": occasion_tags[spec["page"]]})
        ids = self._take(spec, 12, requirements)
        self._grid(ids, 50, 55, 1820, 840, min(6, len(ids)), 8)

    def _draw_dense_mosaic(self, spec):
        self._header(spec)
        requirements = {"allow_fewer": True}
        if spec.get("store"):
            requirements["scope"] = "store"
        if spec["page"] in {22, 42}:
            requirements["scope"] = "section"
        if spec["page"] == 31:
            requirements.update({
                "scope": "store",
                "include_any": ["头部", "面部", "脸"],
            })
        ids = self._take(spec, 20, requirements)
        self._grid(ids, 50, 45, 1820, 860, min(10, len(ids)), 6)

    def _draw_scope(self, spec):
        scope = self.report["scope"]
        self._grid(self._take(spec, 9), 790, 0, 1130, 1080, 3, 6, .25)
        self._text(spec["title"], 50, 990, 34, 660, WHITE, True, max_lines=4)
        self._text(self._body(spec), 50, 790, 19, 650, SAND, max_lines=7)
        metrics = [(scope["target_images"], "ALORUH 全量目标图"), (len(self.report["image_observations"]), "逐图观察"), (scope["competitor_population_images"], "竞品全量分母")]
        for index, (value, label) in enumerate(metrics):
            y = 430 - index * 110
            self._text(f"{value:,}", 50, y, 42, 250, WHITE, True)
            self._text(label, 285, y - 2, 16, 360, SAND)

    def _draw_hero_collage(self, spec):
        category = "TOPS" if spec["page"] == 9 else "SKIRTS"
        ids = self._take(spec, 10, {"category": category})
        self._grid(ids, 0, 0, 1920, 1080, 5, 0, .08)
        self.canvas.setFillColorRGB(0, 0, 0, alpha=.65)
        self.canvas.rect(0, 0, 690, 1080, fill=1, stroke=0)
        self._text(spec["title"], 52, 920, 30, 570, WHITE, True, max_lines=4)
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
        slots = [
            ({**spec, "claim": 0}, {"category": "TOPS", "include_any": ["近景", "近距离", "躯干", "上半身"]}, "TOPS 近景"),
            ({**spec, "claim": 1}, {"category": "SKIRTS", "include_groups": [["全长", "全身", "腰头"], ["下摆", "完整"]]}, "SKIRTS 全长"),
            ({**spec, "claim": 2}, {"evidence": "support", "include_any": ["正面"]}, "正面"),
            ({**spec, "claim": 2}, {"evidence": "counter", "include_any": ["背面", "背对", "背身"]}, "背面"),
            ({**spec, "claim": 2}, {"evidence": "support", "include_any": ["局部", "近景", "特写", "近距离"]}, "局部"),
        ]
        for index, (source, requirements, label) in enumerate(slots):
            image_id = self._take(source, 1, requirements)[0]
            x = 50 + index * 364
            self._photo(image_id, x, 360, 330, 500, slot=label)
            self._text(label, x, 315, 18, 330, INK, True)
            self._text("构图 / 动作 / 卖点 / 场景", x, 265, 14, 330, STONE)
        self._text(self._body(spec), 50, 145, 21, 1780, INK, max_lines=3)

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
        if spec["page"] == 49:
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
        evidence = "counter" if spec["page"] == 50 else "support"
        requirements = {"scope": "section", "evidence": evidence}
        self._grid(self._take(spec, 8, requirements), 500, 30, 1360, 1000, 4, 10)

    def _draw_plan(self, spec):
        self._text(spec["title"], 110, 800, 30, 240, INK, True)
        self._text(spec["subtitle"], 110, 450, 22, 260, STONE, True, max_lines=3)
        requirements = {"scope": "section", "evidence": "support"}
        self._grid(self._take(spec, 8, requirements), 390, 35, 1460, 1000, 4, 10)
