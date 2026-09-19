from 恢复稳定域边界数据 import 主程序 as 恢复数据
from 生成来源哈希清单 import 主程序 as 生成来源哈希
from 第4章绘图核心 import 生成全部图片
from 验收第4章交付物 import 验收


if __name__ == "__main__":
    生成来源哈希()
    恢复数据()
    生成全部图片()
    验收()
    print("第4章5张图片已重建并通过章节验收。")
