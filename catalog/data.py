"""SKU 素材读取与字段映射。

数据源：MARS-6 的 SKU素材收集模板 **v6**（23 SPU 唯一权威版；v5 及更早仅留痕）。
规范 §六 给出「版式位置 → 清单字段」的映射表，本模块按表取数。

v6 相对 v5 只有 5 格差异，全部落在瑜伽 5 个 SPU 的认证列
（`CE/FCC/UL/ETL/PSE` → `非电器——认证徽章不适用…`）。
`cert_list()` 对 Ellylife 本返回空、且 `is_missing()` 已把「非电器」判为缺失，
故这 5 格对 M2 产出是 no-op（MARS-9 预检已逐格比对确认）。

三条硬规则收敛在这里：
1. 缺测值一律显示「待补」（muted 色），禁止估算编造；
2. 型号字符串以清单为准；
3. 右栏第 2/3 格只展示该品类**已有实测**的主参数，没有就写「待补」。
"""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 权威版钉死 v6（MARS-9 预检裁决）；引用必须单点。
CSV_NAME = "SKU素材收集模板_v6.csv"

MISSING = "待补"

# v5 里表示"未实测"的写法：待补（建议…）/ 待实测补录 / 待核 / — / 空
_MISSING_PAT = re.compile(r"待补|待实测|待核|^\s*[—\-–]+\s*$|^\s*$|非电器")


def is_missing(v):
    """该字段是否为未实测值。"""
    if v is None:
        return True
    return bool(_MISSING_PAT.search(str(v)))


def cjk_latin_space(text):
    """中文字与拉丁/数字之间补一个空格（打样页的排印惯例）。

    "50kPa大吸力" → "50kPa 大吸力"；"瑜伽垫TPE-06" → "瑜伽垫 TPE-06"

    同时把 `℃`（U+2103）规范化成 `°C`（U+00B0 + C）—— 打样页用的是后者
    （见 A7 页卖点 "180° 平躺设计"），且部分中文字体缺 U+2103 字形会出豆腐块。
    """
    text = text.replace("℃", "°C")
    text = re.sub(r"([0-9A-Za-z%°)\]）])([\u4e00-\u9fff])", r"\1 \2", text)
    text = re.sub(r"([\u4e00-\u9fff])([0-9A-Za-z(（])", r"\1 \2", text)
    return text


