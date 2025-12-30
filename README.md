# 视频文案提取工具
链接/账号/本地视频 → 抽音频 → ASR → 文本后处理 → Word/Excel/SRT 交付文件。

## 功能

- 解析抖音分享链接获取无水印视频信息，支持抖音文案提取，哔哩哔哩文案提取
- ASR：抖音链接走 DashScope URL；本地/哔哩哔哩走 qwen-audio-asr
- 可选摘要生成（LLM）
- Word/Excel 按交付名称命名
- SRT 导出（带时间轴）
- Web 端任务队列、进度展示、历史批次
- 账号主页采集（Playwright 滚动抓取）
- 使用阿里云百炼平台api调用模型

## 环境准备

- Python >= 3.10
- ffmpeg 已安装并在 PATH 中

```bash
ffmpeg -version
```

## 安装依赖

```bash
pip install -r requirements.txt
```

若使用账号采集功能，需要安装 Playwright 浏览器：

```bash
playwright install
```

## 配置

复制 `.env` 并填写：

```
DASHSCOPE_API_KEY=sk-xxxxxxxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ASR_MODEL=paraformer-v2
LLM_MODEL=qwen-plus
ASR_MODE=auto
AUDIO_ASR_MODEL=qwen-audio-asr
```

## 命令行使用

### 1) 处理链接文件

```bash
python -m src.main --name "客户A_账号xxx" --links links.txt --export docx xlsx
```

`links.txt` 一行一个链接。

### 2) 导出 SRT

```bash
python -m src.main --name "客户A_账号xxx" --links links.txt --export srt
```

### 3) 账号主页采集

```bash
python -m src.main --name "客户A_账号xxx" --uid "<uid-or-profile-url>" --count 50
```

`--count 0` 表示尽量采集全部。

### 4) 处理本地视频

```bash
python -m src.main --name "客户A_账号xxx" --inputs /path/to/a.mp4 /path/to/b.mp4
```

### 5) B站链接

```bash
python -m src.main --name "客户A_账号xxx" --platform bilibili --links bilibili_links.txt
```

## Web 使用

```bash
uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

浏览器打开 `http://localhost:8000`。

Web 支持：
- 账号/链接/文件输入
- 任务队列与进度页
- 历史批次与下载
- SRT/摘要选项

## 输出说明

输出目录：`outputs/<日期>_<交付名称>/`

文件命名：  
- `<交付名称>.docx`  
- `<交付名称>.xlsx`  
- `video_1.srt`、`video_2.srt` ...

Excel 列：  
序号 / 视频标题 / 链接 / 发布时间 / 时长 / 文案 / 摘要(可选) / 关键词(可选)

## 数据流架构图

```
输入(链接/UID/本地视频)
  ├─ 账号采集(Playwright) → 链接列表
  └─ 直接输入链接/文件
           │
           v
    解析分享链接 → 无水印视频URL + 标题/时间/时长
           │
           v
      下载视频(mp4)
           │
           v
   ffmpeg 抽音频(16k wav)
           │
           v
  ASR
     ├─ 抖音URL直传（DashScope paraformer-v2）
     └─ 本地/哔哩哔哩（qwen-audio-asr）
           │
           v
     文本清洗/断句
           │
           ├─ 可选摘要(qwen-plus)
           │
           v
 Word/Excel/SRT 交付文件
```

## 接口调用时序图

```
User/CLI/Web
   │
   ├─(1) 解析分享链接
   │      ├─ GET 分享短链
   │      └─ GET https://www.iesdouyin.com/share/video/{id}
   │
   ├─(2) 下载视频
   │      └─ GET 无水印视频URL
   │
   ├─(3) 抽音频
   │      └─ ffmpeg 本地处理
   │
   ├─(4) ASR
   │      ├─ 抖音URL直传
   │      │     ├─ async_call(model=paraformer-v2, file_urls=[video_url])
   │      │     └─ wait(task_id) -> transcription_url -> GET 结果JSON
   │      └─ 本地/哔哩哔哩
   │            └─ qwen-audio-asr（MultiModalConversation, file://path）
   │
   └─(5) 可选摘要
          └─ POST /chat/completions (model=qwen-plus)
```

## ASR 模式说明

`ASR_MODE=auto` 默认策略：  
- 抖音分享链接：URL 直传  
- 本地/哔哩哔哩：audio-asr

可选值：  
- `dashscope-url`  
- `audio-asr`

## Audio-ASR（本地/哔哩哔哩）

如果没有公网 URL，可以使用 `ASR_MODE=audio-asr`，走 `qwen-audio-asr` 识别本地文件：

```
AUDIO_ASR_MODEL=qwen-audio-asr
ASR_MODE=audio-asr
```

## 常见问题

1) 采集账号视频很慢  
   - 这是 Playwright 渲染+下滑导致，可考虑后续改为接口采集

2) ffmpeg not found  
   - 安装 ffmpeg 并保证在 PATH 中

3) Web 只能 localhost 访问  
   - 用 `--host 0.0.0.0` 启动，并确保防火墙开放端口
