from openai import AsyncOpenAI
import os
import io

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class AudioProcessor:
    async def speech_to_text(self, audio_bytes: bytes) -> str:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.webm"

        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en"
        )
        return transcript.text.strip()

    async def text_to_speech(self, text: str) -> bytes:
        response = await client.audio.speech.create(
            model="tts-1",
            voice="onyx",
            input=text,
            response_format="mp3"
        )
        return response.content
