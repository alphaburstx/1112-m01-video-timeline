# 离线视频工程：起始材料

这是空实现基线，只有工程契约、样例与确定性素材生成器，没有剪辑、规划或渲染实现。Python 3、ffmpeg 和 ffprobe 已安装，只用 Python 标准库组织调用。

先运行 `python3 generate_media.py --output media`。生成五个小 MOV，总视频时长 14 秒，视频为 H.264（含 B 帧），有音轨的源为 PCM；`media/manifest.json` 保存每个文件的 SHA-256、生成参数与实际探测结果。相同环境可重复生成相同输入；不要求跨 FFmpeg 版本编码字节相同。

请实现入口：

```
python3 render.py --project examples/main.json --output-dir output/main
```

项目的 source 相对工程文件所在目录。成功输出目录有 `plan.json`、`master.mkv`（FFV1/yuv420p、单声道 PCM s16le 48000Hz）和 `preview.mp4`（H.264/AAC），并以退出码 0 报告完成。失败退出码非零，stderr 给出 JSON 路径和具体原因；同目录已有成功成品须保持字节不变。允许提供额外启动参数，但此入口必须可用。为可控验证编码失败，FFmpeg/ffprobe 可执行路径分别从环境变量 `M01_FFMPEG`/`M01_FFPROBE` 读取，未设置时使用 PATH 中的命令。

CONTRACT.md 固定时间语义、适配与边界；examples/main.json 覆盖混合素材，另有无转场音画偏移样例、恰好半格点与错误工程。生成器和样例可保留，程序结构自行决定。README 请补上实际运行过的命令、核验方式和限制。不要把“FFmpeg 成功退出”当作成片时间线正确的证明。
