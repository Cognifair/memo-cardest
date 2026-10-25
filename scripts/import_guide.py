#!/usr/bin/env python3
"""Print the TXT import tutorial (text + absolute GIF path) for delivery messages."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GIF = ROOT / "references" / "assets" / "import-flow-36b59d.gif"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("导入方式（电脑版 Markji）：")
    print("1. 打开制卡桌面，进入目标牌组")
    print("2. 右上角「批量制卡」→「从文本导入」")
    print("3. 粘贴 TXT，保持 ### / === / --- 默认，先看预览，再点「导入」")
    print()
    if GIF.is_file():
        print(f"![TXT 导入流程]({GIF.as_posix()})")
    else:
        print(f"动图文件缺失：{GIF.as_posix()}；请只发文字步骤并说明图片不可用。")
    print()
    print("单张卡片正文上限 5000 字符；整份牌组的 TXT 导入没有总量限制，可以一次导入。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
