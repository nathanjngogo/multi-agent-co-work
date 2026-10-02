# -*- coding: utf-8 -*-
"""生成 v7 清单（江楠 2026-10-02 回填资料）并给 data.py 打补丁。

v7 = v6 + 江楠《待补资料填写表》里的数据，逐格可追。新增三列：
  吸力kPa / 续航min / 配色数
（吸力与续航原来是靠"卖点文案正则"抠出来的，额定值与营销文案必须分开，
 故 v7 起改由专门列供数，data.py 优先读列、列空才回落正则。）

用法：python make_v7.py
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(HERE, "input")
V6 = os.path.join(IN, "SKU素材收集模板_v6.csv")
V7 = os.path.join(IN, "SKU素材收集模板_v7.csv")

NEW_COLS = ["吸力kPa", "续航min", "配色数"]

# (型号, 中文品名) → {列: 新值}
EDITS = {
    ("A7", "吸尘器A7"): {
        "噪音dB": "60dB", "吸力kPa": "9", "续航min": "50", "配色数": "2",
        "核心卖点1（中文·短句）": "9kPa大吸力·50分钟长续航",
    },
    ("LP005-White", "吸尘器LP005"): {
        "在售SKU数": "2", "噪音dB": "60dB", "吸力kPa": "7", "续航min": "20",
        "配色数": "2",
        "电压制式": "100-240V 50/60Hz（日规/欧规）",
    },
    ("P11", "吸尘器P11"): {
        "噪音dB": "75dB", "吸力kPa": "32", "续航min": "65", "配色数": "1",
        "规制/颜色摘要（已填·请核对）": "日规/欧规/美规/常规；电机类型：无刷",
    },
    ("P12", "吸尘器P12"): {
        "噪音dB": "65dB", "吸力kPa": "17", "续航min": "65", "配色数": "1",
    },
    ("P16", "吸尘器P16"): {
        "净重/毛重 kg": "3 / 待补", "噪音dB": "65dB", "吸力kPa": "20",
        "续航min": "60", "配色数": "2",
    },
    ("V16", "吸尘器V16"): {
        "在售SKU数": "1", "噪音dB": "75dB", "吸力kPa": "30", "续航min": "60",
        "配色数": "1",
        "核心卖点1（中文·短句）": "400W大功率，1.67m³/min超大风量",
    },
    ("J1D", "吸尘器J1D"): {
        "在售SKU数": "2", "噪音dB": "65dB", "吸力kPa": "13", "续航min": "30",
        "配色数": "2",
    },
    ("CR208", "吸尘器CR208有刷"): {
        "噪音dB": "60dB", "吸力kPa": "12", "续航min": "60", "配色数": "6",
        "核心卖点1（中文·短句）": "12kPa/150W强吸·60分钟长续航",
    },
    ("CR208", "吸尘器CR208无刷"): {
        "噪音dB": "75dB", "吸力kPa": "26", "续航min": "40", "配色数": "6",
    },
    ("AW-2", "吸尘器AW-2-配置1"): {
        "噪音dB": "75dB", "吸力kPa": "9", "续航min": "40", "配色数": "4",
        "核心卖点1（中文·短句）": "9kPa+150W电机，全屋40分钟",
    },
    ("AW-2", "吸尘器AW-2-配置2"): {
        "噪音dB": "75dB", "吸力kPa": "12", "续航min": "40", "配色数": "4",
        "核心卖点1（中文·短句）": "12kPa+150W电机，全屋40分钟",
    },
    ("AW-2", "吸尘器AW-2-配置3"): {
        "噪音dB": "75dB", "吸力kPa": "12", "续航min": "40", "配色数": "4",
        "核心卖点1（中文·短句）": "12kPa+150W电机，全屋40分钟",
    },
    ("AW-2", "吸尘器AW-2-配置4"): {
        "噪音dB": "75dB", "吸力kPa": "32", "续航min": "60", "配色数": "4",
        "核心卖点1（中文·短句）": "32kPa超强吸力，400W无刷电机",
        "核心卖点2（中文·短句）": "60分钟长续航+LED电量屏显",
    },
    ("GT3", "洗地机-GT3"): {
        "噪音dB": "75dB", "吸力kPa": "12", "续航min": "40", "配色数": "1",
        "核心卖点3（中文·短句）": "干湿12kPa双吸40分钟，防缠毛",
    },
    ("BVC-T8", "洗地机T8"): {
        "噪音dB": "75dB", "吸力kPa": "16", "续航min": "30", "配色数": "1",
        "规制/颜色摘要（已填·请核对）": "单SKU/无变体；规格：欧规；颜色：白色；电机类型：无刷",
        "核心卖点2（中文·短句）": "干湿两用16kPa吸力，吸拖一遍过",
    },
    ("LEST-C2", "蒸汽清洗机LEST-C2"): {
        "噪音dB": "60dB", "配色数": "1",
        "规制/颜色摘要（已填·请核对）": "美规/欧规/英规；颜色：黑色；电机类型：无电机",
    },
    ("V9", "布艺机V9"): {
        "配色数": "1",
        "规制/颜色摘要（已填·请核对）": "日规/欧规；颜色：白色；电机类型：有刷干湿电机",
    },
    ("MS21N-001", "烘被机"): {
        "噪音dB": "60dB", "配色数": "1",
    },
    # 4 款瑜伽垫 + 瑜伽砖：无噪音参数（江楠 10-02）
    ("PBK05", "瑜伽垫PU-05"): {"噪音dB": "非电器——无噪音参数", "配色数": "1"},
    ("PMR04", "瑜伽垫PU-04"): {"噪音dB": "非电器——无噪音参数", "配色数": "1"},
    ("TBK06", "瑜伽垫TPE-06"): {"噪音dB": "非电器——无噪音参数", "配色数": "1"},
    ("TBK08", "瑜伽垫TPE-08"): {"噪音dB": "非电器——无噪音参数", "配色数": "1"},
    ("YJZ-001", "瑜伽砖"): {"噪音dB": "非电器——无噪音参数", "配色数": "1"},
}

# 备注列追加一行来源说明（逐行标注，便于回溯）
NOTE_ADD = "｜2026-10-02 江楠回填（v7）"


def main():
    with open(V6, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        rows = list(rd)
        cols = list(rd.fieldnames)
    cols = cols + NEW_COLS
    log = []
    used = set()
    for r in rows:
        key = (r["型号"].strip(), r["中文品名"].strip())
        ed = EDITS.get(key)
        for c in NEW_COLS:
            r.setdefault(c, "")
        if not ed:
            continue
        used.add(key)
        for c, new in ed.items():
            old = r.get(c, "")
            if old != new:
                log.append((key[0], key[1], c, old, new))
            r[c] = new
        r["备注"] = (r.get("备注", "") + NOTE_ADD).strip()
    missing = [k for k in EDITS if k not in used]
    assert not missing, f"EDITS 未命中：{missing}"
    with open(V7, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"v7 写出：{V7}（{len(rows)} 行 × {len(cols)} 列）")
    print(f"逐格改动 {len(log)} 处：")
    for m, n, c, o, x in log:
        print(f"  {m:<12} {c:<22} {o!r} → {x!r}")
    # 口径 C / SKU 合计
    elec, nonelec, sku = {}, {}, 0
    for r in rows:
        if not (r["在售SKU数"] or "").strip():
            continue
        m = r["型号"].strip()
        try:
            sku += int(float(r["在售SKU数"]))
        except ValueError:
            pass
        n = r["配色数"].strip()
        n = int(n) if n.isdigit() else 1
        tgt = nonelec if "非电器" in (r["额定功率W"] or "") else elec
        tgt[m] = max(tgt.get(m, 0), n)
    spu_c = sum(v * 3 for v in elec.values()) + sum(nonelec.values())
    print(f"\n口径 C（型号 × 颜色 × 插头制式）："
          f"电器 {len(elec)} 型号 ×3 + 非电器 {len(nonelec)} 型号 ×1")
    print("  电器配色：" + ", ".join(f"{k}={v}" for k, v in sorted(elec.items())))
    print(f"  → SPU(口径C) = {spu_c}；在售 SKU 合计 = {sku}")


if __name__ == "__main__":
    main()