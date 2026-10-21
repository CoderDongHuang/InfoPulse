"""Real OpenAI SDK contracts against a local transport, without paid credentials."""
import base64
import json
import unittest
from unittest.mock import patch

import httpx
from openai import AsyncOpenAI

from app.config import get_settings
from app.core import llm
from app.core.model_compat import chat_options
from app.core.runtime_settings import use_settings
from app.services import multimodal


class QwenModelsTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_and_vision_disable_default_thinking_and_send_correct_models(self):
        calls = []
        def respond(request):
            body = json.loads(request.content)
            calls.append((str(request.url), request.headers['authorization'], body))
            content = '{"summary":"visible text","ocr":[]}' if body['model'] == 'qwen3-vl-plus' else 'OK'
            return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0,
                "model": body['model'], "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}]})
        def factory():
            return AsyncOpenAI(api_key='qwen-private-fixture', base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
                max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
        config = get_settings().model_copy(update={'LLM_API_BASE': 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'LLM_MODEL': 'qwen-plus'})
        with use_settings(config), patch.object(llm, 'get_llm_client', side_effect=factory), patch.object(multimodal, 'client', side_effect=factory):
            self.assertEqual(await llm.complete_chat('system', 'hello'), 'OK')
            self.assertEqual((await multimodal.vision(b'image', 'image/png', 'qwen3-vl-plus'))['summary'], 'visible text')
        self.assertEqual([x[2]['model'] for x in calls], ['qwen-plus', 'qwen3-vl-plus'])
        for url, key, body in calls:
            self.assertEqual(url, 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
            self.assertEqual(key, 'Bearer qwen-private-fixture')
            self.assertIs(body['enable_thinking'], False)
        self.assertEqual(chat_options('https://api.deepseek.com/v1', 'deepseek-chat'), {})
        self.assertEqual(chat_options('https://dashscope.aliyuncs.com.evil.example/v1', 'qwen-plus'), {})

    async def test_qwen_asr_uses_chat_audio_and_does_not_fabricate_timestamps(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion', 'created': 0,
                'model': 'qwen3-asr-flash', 'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '你好，世界'}}]})
        sdk = AsyncOpenAI(api_key='test', base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
            max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
        config = get_settings().model_copy(update={'MEDIA_TRANSCRIPTION_PROTOCOL': 'qwen_asr'})
        with use_settings(config), patch.object(multimodal, 'client', return_value=sdk):
            result = await multimodal.transcribe(b'RIFF-audio', 'test.wav', 'qwen3-asr-flash')
        self.assertTrue(sdk.is_closed())
        self.assertEqual(requests[0].url.path, '/compatible-mode/v1/chat/completions')
        body = json.loads(requests[0].content)
        self.assertEqual(body['asr_options'], {'enable_itn': False})
        audio = body['messages'][0]['content'][0]['input_audio']['data']
        self.assertEqual(audio, 'data:audio/wav;base64,' + base64.b64encode(b'RIFF-audio').decode())
        self.assertEqual(result[0]['text'], '你好，世界')
        self.assertIsNone(multimodal.transcript_locator(result[0])['start_ms'])
        self.assertIsNone(multimodal.transcript_locator(result[0])['end_ms'])

    async def test_qwen_rejects_oversize_and_wrong_api_models_before_sending(self):
        config = get_settings().model_copy(update={'MEDIA_TRANSCRIPTION_PROTOCOL': 'qwen_asr'})
        with use_settings(config), patch.object(multimodal, 'client') as factory:
            for data, name, model in [(b'a' * 8_000_000, 'a.wav', 'qwen3-asr-flash'),
                (b'a', 'a.wav', 'qwen3-asr-flash-filetrans'), (b'a', 'a.webm', 'qwen3-asr-flash')]:
                with self.assertRaises(ValueError):
                    await multimodal.transcribe(data, name, model)
            factory.assert_not_called()

    async def test_openai_transcription_retains_real_segments(self):
        def respond(request):
            self.assertEqual(request.url.path, '/v1/audio/transcriptions')
            self.assertIn(b'whisper-1', request.content)
            return httpx.Response(200, json={'text': 'real text', 'segments': [{'start': 1.2, 'end': 3.5, 'text': 'real text'}]})
        sdk = AsyncOpenAI(api_key='test', base_url='https://api.example.com/v1', max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
        config = get_settings().model_copy(update={'MEDIA_TRANSCRIPTION_PROTOCOL': 'openai'})
        with use_settings(config), patch.object(multimodal, 'client', return_value=sdk):
            result = await multimodal.transcribe(b'audio', 'a.wav', 'whisper-1')
        self.assertEqual(multimodal.transcript_locator(result[0])['start_ms'], 1200)
        self.assertEqual(multimodal.transcript_locator(result[0])['end_ms'], 3500)
