# 方案C 画册排版 —— 32P 全册（MARS-9 阶段B 放量版）

依据 **方案C设计系统规范 v1.0** + MARS-11 阶段A 页型/页序引擎，接图库出
**32P 全册双 PDF**（印刷版 + 邮件版）。阶段A 的页型说明见 MARS-11 交付贴，
本 README 只记放量期改动的构建方式。

---

## 一键构建

在 `workdir` 目录下执行：

```bat
set GALLERY_ROOT=%CD%\gallery
build.cmd
```

`GALLERY_ROOT` 指向解包后的图库（MARS-9 工单附件
`产品画册图片_20260929.zip`）。未设置时 A7/TBK06 回落到打样裁切件，
其余型号走"待补产品主图"占位。

也可以直接用 Python：

```bat
python catalog\build.py                        :: 32P 全册，两版都出
python catalog\build.py --samples              :: 每页型出 1~2 页样张
python catalog\build.py --variant print        :: 只出印刷版
python catalog\build.py --variant email        :: 只出邮件版
python catalog\build.py --prepare-fonts        :: 仅重建字体实例
python -m unittest discover -s tests           :: 页序引擎 20 项单测
```

数据：`input\SKU素材收集模板_v6.csv`（唯一权威版，`data.py` 单点引用）。

### 产物（双版本）

| 文件 | 说明 |
|---|---|
| `output\print\*.pdf`（32 页） | **印刷版** 303×216mm（A4 横版 + 3mm 出血），300dpi 素材，字体内嵌，交印厂 |
| `output\print\合订本_print.pdf` | 印刷版合订本（32 页） |
| `output\email\*.pdf`（32 页） | **邮件版** 297×210mm（成品尺寸，无出血），150dpi 素材，整册 <10MB |
| `output\email\合订本_email.pdf` | 邮件版合订本（32 页） |
| `output\_build.json` | 本批次构建清单（版本、页码、体积、notes） |
| `output\_selfcheck.json` | 交付前自检报告（551 项） |

---

## 放量期改动（MARS-9 阶段B，2026-09-29）

1. **主图接入**（`build.py`）：`resolve_image()` 单点接 `GALLERY_ROOT`，
   按 v6「现有主图文件」列的**文件名**检索（目录名陷阱：`XCQ-AW-2` 实际
   目录 `AW-02-1`、`XCQ-CR208-` 有独立目录、`XCQ-V12` 内是 P16 图——
   一律不按目录名猜）。选图清单 `PICKED_MAIN` 集中可改。
2. **C 级"待补重拍"占位**（`build.py` `C_GRADE_MODELS`）：PBK05、CR208、
   LEST-C2、J1D、V9、P12 六型号强制占位（图库现存图均为 733–800px 或
   需重抠，不入册）。
3. **对比表 token 完整性**（`fonts.py` `wrap_cjk` 重写 + `fits_unwrapped`；
   `m3.py`/`m2merged.py` 接入）：拉丁/数字 token（`50/60Hz`、
   `43.7×25.3×18.5`）不可断；整 token 装不下列宽时**降字号**（9→8pt 下限），
   再按空格断行。修 MARS-11 验收必修项。
4. **合并页列序**（`pagemap.py` `_sort_by_config_tag`）：按 v6「中文品名」
   配置号自然序（配置1→4），修 P.17 列序 4/3/1/2。
5. **YJZ-001 Coming Soon**（`data.py` `coming_soon` + `m2.py`）：v6 备注
   "瑜伽砖单品页只写 Coming Soon"——左栏卖点与参数条让位于占位表达。
6. **自检新增**（`selfcheck.py` `check_no_token_split`）：全册扫描
   "同列上下相邻行拼出被切断的值 token"，防回归。
7. **目录索引单列**（`m4.py` `draw_index_content`）：23 条按页码升序单列，
   行距仍 §1.3 body 5.2mm（框高自然贴合，无新增设计常量）。
8. **官方认证标识接入**（`catalog/certmarks.py` + `assets/certmarks/`）：
   见下节。

## 官方认证标识（`assets/certmarks/`）

**口径：只有官方原件才入册；取不到就走纯文本。绝不手绘或位图描摹。**

| 标 | 状态 | 来源 / 说明 |
|---|---|---|
| **CE** | ✅ 官方件已入册 | 欧委会官方包（矢量 `CE.eps`/`CE.ai` + 位图 `CE.png`），构型依 Reg. (EC) No 765/2008 Annex II |
| FCC | ⏳ 待取 | fcc.gov 在本构建机返回 403；现按纯文本渲染 |
| PSE | ⏳ 待取 | meti.go.jp 返回 403；菱形/圆形形态见 `certmarks.PSE_FORM_*` 开关 |
| UL | ⏳ 待取 | UL LLC 注册商标，图纸须向 UL 索取 |
| ETL | ⏳ 待取 | Intertek 注册商标，图纸须向 Intertek 索取（画册最小宽度 25mm） |

- 图件来源与 SHA-256 记在 `assets/certmarks/_manifest.json`，`selfcheck.py`
  的 `check_certmark_policy` 逐条复验（清单声明 official 的文件必须在位且
  hash 一致；pending 的标不得解析出图件，防手绘冒充）。
- 置入用官方位图（ReportLab 不置入 EPS）；**矢量原件随包保留交印厂**，
  经 `certmarks.vector_masters()` 取。
- 图形模式由 `draw_badges(..., graphics=True)` 显式开启；当前仅
  **P.03 品牌总览 / P.04 认证体系页**开启，14 个单品页徽章行保持文本
  （等 A/B 拍板）。
- 认证标识在邮件版**不降采样、不转 JPEG**（`webassets._is_line_art`
  把 `certmarks/` 视为线条稿），避免振铃模糊法定图形轮廓。

## 页序（page_map 单点定义在 `catalog/pagemap.py`）

M1×2 + M4×4 + M2×19（17 独立 + CR208/AW-2 合并）+ M3×7 = 32，页码 P.01–P.32。
改页序只动 `PAGE_MAP` 一处；目录页（P.02）数据驱动自动跟随。