class Sku:
    """单个 SPU 的结构化视图。"""

    def __init__(self, row):
        self.raw = row
        self.spu = row["SPU编码"].strip()
        # 型号以 v5 清单为准（打样页出现过 TBK06 / TPE-06 两种写法）
        self.model = row["型号"].strip()
        self.name_cn = row["中文品名"].strip()
        self.category = row["二级分类"].strip()
        self.page_group = row["入册页组"].strip()
        self.brand = row["品牌标"].strip()
        self.sku_count = row["在售SKU数"].strip()
        self.variant_summary = row["规制/颜色摘要（已填·请核对）"].strip()
        self.points = [row["核心卖点1（中文·短句）"].strip(),
                       row["核心卖点2（中文·短句）"].strip(),
                       row["核心卖点3（中文·短句）"].strip()]
        self.power_w = row["额定功率W"].strip()
        self.coverage = row["覆盖面积/有效范围"].strip()
        self.noise_db = row["噪音dB"].strip()
        self.size_field = row["尺寸L×W×H mm"].strip()
        self.weight_kg = row["净重/毛重 kg"].strip()
        self.voltage = row["电压制式"].strip()
        self.certs_field = row["持证清单确认（默认CE/FCC/UL/ETL/PSE，如不符请改）"].strip()
        self.carton_mm = row["外箱尺寸 mm"].strip()
        self.carton_kg = row["单箱毛重 kg"].strip()
        self.per_carton = row["每箱数量"].strip()
        self.moq = row["MOQ"].strip()
        self.oem = row["OEM/ODM能力说明"].strip()
        self.images = row["现有主图文件（已盘点·请指认可用张）"].strip()
        self.image_grade = row["主图可印评级（A直排/B≤85mm/C需补拍重抠）"].strip()

    # ------------------------------------------------------------ 品牌
    @property
    def is_ellylife(self):
        return self.brand.lower() == "ellylife"

    # ------------------------------------------------------------ 品名
    # v5 的「中文品名」列里，拉丁尾串有时写的是 **SPU 编码**而不是「型号」。
    # 例：SPU `YJD-TPE-06` / 型号 `TBK06` / 品名 `瑜伽垫TPE-06`。
    # 经理终验明确：**型号字符串以 v5「型号」列为准**，`TPE-06` 是 SPU 编码
    # 不是型号，版面上应写作「瑜伽垫 TBK06」。
    #
    # 这是 v5 数据本身的系统性问题，全表 23 个 SPU 里有 6 个受影响
    # （LP005-White / PBK05 / TBK06 / TBK08 / BVC-T8 / PMR04），
    # 故在此统一按「型号列为权威」纠正，而不是逐页硬改文案。
    _LATIN_TAIL = re.compile(r"([A-Za-z][A-Za-z0-9\-]*)\s*$")

    @property
    def display_name(self):
        """版面上使用的中文品名 —— 拉丁尾串对齐 v5「型号」列。"""
        name = self.name_cn
        m = self._LATIN_TAIL.search(name)
        if not m:
            return name
        tail = m.group(1)
        base = name[:m.start()].rstrip()
        if tail.replace("-", "").lower() == self.model.replace("-", "").lower():
            return name                       # 已经是型号，原样使用
        if tail.replace("-", "").lower() in self.spu.replace("-", "").lower():
            # 尾串是 SPU 编码 → 换成 v5 权威型号
            return f"{base}{self.model}"
        return name                           # 其它情况不动（如 CR208 的括注）

    @property
    def is_electric(self):
        """瑜伽品类不适用 CE/FCC/UL/ETL/PSE（规范 §二 M2 Ellylife 变体）。"""
        return not is_missing(self.power_w)

    def brand_label(self):
        """左栏品牌标签（§二 M2：HEARTEN / ELLYLIFE）。"""
        return "ELLYLIFE" if self.is_ellylife else "HEARTEN"

    def cert_list(self):
        """认证徽章行；Ellylife 变体认证位留空。"""
        if self.is_ellylife:
            return []
        base = ["CE", "FCC", "UL", "ETL", "PSE"]
        f = self.certs_field
        if not f or f == "CE/FCC/UL/ETL/PSE":
            return base
        found = [c.strip() for c in re.split(r"[/,、]", f) if c.strip()]
        return found or base

    # ------------------------------------------------------------ 右栏
    def power_display(self):
        """右栏黑块：数值 + 单位。

        打样实测的取数规则：
        * 电器类（有额定功率）→ 黑块放 功率（规范 §六「右栏 POWER ← 额定功率W」）；
        * 非电器类（瑜伽品类，v5 功率字段为「—(非电器)」）→ 黑块改放该品类的
          头号实测主参数（瑜伽垫 = 厚度），与打样页 TBK06 一致。
        绝不把「非电器」渲染成「待补」——那不是缺测，是不适用。
        """
        if self.is_electric:
            v = self.power_w
            # 单位只取拉丁/符号段：v6 有 "400W 无刷" 这类写法，"无刷"是电机
            # 类型不是单位（它由对比表/合并页的电机类型行展示）。若整段塞进
            # 单位并按小标签档用拉丁字体渲染，中文会出豆腐块。
            m = re.match(r"^\s*([\d.]+)\s*([A-Za-z\u03bc%/\u00b0\u00b2\u00b3]*)", v)
            if not m:
                return cjk_latin_space(v), ""
            return m.group(1), (m.group(2).strip() or "W")
        label, value, unit, _ = self.hero_black()
        return value, unit

    def hero_black_label(self):
        """黑块标签文案（与 hero_black() 配套）。"""
        return "功率" if self.is_electric else self.hero_black()[0]

    def moq_display(self):
        """起订量格（v5 MOQ=1000，23/23 满）。"""
        if is_missing(self.moq):
            return MISSING, ""
        return self.moq, "pcs"

    # -------- 主参数槽（打样实测的取数结构）--------
    def hero_black(self):
        """黑块主参数（非电器品类用）。"""
        if self.category == "瑜伽垫":
            return self._thickness()
        return self._dims()

    def hero_white(self):
        """白底格的两个实测主参数（不含起订量）。

        严格只取 v5 里**明确写出**的数字，取不到即「待补」，绝不估算。
        对应规范 §六：「右栏第 2/3 格改用该品类已有实测的主参数」。
        """
        cat = self.category
        if cat == "吸尘器":
            return [self._from_points("吸力", r"([\d.]+)\s*kPa", "kPa"),
                    self._runtime()]
        if cat == "蒸汽清洗机":
            # v5 原文 "105℃高温蒸汽…"；单位按打样惯例渲染为 °C
            return [self._from_points("蒸汽温度", r"([\d.]+)\s*[℃°]", self._temp_unit()),
                    self._from_points("水箱容量", r"([\d.]+)\s*ml", "ml")]
        if cat in ("洗地机", "布艺清洗机"):
            return [self._from_points("吸力", r"([\d.]+)\s*kPa", "kPa"),
                    self._noise()]
        if cat == "瑜伽垫":
            # 黑块已放厚度，白格放尺寸 + 净重（与打样页 TBK06 一致）
            return [self._dims(), self._weight()]
        if cat in ("烘鞋器/烘被机", "瑜伽砖"):
            return [self._dims(), self._weight()]
        return [self._dims(), self._weight()]

    # -------- 白格取值助手 --------
    def _from_points(self, label, pattern, unit, prefer=()):
        """从卖点文案里取出**明确写出**的数值主参数。"""
        for p in self.points:
            if not p:
                continue
            m = re.search(pattern, p)
            if m:
                return (label, m.group(1), unit, False)
        return (label, MISSING, "", True)

    def _temp_unit(self):
        """温度单位：v5 里写作 ℃，版面上按打样惯例渲染为 °C。"""
        return "°C"

    def _runtime(self):
        """续航：只认卖点里明确写出的「N 分钟」。"""
        for p in self.points:
            if not p:
                continue
            m = re.search(r"([\d.]+)\s*分钟", p)
            if m:
                return ("续航", m.group(1), "min", False)
        return ("续航", MISSING, "", True)

    def _noise(self):
        """噪音：仅对有实测值的款标注（规范 §六）。"""
        if is_missing(self.noise_db):
            return ("噪音", MISSING, "", True)
        m = re.search(r"([\d.]+)", self.noise_db)
        return ("噪音", m.group(1) if m else self.noise_db, "dB", False)

    def _thickness(self):
        """瑜伽垫厚度：从尺寸字段尾段（0.6cm → 6mm）换算。"""
        m = re.search(r"[×x]\s*([\d.]+)\s*cm\s*(?:$|[（(])", self.size_field)
        if m:
            try:
                return ("厚度", f"{float(m.group(1)) * 10:g}", "mm", False)
            except ValueError:
                pass
        return ("厚度", MISSING, "", True)

    def _dims(self):
        """尺寸：长×宽（去掉厚度/高度项），无实测则待补。"""
        if is_missing(self.size_field):
            return ("尺寸", MISSING, "", True)
        m = re.match(r"^\s*([\d.]+)\s*[×x]\s*([\d.]+)", self.size_field)
        if m:
            return ("尺寸", f"{m.group(1)}×{m.group(2)}", "cm", False)
        return ("尺寸", MISSING, "", True)

    def _weight(self):
        """净重：斜杠前为净重、后为毛重。"""
        if is_missing(self.weight_kg):
            return ("净重", MISSING, "", True)
        net = self.weight_kg.split("/")[0].strip().replace("约", "").strip()
        if is_missing(net):
            return ("净重", MISSING, "", True)
        return ("净重", net, "kg", False)

    # ------------------------------------------------------------ 底部参数条
    # 非电器品类（v5 功率/电压字段写作「—(非电器)」）不适用功率与电压，
    # 显示"待补"会误导读者以为在等一个永远不来的实测值。
    # 打样页 TBK06 的处理是把第 3/4 槽换成**材质**，与规范 §六「改用该品类
    # 已有的主参数」同一思路；此处照此实现，材质串只从 v5 卖点原文截取，
    # 不新增任何未经 v5 记载的信息。
    _MATERIAL_SUFFIX = re.compile(
        r"(双层结构|三层结构|层结构|结构|材质|表层|面料|面|款)$")

    def material_display(self):
        """非电器品类的材质摘要（仅从 v5 卖点 1 原文截取）。"""
        p = (self.points[0] or "").strip()
        if not p or is_missing(p):
            return MISSING
        # 材质通常列在最后一个「+」之后（基材+表层）
        tail = re.split(r"[+＋]", p)[-1].strip()
        tail = self._MATERIAL_SUFFIX.sub("", tail).strip()
        return cjk_latin_space(tail) if tail else MISSING

    def param_bar(self):
        """尺寸 + 净重 + 功率 + 电压制式（§六，23/23 满）；缺项写「待补」。

        非电器品类把功率/电压两槽换成材质（见 material_display 说明）。
        """
        parts = []
        # 尺寸
        if is_missing(self.size_field):
            parts.append(MISSING)
        else:
            s = self.size_field
            s = s.split("（")[0].split("(")[0].strip()   # 去掉括注（PU面）等
            s = s.replace(" ", "").replace("x", "×").replace("X", "×")
            s = re.sub(r"^(\d[\d.]*(?:×\d[\d.]*)+)(cm|mm)", r"\1 \2", s)
            parts.append(s)
        # 净重
        if is_missing(self.weight_kg):
            parts.append(MISSING)
        else:
            net = self.weight_kg.split("/")[0].strip().replace("约", "").strip()
            parts.append(net if net.endswith("kg") else f"{net} kg")
        if self.is_electric:
            # 功率
            parts.append(self.power_w if not is_missing(self.power_w) else MISSING)
            # 电压制式
            if is_missing(self.voltage):
                parts.append(MISSING)
            else:
                v = re.sub(r"[（(].*?[)）]", "", self.voltage).strip()
                v = v.replace("~", "").replace(" ", "")
                parts.append(v)
        else:
            # 非电器：材质（替代不适用的功率/电压）
            parts.append(self.material_display())
        return [cjk_latin_space(p) for p in parts]

    # ------------------------------------------------------------ 左栏文案
    def point_title_sub(self, i):
        """把 v5 的一条卖点按母版拆成 标题 + 副句。

        **只在 `·` 与 `，` 处断句，绝不在 `+` 处断。**
        理由（经理终验修正清单 5）：`+` 连接的是同一卖点内的并列成分，
        在 `+` 处断开会把标题切成一个不完整的片段，读起来像改写过的文案。
        例：
          v5 `天然橡胶+环保TPE双层结构` —— 无 `·`/`，`，整句作标题（直排）
          v5 `亲肤超防滑+校准线，附背带`  —— 标题保留 `+校准线`
          v5 `50kPa大吸力·50分钟长续航`   —— `·` 断句，与打样页一致
          v5 `180°平躺设计，床底沙发底一伸即净` —— `，` 断句，与打样页一致

        拆出的标题与副句都**只用 v5 原文**，不改字、不增删信息。
        """
        if i >= len(self.points):
            return "", ""
        p = (self.points[i] or "").strip()
        if not p or is_missing(p):
            return "", ""
        m = re.search(r"[·，]", p)
        if not m:
            return cjk_latin_space(p), ""
        title = p[:m.start()].strip()
        sub = p[m.end():].strip()
        return cjk_latin_space(title), cjk_latin_space(sub)

    def caption(self, view="FRONT"):
        """图注：中文图注 · FIG. 标注（§三）。用 display_name 保证型号口径一致。"""
        return f"{cjk_latin_space(self.display_name)} · {view}"

    @property
    def coming_soon(self):
        """卖点区整体是「Coming Soon」占位（江楠指令：瑜伽砖页只写它）。

        判据取 v6「核心卖点1」原文 —— 该格写作 Coming Soon 时，左栏卖点
        与参数条都让位于占位表达（不做"待补"参数槽的假数据感）。
        """
        return bool(self.points) and self.points[0].strip().lower() == "coming soon"

    def variant_line(self):
        """型号大字下方的一行辅助信息（变体/规制摘要）。"""
        return cjk_latin_space(self.variant_summary) if self.variant_summary else ""

    # ------------------------------------------------------------ 入册页组
    # v6「入册页组」是本阶段页序引擎的**权威分组字段**（MARS-9 预检点名要求
    # 「真正消费」它，替换原先"清单行号即页码"的做法）。三种取值：
    #
    #   独立单品页                                  → 自成一组，键 = 型号
    #   CR208（有刷/无刷合并：1单品页+配置对比表）      → 一组两行，键 = CR208
    #   AW-2（四配置合并：1单品页+配置对比表）         → 一组四行，键 = AW-2
    #
    # 合并组在册子里**只出一页**（组内配置差异用该页的配置对比表表达）。
    _GROUP_HEAD = re.compile(r"^([^（(]+)")

    @property
    def is_merged_group(self):
        """该行是否属于"多配置合并为一页"的页组。"""
        return not self.page_group.startswith("独立单品页")

    @property
    def page_key(self):
        """页组键 —— 决定该行落在册子的哪一页。同键的多行共用一页。"""
        if not self.is_merged_group:
            return self.model
        m = self._GROUP_HEAD.match(self.page_group)
        return (m.group(1).strip() if m else self.model) or self.model

    @property
    def group_label(self):
        """合并组在版面/清单上的组名（独立页即型号）。"""
        return self.page_key

    # ------------------------------------------------------------ 对比表取值
    # M3 系列/对比页与 M2 合并页的配置对比表共用这套取值器。
    # 硬规则（规范 §二 M3）：缺测一律「待补」muted，**不得留空、不得估算**。
    _MOTOR = re.compile(r"电机类型[:：]\s*([^;；]+)")

    def motor_type(self):
        """电机类型（仅从 v6「规制/颜色摘要」原文提取，取不到即待补）。"""
        m = self._MOTOR.search(self.variant_summary or "")
        return (m.group(1).strip() if m else MISSING), (m is None)

    def power_plain(self):
        """对比表用功率串：v6「额定功率W」原文；非电器/缺测 → 待补。"""
        if is_missing(self.power_w):
            return MISSING, True
        return cjk_latin_space(self.power_w.strip()), False

    def voltage_display(self):
        """对比表用电压制式：去掉括注，保留拉丁与 ~ 的规范写法。"""
        if is_missing(self.voltage):
            return MISSING, True
        v = re.sub(r"[（(].*?[)）]", "", self.voltage).strip()
        return cjk_latin_space(v.replace("~", "").strip()), False

    def dims_display(self):
        """对比表用整机尺寸串（cm/mm 原样，× 归一）。"""
        if is_missing(self.size_field):
            return MISSING, True
        s = self.size_field.split("（")[0].split("(")[0].strip()
        s = s.replace(" ", "").replace("x", "×").replace("X", "×")
        s = re.sub(r"^(\d[\d.]*(?:×\d[\d.]*)+)(cm|mm)", r"\1 \2", s)
        return cjk_latin_space(s), False

    def net_weight_display(self):
        """对比表用整机净重（斜杠前为净重）。"""
        if is_missing(self.weight_kg):
            return MISSING, True
        net = self.weight_kg.split("/")[0].strip().replace("约", "").strip()
        if is_missing(net):
            return MISSING, True
        return cjk_latin_space(net if net.endswith("kg") else f"{net} kg"), False

    def noise_display(self):
        """对比表用噪音；仅对有实测值的款标注（规范 §六）。"""
        if is_missing(self.noise_db):
            return MISSING, True
        return cjk_latin_space(self.noise_db.replace("≤", "≤ ").strip()), False

    def thickness_display(self):
        """非电器品类的厚度（瑜伽垫从尺寸字段尾段换算，同 M2 口径）。"""
        label, value, unit, missing = self._thickness()
        if missing:
            return MISSING, True
        return f"{value} {unit}", False

    def material_plain(self):
        """非电器品类的材质摘要（仅从卖点 1 原文截取）。"""
        v = self.material_display()
        return v, v == MISSING

    def sku_count_display(self):
        """在售 SKU 数（v6「在售SKU数」，23/23 满）。"""
        if is_missing(self.sku_count):
            return MISSING, True
        return self.sku_count, False

    _CONFIG_TAG = re.compile(r"(配置[0-9一二三四]+|[有无]刷)")

    def config_tag(self):
        """合并组内该配置的短标签（取自 v6「中文品名」原文）。

        CR208 的品名写"吸尘器CR208无刷/有刷" → 无刷 / 有刷；
        AW-2 的品名写"吸尘器AW-2-配置1..4" → 配置1..配置4。
        这是合并页列题头区分同型号多配置的唯一 v6 原文依据；取不到返回空串。
        """
        m = self._CONFIG_TAG.search(self.name_cn or "")
        return m.group(1) if m else ""

    def compare_rows(self):
        """M3/合并页对比表的行序列:[(行标签, 值, 是否待补), ...]。

        行集按 **两个 SKU 的品类交集**决定（§二 M3「两两对比」）：
        电器款出功率/电机/电压，非电器款出厚度/材质；尺寸、净重、噪音、
        在售 SKU 为两品类共有。跨品类对比（如蒸汽清洗机 vs 布艺清洗机）
        时按"任一方适用即出行"，不适用的一方写「待补」——不编造、不留空。
        """
        other = self._pair_partner
        both = [self] if other is None else [self, other]
        any_electric = any(s.is_electric for s in both)
        any_non_electric = any(not s.is_electric for s in both)

        rows = []
        if any_electric:
            rows.append(("额定功率", self.power_plain()))
            rows.append(("电机类型", self.motor_type()))
            rows.append(("电压制式", self.voltage_display()))
        if any_non_electric:
            rows.append(("厚度", self.thickness_display()))
            rows.append(("材质", self.material_plain()))
        rows.append(("整机尺寸", self.dims_display()))
        rows.append(("整机净重", self.net_weight_display()))
        rows.append(("噪音", self.noise_display()))
        rows.append(("在售 SKU", self.sku_count_display()))
        return rows

    # 由 pagemap 在配对时注入，使 compare_rows() 能按"两方交集"出行。
    _pair_partner = None

    def set_pair_partner(self, other):
        """登记对比伙伴，供 compare_rows() 判定共同可比的字段集。"""
        self._pair_partner = other
        return self

    # ------------------------------------------------------------ M4 用
    def carton_display(self):
        """外箱尺寸（去掉"…条/箱"尾巴，那是每箱数量列的内容）。"""
        if is_missing(self.carton_mm):
            return MISSING, True
        s = re.split(r"[，,]", self.carton_mm)[0].strip()
        s = s.replace(" ", "").replace("x", "×").replace("X", "×")
        s = re.sub(r"^(\d[\d.]*(?:×\d[\d.]*)+)(cm|mm)", r"\1 \2", s)
        return cjk_latin_space(s), False

    def gross_weight_display(self):
        """单箱毛重（v6「单箱毛重 kg」）。"""
        if is_missing(self.carton_kg):
            return MISSING, True
        v = self.carton_kg.strip()
        return cjk_latin_space(v if v.endswith("kg") else f"{v} kg"), False

    def per_carton_display(self):
        """每箱数量（pcs）。"""
        if is_missing(self.per_carton):
            return MISSING, True
        return self.per_carton.strip(), False

    def moq_plain(self):
        """起订量（v6 MOQ）。"""
        if is_missing(self.moq):
            return MISSING, True
        return self.moq.strip(), False


