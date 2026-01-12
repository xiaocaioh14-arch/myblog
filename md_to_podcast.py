#!/usr/bin/env python3
"""
MD 文件 → ListenHub 生成音频 → 上传小宇宙

将 Markdown 文件转换为播客音频并自动上传至小宇宙平台。

配置说明：
- ListenHub API Key: 在 LISTENHUB_API_KEY 环境变量或代码中设置
- 音色名称: 通过 VOICE_MAPPING 映射到 speakerId
- 小宇宙播客 ID: 在 PODCAST_ID 中设置
"""

import os
import re
import sys
import time
import asyncio
import tempfile
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple

# ==================== 配置 ====================

LISTENHUB_API_KEY = os.getenv(
    "LISTENHUB_API_KEY",
    "lh_sk_6963b6933fccf46ae41b03fa_0e0e6ff39150098b611039bacf88fca63d77648805621463"
)

PODCAST_ID = "6963b4d73c5a03c6a6c4e031"

# 音色映射表：名称 -> speakerId
VOICE_MAPPING = {
    "王永威声音": "voice-clone-6963b6553821bc6abf722b28",
}

# ListenHub API 配置
LISTENHUB_API_BASE = "https://api.marswave.ai/openapi/v1"

# 小宇宙浏览器数据目录
BROWSER_DATA_DIR = os.path.expanduser("~/.xiaoyuzhou_browser_data")

# ==================== 数据类 ====================

@dataclass
class MarkdownContent:
    """解析后的 Markdown 内容"""
    title: str
    content: str
    raw_text: str


# ==================== MD 解析模块 ====================

