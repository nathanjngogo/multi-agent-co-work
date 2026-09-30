# 工具脚本（保留供回归复现）

这些脚本是本轮反推打样基准、并做交付前核对的工具，物化保留以便复现。

| 脚本 | 用途 |
|---|---|
| `extract_assets.py` | 从打样基准 PDF 原位裁切素材（300dpi 原生像素），写入 `assets/` |
| `pixeldiff.py` | 逐元素像素级对照：把基准页与产出页换算到同一成品坐标系，报告落位偏差 |
| `make_compare.py` | 生成三张人眼对照图（印刷版vs基准 / 邮件版vs基准 / 印刷版vs邮件版） |
| `list_fonts.py` | 列出 `fonts/static/` 每个实例的 wght 与 PostScript 名（查字重折叠） |
| `verify_fix.py` | 列出交付 PDF 内嵌的字体面及各自 wght（查字重折叠） |
| `stroke_width.py` | 按经理判据量笔画宽中位数，与母版 0.339mm 对照 |
| `tier_check.py` | 逐 span 列出每个版位实际用的字体面（验证三档分工） |
| `selfcheck.py` | 交付前自检（由 `catalog/build.py` 自动调用） |
| `run.cjs` | Multica CLI 调用包装（本沙箱禁止原生命令管道，用文件描述符重定向替代） |
| `exec.cjs` | 通用命令调用包装（同上） |
| `pip.cjs` | pip 包装（沙箱的临时目录权限限制绕行） |

## 回归流程

```bat
python catalog\build.py                   :: 重新构建两版 + 自检
python pixeldiff.py                       :: 与打样基准逐元素比对 → pixeldiff_out.txt
python make_compare.py                    :: 生成对照图 output\对照_*.png
```

`pixeldiff.py` 里 `REGIONS` 定义了参与比对的版位（成品坐标 mm）**及其水平锚点**。
新增版式元素时在此登记对应区域，即可纳入回归。

锚点决定判据：左对齐元素比左沿、居中元素比中心。拿居中元素的左沿去比基准，
会把"文案更短"误报成"版式错位" —— 这正是 `caption` / `param_bar` 的锚点要标
`center` 的原因。

## 关于 0.5mm 级残余偏差

`pixeldiff.py` 现在把偏差分成两类报告：

- **落位偏差**（判据 ≤0.5mm）—— 版式正确性
- **宽度偏差**（仅参考）—— 文案长度差异，因打样页用 UI 手写原型稿、本实现按
  v5 权威清单取数

实测落位最大偏差 ≤0.98mm，且残余部分已定位为**字体替换副作用**：两版笔位
完全相同，只是替代字体（Bahnschrift）的数字字形左边距比基准字体大 ~0.5mm。
换装规范指定的拉丁字体后此项归零。

## 字重回归排查（重要）

若怀疑字重被折叠（整册偏粗 / 内嵌字体只有一款中文面），按此顺序查：

```bat
python list_fonts.py     :: fonts/static/ 每个实例的 wght 与 PostScript 名
python verify_fix.py     :: 交付 PDF 内嵌了哪些字体面、各自 wght
python stroke_width.py   :: 按经理判据量笔画宽，与母版 0.339mm 对照
python tier_check.py     :: 每个版位实际用的字体面
```

判定标准：

- `fonts/static/` 里每个逻辑字重的 **PostScript 名必须唯一**；
- 交付 PDF 里中文应出现 **3 个**不同 wght 的面（600 / 500 / 400）；
- 任一环节只有 1 个中文面 → 字重已折叠，重跑
  `python catalog/build.py --prepare-fonts --force`（该命令负责写唯一 name 表）。

`fonts/static/` 下的字体**必须**由 `--prepare-fonts` 生成；手工放入的字体
没有唯一 name，会直接触发折叠。
