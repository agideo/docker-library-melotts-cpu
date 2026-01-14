from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from melo.api import TTS
import hashlib
import os
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ==================== 配置区 ====================

MAX_TEXT_LENGTH = 500
THREAD_POOL_SIZE = 4

# ==================== 全局状态 ====================

tts_model = None
executor = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)

# ==================== 核心函数 ====================

def load_model() -> TTS:
    """加载中文 TTS 模型（CPU版本）"""
    print("[模型加载] 开始加载中文 TTS 模型 (CPU)...", file=sys.stderr)
    try:
        model = TTS(language='ZH', device='cpu')
        print("[模型加载] 模型加载成功", file=sys.stderr)
        return model
    except Exception as e:
        print(f"[模型加载] 模型加载失败: {e}", file=sys.stderr)
        raise


def get_model() -> TTS:
    """获取 TTS 模型（单例模式）"""
    global tts_model
    if tts_model is None:
        tts_model = load_model()
    return tts_model


def generate_audio_file(text: str, speed: float) -> str:
    """生成语音文件"""
    model = get_model()
    content_hash = hashlib.md5(f"{text}_{speed}".encode()).hexdigest()
    output_file = f"/tmp/tts_{content_hash}.wav"
    speaker_id = model.hps.data.spk2id['ZH']

    model.tts_to_file(
        text=text,
        speaker_id=speaker_id,
        output_path=output_file,
        speed=speed
    )
    return output_file


def delete_file(filepath: str):
    """删除临时文件"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"[清理] 已删除临时文件: {filepath}", file=sys.stderr)
    except Exception as e:
        print(f"[清理] 删除文件失败: {filepath}, 原因: {e}", file=sys.stderr)

# ==================== API 接口 ====================

app = FastAPI(title="MeloTTS 中文语音服务 (CPU)")


@app.on_event("startup")
def startup_event():
    """服务启动时预加载模型"""
    print("[启动] 预加载 TTS 模型...", file=sys.stderr)
    get_model()
    print("[启动] 模型加载完成，服务就绪", file=sys.stderr)


@app.post("/tts")
async def text_to_speech(request: dict):
    """
    文字转语音 API

    请求体:
        {
            "content": "你好世界",
            "speed": 1.0
        }
    """
    content = request.get("content", "")
    speed = request.get("speed", 1.0)

    # 参数校验
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="参数 content 不能为空")

    if len(content) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail=f"文本过长，最多 {MAX_TEXT_LENGTH} 字")

    if not 0.5 <= speed <= 2.0:
        raise HTTPException(status_code=400, detail="speed 必须在 0.5-2.0 之间")

    try:
        loop = asyncio.get_event_loop()
        audio_file = await loop.run_in_executor(
            executor,
            generate_audio_file,
            content,
            speed
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音生成失败: {str(e)}")

    return FileResponse(
        path=audio_file,
        media_type="audio/wav",
        background=BackgroundTask(delete_file, audio_file)
    )


@app.get("/health")
def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "model_loaded": tts_model is not None,
        "device": "cpu",
        "thread_pool_size": THREAD_POOL_SIZE
    }


@app.get("/")
def root():
    """服务首页"""
    return {
        "service": "MeloTTS 中文语音服务",
        "version": "1.0",
        "device": "cpu",
        "usage": 'POST /tts with JSON: {"content": "你好世界", "speed": 1.0}'
    }
