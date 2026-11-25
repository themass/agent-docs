"""provider 实现：fake（默认可跑通全链路）+ 真实模型的挂载点。

选型口径（Android ``docs/design/2026-11-24-try-on-and-avatar-licensing.md``）：
真人照片做风格化只能用 **OpenRAIL 系动漫检查点**（animagine-xl-3.1 / waifu-diffusion
+ lcm-lora）， licence 允许合成派生发布。本任务不下载、不集成大模型——默认 provider
是一个确定性的轻量变换，把「接口 / 配额 / 清理」先用 fake 钉绿；真实 provider 的
挂载点只有这里一个（``settings.avatar_gen_provider`` 选实现），见 ``real_provider``。
"""

from __future__ import annotations

import io
import logging

from companion.service.avatar_gen.port import AnimeStyleProvider

log = logging.getLogger("companion.avatar_gen")

FAKE_PROVIDER_NAME = "fake"


class FakeStyleProvider:
    """确定性的轻量变换：JPEG 重编码 + 灰边框。无重依赖、无网络，测试全程用它。

    它存在的意义不是「出图好看」，而是把契约钉死：输入源图字节，输出**另一份**可被
    上传管线再处理的 JPEG（正常走 ``UploadService.accept`` 入库）。边框让「结果确实
    经过 provider」在字节层面可验证（不是原样回拷）。
    """

    name = FAKE_PROVIDER_NAME

    async def generate(self, *, image: bytes, style: str) -> bytes:
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(image)) as img:
            img = img.convert("RGB")
            # 头像最终是圆形裁切展示：方边 + 居中方形裁切，预览阶段就能看出构图。
            side = max(img.size)
            canvas = Image.new("RGB", (side, side), (24, 24, 27))
            offset = ((side - img.width) // 2, (side - img.height) // 2)
            canvas.paste(img, offset)
            bordered = ImageOps.expand(canvas, border=max(4, side // 40), fill=(88, 132, 255))
        out = io.BytesIO()
        bordered.save(out, format="JPEG", quality=88)
        return out.getvalue()


def real_provider(settings) -> AnimeStyleProvider | None:
    """真实模型的挂载点。**本任务刻意不实现**：不下载检查点、不起推理进程。

    接线时要同时满足的清单（缺一条就宁可继续用 fake）：
    1. 检查点只能选 OpenRAIL 动漫系（animagine-xl-3.1 / waifu-diffusion），
       加速用 lcm-lora——许可口径见上面的 licensing 文档；
    2. 推理进程是独立的（专用 GPU 机上的 HTTP 端点或本机 systemd 服务），
       **不在 API 进程里养模型**：120s 的同步生成会占死一个 worker；
    3. 这里返回的 provider 负责调用那个端点并把结果解码成 JPEG 字节；
       失败抛异常即可，服务层统一收敛成 provider_failed（502）。

    配置入口已经留好：``COMPANION_AVATAR_GEN_PROVIDER``。取值不是 "fake" 而这里给不出
    实现时**拒绝启动**（fail-closed），不能悄悄退回 fake——用户会拿到一张带边框的
    原始自拍当二次元头像，且没有任何地方报错。
    """
    name = (getattr(settings, "companion_avatar_gen_provider", FAKE_PROVIDER_NAME) or FAKE_PROVIDER_NAME).strip()
    if name in ("", FAKE_PROVIDER_NAME):
        return FakeStyleProvider()
    raise RuntimeError(
        f"COMPANION_AVATAR_GEN_PROVIDER={name!r} 还没有实现（真实模型接线未落地）。"
        f"改回 fake 或补上 {__name__}.real_provider 的实现。"
    )
