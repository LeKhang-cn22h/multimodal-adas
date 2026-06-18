import os
import sys
import logging
import io
import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from transformers import pipeline
from pydub import AudioSegment


'''
api giong noi
url /ttsVoice

request param toStream : bool
input json 
{
    "text_input"
}

respone: neu toStream laf true, respone tra ve la cac byte am thanh, 
neu la false thi tra ve file mp3
'''

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
os.environ["HF_HUB_DISABLE_HTTP2"] = "1"
os.environ["HF_HOME"] = "./HF_Cache"

# ---------------------------------------------------------
# 1. Core TTS Class
# ---------------------------------------------------------
class VoiceSynth:
    def __init__(self):

        self.synthesiser = pipeline("text-to-speech", model="facebook/mms-tts-vie")
        
    def tts_array(self, text_input: str) -> tuple[np.ndarray, int]:
        speech = self.synthesiser(text_input)
        audio_array = speech["audio"]
        sample_rate = speech["sampling_rate"]
        
        audio_data = np.squeeze(audio_array)
        # Convert to int16 for standard audio processing compatibility
        audio_data_int16 = (audio_data * 32767).astype(np.int16)
        
        return audio_data_int16, sample_rate

# Global variable to hold model instance
voice_model = None

# ---------------------------------------------------------
# 2. Application Lifespan Management
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager to handle startup and shutdown events.
    This replaces the deprecated @app.on_event("startup").
    """
    global voice_model
    logger.info("Initializing application and loading AI models...")
    try:
        # Initialize the model once and keep it in memory
        voice_model = VoiceSynth()
        logger.info("MMS-TTS model loaded successfully.")
    except Exception as e:
        # Log the critical error and kill the app immediately
        logger.critical(f"Failed to load the TTS model. Terminating application. Error: {str(e)}")
        sys.exit(1)
        
    yield # The application runs while yielding here
    
    # Clean up resources on shutdown if necessary
    logger.info("Application shutting down...")
    voice_model = None

# Initialize FastAPI with the lifespan manager
app = FastAPI(lifespan=lifespan)

# ---------------------------------------------------------
# 3. API Schemas & Endpoints
# ---------------------------------------------------------
class TTSRequest(BaseModel):
    # This defines the expected JSON body structure
    text_input: str

@app.post("/ttsVoice")
async def tts_voice(
    request: TTSRequest, 
    toStream: bool = Query(..., description="Set to true for raw byte stream, false for MP3 file")
):
    """
    Endpoint to generate text-to-speech audio.
    """
    text = request.text_input.strip()
    
    # 400 Bad Request: Validate input data
    if not text:
        raise HTTPException(status_code=400, detail="The 'text_input' field cannot be empty.")
    
    if voice_model is None:
        raise HTTPException(status_code=503, detail="TTS Model is not available.")

    try:
        # Generate the audio array
        audio_data, sample_rate = voice_model.tts_array(text)
        
        if toStream:
            # Create a generator function to stream raw bytes chunk by chunk
            def raw_byte_generator():
                yield audio_data.tobytes()
            
            # Return raw binary stream
            return StreamingResponse(
                raw_byte_generator(), 
                media_type="application/octet-stream"
            )
            
        else:
            # Convert raw array to MP3 entirely in-memory
            
            # Step 1: Write raw array to an in-memory WAV buffer using soundfile
            wav_io = io.BytesIO()
            sf.write(wav_io, audio_data, sample_rate, format='WAV', subtype='PCM_16')
            wav_io.seek(0) # Reset pointer to the start of the buffer
            
            # Step 2: Use pydub to convert the WAV buffer to an MP3 buffer
            audio_segment = AudioSegment.from_wav(wav_io)
            mp3_io = io.BytesIO()
            audio_segment.export(mp3_io, format="mp3")
            mp3_io.seek(0)
            
            # Return the file response
            return StreamingResponse(
                mp3_io, 
                media_type="audio/mpeg", 
                headers={"Content-Disposition": f"attachment; filename=output.mp3"}
            )
            
    except Exception as e:
        # 500 Internal Server Error: Catch processing failures
        logger.error(f"Error processing TTS request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during audio generation.")

if __name__ == "__main__":
    import uvicorn
    # Run the server on port 8000
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)