def load_all(path=None):
    """读取 v6 清单。返回 (有序 Sku 列表, {型号: Sku})。

    `by_model` 每个型号只留**首行**（与打样期口径一致，M2 单品页取代表行）；
    合并组的全部行请用 `group_members()` 取。
    """
    root = os.path.dirname(HERE)
    path = path or os.path.join(root, "input", CSV_NAME)
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("型号") or "").strip():
                rows.append(Sku(row))
    by_model = {}
    for s in rows:
        by_model.setdefault(s.model, s)
    return rows, by_model


def pick(rows, model):
    """按 v6 权威型号取一条（合并组返回首行，与打样口径一致）。"""
    for s in rows:
        if s.model == model:
            return s
    raise KeyError(f"v6 清单中找不到型号 {model!r}")


def group_members(rows, page_key):
    """取出同一「入册页组」的全部行（独立单品页返回单行）。"""
    out = [s for s in rows if s.page_key == page_key]
    if not out:
        raise KeyError(f"v6 清单中找不到页组 {page_key!r}")
    return out


def catalog_stats(rows):
    """M4 右栏数据块的权威口径。

    打样页 M4 写的是 SPU 23 / SKU 108 / SPU PAGES 19。前两项**由数据算出**，
    不写死：SPU = 清单行数；SKU = 「在售SKU数」列求和（v6 实测 108）。
    第三项「单品页数」= 独立单品页 + 合并组页数（= 册子里 M2 页的页数），
    由 page_map 给出，故不在此统计。
    """
    total_sku = 0
    for s in rows:
        if not is_missing(s.sku_count):
            try:
                total_sku += int(float(s.sku_count))
            except ValueError:
                pass
    brands = []
    for s in rows:
        b = s.brand.strip()
        if b and b not in brands:
            brands.append(b)
    cats = []
    for s in rows:
        c = s.category.strip()
        if c and c not in cats:
            cats.append(c)
    return {
        "spu": len(rows),
        "sku": total_sku,
        "brands": brands,
        "categories": cats,
        "models": [s.model for s in rows],
    }


def union_rows(members):
    """合并组内"哪一方有实测就取哪一方"的字段并集（用于 M2 合并页参数条）。

    返回 (值, 是否待补) 列表；全组都缺测才写「待补」。
    """
    out = []
    keys = ["power_plain", "voltage_display", "dims_display", "net_weight_display"]
    for k in keys:
        got = None
        for s in members:
            v, missing = getattr(s, k)()
            if not missing:
                got = v
                break
        out.append((got if got is not None else MISSING, got is None))
    return out

