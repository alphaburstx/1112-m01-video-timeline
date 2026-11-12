# 工程契约 v1

## 输入与时间原点

JSON 顶层为 `version:1`、`output`、`clips`；未知字段须拒绝。output 含正偶数 width/height、正有理数字符串 fps、sample_rate=48000、background=`#RRGGBB`。clips 为非空列表，每项含 source、source_in、source_out、speed、gain_db、fit、transition_out。时间、速度均用十进制整数或 `整数/正整数` 字符串，不接受 float、NaN 或无穷；in>=0、out>in，speed 在 [1/4,4]。gain_db 为 [-60,12] 的 JSON 数值，fit 为 contain 或 cover。

source_in/out 的 0 是该源**最早可解码展示视频帧的 PTS**，不是容器 start_time，也不是各音轨单独的 0。使用首个视频、首个音轨；音频早于视频的部分裁去，晚开始的部分补静音，保留双方的相对 PTS。仅截取半开区间 [in,out)，out 不得超过实际最后视频帧 PTS 加该帧展示时长。须探测记录容器起点、视频 PTS、音频起点和范围，使用展示顺序处理 B 帧和 VFR。

## 全局计划与格点

所有时间线决定使用精确有理数。第 i 段持续 d=(out-in)/speed；第一段 start=0、end=d；后段 start=前段 end-前段 transition_out.duration，end=start+d。transition_out 为 {type:cut,duration:"0"} 或 {type:dissolve|wipe_left,duration:正有理数}。最后段只能 cut；任一段入转场长度+出转场长度不得大于自身 d，相等允许。

格点映射固定为 Q_r(t)=floor(t*r+1/2)，恰好半格向正方向。先计算所有全局有理数边界，再各自映射；不能逐段取整后相加。输出视频帧数 N=Q_fps(最终 end)，音频样本数 S=Q_48000(最终 end)。两条流分别结束，master 不用 shortest 截掉尾部，也不人为补齐到另一条流；最终帧展示到 N/fps，音频到 S/48000，二者差最多半帧加半样本。所有离散范围为 [Q(start),Q(end))。正转场映射后若不足 2 帧或 2 样本，编码前拒绝。

视频第 n 帧的名义全局时刻为 n/fps；各片段仅在其映射后的帧范围内活动。活动片段的源采样时刻为 in+(n/fps-start)*speed，超出截取区间时夹到最近的合法时刻；源帧取 PTS 不大于该时刻的最后展示帧，末帧保持到 out。不得把 VFR 帧号当恒定帧率。音频对应全局 s/48000，按相同源时间关系变速；保持音高，gain_db 在变速后应用，无音轨精确补静音。允许保音高算法造成最多 40ms 的局部脉冲展宽/位移，禁止累计音画漂移；无变速脉冲误差应在 128 样本内。

## 图像和声音转场

先应用源样本宽高比和显示旋转，再等比适配。contain 居中补背景色，cover 居中裁切；样例覆盖竖屏与非方形像素。输出 yuv420p。转场区间 [右片段 start,左片段 end)；映射后 m 帧中第 k 帧的进度 w=k/(m-1)，首帧全左、末帧全右。dissolve=(1-w)*左+w*右；wipe_left 中右片段从画面右侧向左覆盖，在像素 x/(width-1)>=1-w 时取右片段，w=0 特例全左。视频量化或缩放差异允许少量像素误差，方向与端点不能变。

所有非 cut 转场音频用等功率混合：映射后的 m 个样本中第 k 个样本 w=k/(m-1)，左权重 cos(pi*w/2)，右权重 sin(pi*w/2)。转场外只保留对应片段音频。不要用额外淡入淡出掩盖偏移。响度不能超限时可拒绝，样例不应触发此拒绝。

## 输出、诊断与原子发布

plan.json 至少包含 `version`、`output`（含 fps/sample_rate）、`duration`、`video_frames`、`audio_samples`、`clips`。时间以约分的有理数字符串记录；每段含 source、source_in/out、speed、start/end、start_frame/end_frame、start_sample/end_sample 和 transition_out（type、duration、start/end 及其帧/样本边界）。cut 也记录同点的零长度边界。附录可记录输入探测信息和命令，不以这些自报统计替代解码验收。

非法 JSON、缺失/损坏源、超范围截取、非法速率/尺寸/转场必须在调用编码器前失败。允许调用 ffprobe 或 FFmpeg 解码预检。给出如 `$.clips[1].source_out` 的路径。所有成品先写临时区域，编码及解码核验成功后发布。已有 output-dir 在任一步骤失败时其成功文件须逐字节保持；预览编码失败也属于失败。允许使用同目录备份与回滚实现多文件发布，不要求操作系统级跨文件原子事务。

观看用 MP4 可以为了播放器兼容处理末端不足一帧的差异，数值验收只读取无损 master.mkv。成功报告记录实际命令、帧数和样本数。提供独立读取工程和解码输出的自检脚本，涵盖长度、单调 PTS、关键转场帧、脉冲、静音与错误路径；同时说明实际运行证据和平台限制。
