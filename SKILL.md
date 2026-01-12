# MD 文件 → ListenHub → 小宇宙 Skill

将 Markdown 文件转换为播客音频，并自动上传到小宇宙平台。

## 功能

1. **解析 MD 文件** - 提取备选标题和正文内容
2. **生成音频** - 使用 ListenHub API 将文本转为语音
3. **自动上传** - 使用 Playwright 自动上传到小宇宙

## 配置

### 必需配置

在 `md_to_podcast.py` 中配置以下内容：

```python
# ListenHub API Key
LISTENHUB_API_KEY = "your_api_key"

# 小宇宙播客 ID
PODCAST_ID = "your_podcast_id"

# 音色映射表
VOICE_MAPPING = {
    "王永威声音": "voice-clone-6963b6553821bc6abf722b28",
}
```

### 当前配置

| 配置项 | 值 |
|--------|-----|
| ListenHub API Key | `lh_sk_6963b6933fccf...` |
| 播客 ID | `6963b4d73c5a03c6a6c4e031` |
| 音色 | 王永威声音 |

## MD 文件格式

```markdown
## 备选标题
这里是播客节目的标题

## 正文
这里是正文内容，将被转换为音频...
```

## 使用方法

### 1. 安装依赖

```bash
pip install requests playwright
playwright install chromium
```

### 2. 首次运行（登录小宇宙）

```bash
python md_to_podcast.py your_episode.md
```

首次运行时会打开浏览器，需要手动登录小宇宙。登录信息会保存到 `~/.xiaoyuzhou_browser_data`，后续运行自动保持登录。

### 3. 运行

```bash
# 使用默认音色
python md_to_podcast.py episode.md

# 指定音色
python md_to_podcast.py episode.md "王永威声音"
```

## 技术说明

- **浏览器持久化**: 使用 `launch_persistent_context` 保存登录状态
- **上传按钮定位**: 点击"点击上传音频"文字上方 40px
- **复选框定位**: 点击"阅读并同意"文字左侧 25px

## 故障排除

### 音色 speakerId 未配置

```
ValueError: 音色 'XXX' 的 speakerId 为空
```

在 `VOICE_MAPPING` 中填入正确的 speakerId。

### 需要重新登录

删除浏览器数据目录后重新运行：

```bash
rm -rf ~/.xiaoyuzhou_browser_data
python md_to_podcast.py episode.md
```