def parse_markdown(file_path: str) -> MarkdownContent:
    """
    解析 Markdown 文件，提取备选标题和正文。
    
    MD 格式要求：
    ## 备选标题
    标题内容
    
    ## 正文
    正文内容
    
    Args:
        file_path: Markdown 文件路径
        
    Returns:
        MarkdownContent 对象
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()
    
    # 提取备选标题
    title_match = re.search(r'##\s*备选标题\s*\n(.*?)(?=\n##|\Z)', raw_text, re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    
    # 提取正文
    content_match = re.search(r'##\s*正文\s*\n(.*?)(?=\n##|\Z)', raw_text, re.DOTALL)
    content = content_match.group(1).strip() if content_match else ""
    
    if not title:
        print("⚠️ 警告: 未找到 '## 备选标题' 部分")
    if not content:
        print("⚠️ 警告: 未找到 '## 正文' 部分")
    
    return MarkdownContent(title=title, content=content, raw_text=raw_text)


# ==================== ListenHub API 模块 ====================

def get_speaker_id(voice_name: str) -> str:
    """
    根据音色名称获取 speakerId。
    
    Args:
        voice_name: 音色名称
        
    Returns:
        speakerId
        
    Raises:
        ValueError: 如果音色名称不在映射表中或 speakerId 为空
    """
    if voice_name not in VOICE_MAPPING:
        raise ValueError(
            f"音色名称 '{voice_name}' 不在映射表中。\n"
            f"可用的音色: {list(VOICE_MAPPING.keys())}\n"
            f"请在 VOICE_MAPPING 中添加此音色，或提供正确的音色名称。"
        )
    
    speaker_id = VOICE_MAPPING[voice_name]
    if not speaker_id:
        raise ValueError(
            f"音色 '{voice_name}' 的 speakerId 为空。\n"
            f"请在 VOICE_MAPPING 中填入正确的 speakerId。\n"
            f"您可以在 ListenHub 控制台中找到您的音色 ID。"
        )
    
    return speaker_id


def generate_audio_listenhub(text: str, voice_name: str, output_path: Optional[str] = None) -> str:
    """
    使用 ListenHub API 生成音频。
    
    Args:
        text: 要转换为音频的文本
        voice_name: 音色名称
        output_path: 输出文件路径（可选，默认生成临时文件）
        
    Returns:
        生成的音频文件路径
    """
    speaker_id = get_speaker_id(voice_name)
    
    headers = {
        "Authorization": f"Bearer {LISTENHUB_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 使用 /speech 端点直接生成音频
    payload = {
        "scripts": [
            {
                "content": text,
                "speakerId": speaker_id
            }
        ]
    }
    
    print(f"🎙️ 正在调用 ListenHub API 生成音频...")
    print(f"   文本长度: {len(text)} 字符")
    print(f"   音色: {voice_name} (ID: {speaker_id[:30]}...)")
    
    response = requests.post(
        f"{LISTENHUB_API_BASE}/speech",
        headers=headers,
        json=payload,
        timeout=300  # 5分钟超时
    )
    
    if response.status_code != 200:
        raise Exception(f"ListenHub API 错误: {response.status_code}\n{response.text}")
    
    # 处理响应
    result = response.json()
    
    # 检查响应状态
    if result.get("code") != 0:
        raise Exception(f"API 返回错误: {result}")
    
    # 获取音频 URL
    audio_url = result.get("data", {}).get("audioUrl")
    if not audio_url:
        # 尝试从其他字段获取
        audio_url = result.get("audioUrl") or result.get("data", {}).get("url")
    
    if not audio_url:
        raise Exception(f"无法从响应中获取音频 URL: {result}")
    
    # 下载音频文件
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3")
    
    print(f"📥 下载音频文件...")
    audio_response = requests.get(audio_url, timeout=120)
    with open(output_path, 'wb') as f:
        f.write(audio_response.content)
    
    print(f"✅ 音频已生成: {output_path}")
    return output_path


def poll_task_result(task_id: str, max_attempts: int = 60, interval: int = 5) -> str:
    """
    轮询异步任务结果。
    
    Args:
        task_id: 任务 ID
        max_attempts: 最大尝试次数
        interval: 轮询间隔（秒）
        
    Returns:
        音频文件 URL
    """
    headers = {
        "Authorization": f"Bearer {LISTENHUB_API_KEY}",
        "Content-Type": "application/json"
    }
    
    for attempt in range(max_attempts):
        print(f"   轮询任务状态... (尝试 {attempt + 1}/{max_attempts})")
        
        response = requests.get(
            f"{LISTENHUB_API_BASE}/task/{task_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"获取任务状态失败: {response.status_code}")
        
        result = response.json()
        status = result.get("status", "")
        
        if status == "completed":
            return result.get("audio_url", "")
        elif status == "failed":
            raise Exception(f"音频生成失败: {result.get('error', '未知错误')}")
        
        time.sleep(interval)
    
    raise Exception("任务超时")


def test_listenhub_connection() -> bool:
    """测试 ListenHub API 连接"""
    print("🔗 测试 ListenHub API 连接...")
    try:
        headers = {
            "Authorization": f"Bearer {LISTENHUB_API_KEY}",
            "Content-Type": "application/json"
        }
        # 发送一个简单的请求来测试连接
        response = requests.get(
            f"{LISTENHUB_API_BASE}/health",
            headers=headers,
            timeout=10
        )
        print(f"   状态码: {response.status_code}")
        return response.status_code in [200, 401, 403]  # 即使认证失败，连接也是正常的
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False


# ==================== 小宇宙上传模块 ====================

async def upload_to_xiaoyuzhou(
    audio_path: str,
    title: str,
    description: str,
    podcast_id: str = PODCAST_ID
) -> bool:
    """
    使用 Playwright 上传音频到小宇宙。
    
    Args:
        audio_path: 音频文件路径
        title: 节目标题
        description: 节目描述
        podcast_id: 播客 ID
        
    Returns:
        是否上传成功
    """
    from playwright.async_api import async_playwright
    
    # 确保浏览器数据目录存在
    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
    
    print(f"🌐 启动浏览器...")
    print(f"   浏览器数据目录: {BROWSER_DATA_DIR}")
    
    async with async_playwright() as p:
        # 使用持久化上下文保持登录状态
        context = await p.chromium.launch_persistent_context(
            BROWSER_DATA_DIR,
            headless=False,  # 首次需要手动登录
            viewport={"width": 1280, "height": 800},
            locale="zh-CN"
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            # 先去主播后台首页检查登录状态和获取播客列表
            dashboard_url = "https://podcaster.xiaoyuzhoufm.com/dashboard"
            print(f"📍 导航到主播后台: {dashboard_url}")
            await page.goto(dashboard_url, wait_until="networkidle", timeout=60000)
            
            # 检查是否需要登录
            if "login" in page.url.lower():
                print("\n⚠️ 需要登录小宇宙")
                print("   请在浏览器中完成登录...")
                print("   登录完成后，脚本将自动继续")
                
                # 等待用户登录（最多5分钟）
                for _ in range(300):
                    await asyncio.sleep(1)
                    if "login" not in page.url.lower():
                        break
                else:
                    print("❌ 登录超时")
                    return False
                
                # 登录后重新导航到后台
                await page.goto(dashboard_url, wait_until="networkidle", timeout=60000)
            
            print("✅ 已登录")
            await asyncio.sleep(2)
            
            # 尝试获取用户的播客列表
            podcasts = await page.evaluate('''() => {
                const links = document.querySelectorAll('a[href*="/podcasts/"]');
                const result = [];
                links.forEach(a => {
                    const match = a.href.match(/\/podcasts\/([a-f0-9]+)/);
                    if (match) {
                        result.push({
                            id: match[1],
                            text: a.innerText.trim().substring(0, 50),
                            href: a.href
                        });
                    }
                });
                return result;
            }''')
            
            # 去重
            seen_ids = set()
            unique_podcasts = []
            for podcast in podcasts:
                if podcast['id'] not in seen_ids:
                    seen_ids.add(podcast['id'])
                    unique_podcasts.append(podcast)
            
            if unique_podcasts:
                print(f"\n📻 找到 {len(unique_podcasts)} 个播客:")
                for i, podcast in enumerate(unique_podcasts[:5]):
                    print(f"   {i+1}. {podcast['text']} (ID: {podcast['id']})")
                
                # 使用第一个播客或配置的播客
                if podcast_id not in [podcast['id'] for podcast in unique_podcasts]:
                    print(f"\n⚠️ 配置的播客 ID ({podcast_id}) 未找到")
                    podcast_id = unique_podcasts[0]['id']
                    print(f"   使用第一个播客: {podcast_id}")
            else:
                print("\n⚠️ 未找到任何播客，请确保您已在小宇宙创建了播客")
                print("   浏览器将保持打开，请手动操作或按 Ctrl+C 退出")
                await asyncio.sleep(30)
                return False
            
            # 导航到创建节目页面
            upload_url = f"https://podcaster.xiaoyuzhoufm.com/podcasts/{podcast_id}/create/episode?type=hosted"
            print(f"\n📍 导航到创建节目页面: {upload_url}")
            await page.goto(upload_url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(3)
            
            # 检查页面是否正常加载
            page_text = await page.inner_text("body")
            if "找不到" in page_text or "not found" in page_text.lower():
                print("❌ 页面显示播客不存在，请检查播客 ID")
                return False
            
            print("✅ 页面加载完成，开始上传流程...")
            
            # ========== 上传音频文件 ==========
            # 使用 input#upload 直接上传（这是隐藏的文件输入）
            print(f"📁 上传音频文件: {audio_path}")
            file_input = page.locator("input#upload")
            if await file_input.count() > 0:
                await file_input.set_input_files(audio_path)
                print("   ✅ 音频文件已选择")
            else:
                # 备选方案：查找任何 file input
                file_input = page.locator("input[type='file']").first
                if await file_input.count() > 0:
                    await file_input.set_input_files(audio_path)
                    print("   ✅ 音频文件已选择（备选方案）")
                else:
                    print("❌ 未找到上传元素")
                    print("   浏览器将保持打开，请手动上传...")
                    await asyncio.sleep(60)
                    return False
            
            # 等待上传完成（根据文件大小调整等待时间）
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            wait_time = max(10, int(file_size_mb * 2))  # 每 MB 等待 2 秒，最少 10 秒
            print(f"⏳ 等待上传完成... (预计 {wait_time} 秒)")
            await asyncio.sleep(wait_time)
            
            # ========== 填写标题 ==========
            print(f"📝 填写标题: {title}")
            title_input = page.locator('input[placeholder="输入单集标题"]')
            if await title_input.count() > 0:
                await title_input.fill(title)
                print("   ✅ 标题已填写")
            else:
                # 备选方案
                title_input = page.locator('input[placeholder*="标题"]').first
                if await title_input.count() > 0:
                    await title_input.fill(title)
                    print("   ✅ 标题已填写（备选方案）")
                else:
                    print("   ⚠️ 未找到标题输入框，请手动填写")
            
            # ========== 填写描述（Show Notes） ==========
            print(f"📝 填写描述...")
            # 小宇宙使用 Draft.js 富文本编辑器
            desc_editor = page.locator('.public-DraftEditor-content')
            if await desc_editor.count() > 0:
                await desc_editor.click()
                await desc_editor.fill(description[:2000])  # 描述限制
                print("   ✅ 描述已填写")
            else:
                # 备选方案：查找可编辑区域
                editable = page.locator('[contenteditable="true"]').first
                if await editable.count() > 0:
                    await editable.click()
                    await editable.fill(description[:2000])
                    print("   ✅ 描述已填写（备选方案）")
                else:
                    print("   ⚠️ 未找到描述编辑器，请手动填写")
            
            await asyncio.sleep(1)
            
            # ========== 勾选同意条款 ==========
            print("☑️ 勾选同意条款...")
            # 方法1：直接点击包含"阅读并同意"的文本
            agree_text = page.locator("text=阅读并同意")
            if await agree_text.count() > 0:
                await agree_text.click()
                await asyncio.sleep(0.5)
                print("   ✅ 已勾选")
            else:
                # 方法2：使用 bounding box 点击左侧复选框
                agree_container = page.locator('div:has-text("阅读并同意")').last
                if await agree_container.count() > 0:
                    box = await agree_container.bounding_box()
                    if box:
                        await page.mouse.click(box["x"] + 10, box["y"] + box["height"] / 2)
                        await asyncio.sleep(0.5)
                        print("   ✅ 已勾选（通过点击）")
            
            # ========== 点击创建按钮 ==========
            print("🚀 查找创建/发布按钮...")
            # 等待用户确认后再提交
            create_button = page.locator('div:has-text("创建")').last
            publish_button = page.locator('button:has-text("发布")').first
            
            # 先检查创建按钮
            if await create_button.count() > 0 and await create_button.is_visible():
                print("   找到「创建」按钮")
                print("\n" + "=" * 50)
                print("⚠️ 请在浏览器中检查内容无误")
                print("   如需修改，请直接在浏览器中编辑")
                print("   确认无误后，请手动点击「创建」按钮发布")
                print("=" * 50)
                print("\n   脚本将等待 60 秒供您操作...")
                await asyncio.sleep(60)
            elif await publish_button.count() > 0 and await publish_button.is_visible():
                print("   找到「发布」按钮")
                print("\n⚠️ 请在浏览器中检查并点击发布")
                await asyncio.sleep(60)
            else:
                print("   未找到发布按钮，请手动操作")
                await asyncio.sleep(60)
            
            print("✅ 上传流程完成！")
            print("   请检查小宇宙后台确认发布状态")
            
            return True
            
        except Exception as e:
            print(f"❌ 上传失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            await context.close()


# ==================== 主函数 ====================

async def main(md_file: str, voice_name: str = "王永威声音"):
    """
    主函数：将 MD 文件转换为播客并上传。
    
    Args:
        md_file: Markdown 文件路径
        voice_name: 音色名称
    """
    print("=" * 50)
    print("MD 文件 → ListenHub → 小宇宙")
    print("=" * 50)
    
    # 1. 解析 MD 文件
    print("\n📄 步骤 1: 解析 Markdown 文件")
    md_content = parse_markdown(md_file)
    print(f"   标题: {md_content.title[:50]}..." if len(md_content.title) > 50 else f"   标题: {md_content.title}")
    print(f"   正文: {len(md_content.content)} 字符")
    
    # 2. 生成音频
    print("\n🎙️ 步骤 2: 生成音频")
    audio_path = generate_audio_listenhub(md_content.content, voice_name)
    
    # 3. 上传到小宇宙
    print("\n📤 步骤 3: 上传到小宇宙")
    success = await upload_to_xiaoyuzhou(
        audio_path=audio_path,
        title=md_content.title,
        description=md_content.content[:500],  # 描述限制500字符
        podcast_id=PODCAST_ID
    )
    
    if success:
        print("\n🎉 完成！播客已成功上传")
    else:
        print("\n⚠️ 上传可能未完成，请检查小宇宙后台")
    
    return success


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python md_to_podcast.py <markdown文件> [音色名称]")
        print("")
        print("示例:")
        print("  python md_to_podcast.py episode.md")
        print("  python md_to_podcast.py episode.md 王永威声音")
        sys.exit(1)
    
    md_file = sys.argv[1]
    voice_name = sys.argv[2] if len(sys.argv) > 2 else "王永威声音"
    
    if not os.path.exists(md_file):
        print(f"❌ 文件不存在: {md_file}")
        sys.exit(1)
    
    asyncio.run(main(md_file, voice_name))
