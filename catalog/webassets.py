"""邮件版素材降采样。

印刷版直接使用 300dpi 原生素材（`assets/`）。邮件版面向屏幕阅读与跨境买手
发信，目标是**整册 32P 也压在 10MB 以内**，因此按目标 DPI 重新采样：

* 按**实际版面尺寸 × 目标 DPI** 反算所需像素数，而不是盲目按比例缩放 ——
  素材来源不同（打样裁切 / 后续补拍）时结果一致；
* **绝不放大**：源图分辨率不足时保持原样，避免糊化；
* 照片类转 JPEG（DCTDecode 直接内嵌，ReportLab 不再二次编码，体积最小）；
  线条类 Logo 保留 PNG（无损、且本就只有几 KB）。

生成的副本缓存在 `assets/web/`，与印刷素材分开放，不污染印刷链路。
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")
WEB_DIR = os.path.join(ASSETS, "web")

# 邮件版图片目标分辨率（dpi）。150dpi 是屏幕阅读与家用打印的通用档位，
# 相对印刷版 300dpi 约减重 75%。
WEB_DPI = 150
JPEG_QUALITY = 82

_cache = {}


def _is_line_art(path):
    """线条/文字类素材保留 PNG 无损，避免 JPEG 振铃。

    两类命中：
    * 文件名含 `logo`（品牌标）；
    * **认证标识目录**（`certmarks/`）—— 法定图形，JPEG 振铃会模糊轮廓，
      属于合规风险；且本就不大，无损代价可忽略。
    """
    p = path.replace("\\", "/").lower()
    if "certmarks/" in p:
        return True
    return "logo" in os.path.basename(path).lower()


def downsample_for(src_path, target_w_mm, target_h_mm, dpi=WEB_DPI,
                   quality=JPEG_QUALITY):
    """返回适合邮件版的素材路径。

    src_path      源图（印刷素材）
    target_w_mm   该图在版面上的实际放置宽
    target_h_mm   该图在版面上的实际放置高
    两者用于反算"目标 DPI 下真正需要的像素数"。
    """
    if not src_path or not os.path.exists(src_path):
        return src_path

    key = (os.path.abspath(src_path), round(target_w_mm, 2),
           round(target_h_mm, 2), dpi, quality)
    if key in _cache:
        return _cache[key]

    stem = os.path.splitext(os.path.basename(src_path))[0]
    line_art = _is_line_art(src_path)
    ext = ".png" if line_art else ".jpg"
    dst = os.path.join(WEB_DIR, f"{stem}@{dpi}dpi{ext}")

    if not os.path.exists(dst):
        os.makedirs(WEB_DIR, exist_ok=True)
        with Image.open(src_path) as im:
            im = im.convert("RGBA" if line_art else "RGB")
            sw, sh = im.size
            # 目标 DPI 下真正需要的像素数
            need_w = max(1, int(round(target_w_mm / 25.4 * dpi)))
            need_h = max(1, int(round(target_h_mm / 25.4 * dpi)))
            # 按比例缩到"刚好覆盖所需像素"，绝不放大
            scale = min(need_w / sw, need_h / sh, 1.0)
            if scale < 1.0:
                im = im.resize((max(1, int(sw * scale)), max(1, int(sh * scale))),
                               Image.LANCZOS)
            if line_art:
                im.save(dst, "PNG", optimize=True)
            else:
                im.convert("RGB").save(dst, "JPEG", quality=quality,
                                       optimize=True, progressive=True)
    _cache[key] = dst
    return dst


def clear_cache():
    """清掉已生成的邮件版素材（重建时用）。"""
    _cache.clear()
    if os.path.isdir(WEB_DIR):
        for f in os.listdir(WEB_DIR):
            os.remove(os.path.join(WEB_DIR, f))


if __name__ == "__main__":
    import sys
    print(f"邮件版素材目录：{WEB_DIR}")
    if os.path.isdir(WEB_DIR):
        for f in sorted(os.listdir(WEB_DIR)):
            p = os.path.join(WEB_DIR, f)
            print(f"  {os.path.getsize(p) / 1024:8.1f} KB  {f}")
    else:
        print("  （尚未生成）")
