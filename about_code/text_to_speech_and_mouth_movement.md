# Text-to-Speech and Mouth Movement Integration

## Overview
This document describes the implementation of text-to-speech (TTS) synthesis and synchronized mouth movement for the VTuber system. The backend generates audio from LLM responses using an external TTS service, and the frontend plays the audio while triggering a "Mouth Move" expression for the duration of playback.

## Architecture

### Backend TTS Integration (`backend/server.py`)

#### Configuration Loading
- **TTS Settings**: Added TTS configuration to `load_llm_config()` with environment variable overrides:
  - `TTS_HOST`: TTS service endpoint (default: `https://tts.tarunravi.com`)
  - `TTS_MODEL`: TTS model name (default: `kokoro`)
  - `TTS_SPEED`: Speech speed multiplier (default: `1.0`)
  - `TTS_LANG_CODE`: Language code (default: `en-US`)

- **Model-Specific Voice**: Each model in `vtuber.config.json` now includes a `ttsVoice` field:
  ```json
  {
    "models": {
      "ellot": {
        "ttsVoice": "af_heart",
        "emotions": { ... }
      },
      "mao": {
        "ttsVoice": "af_heart", 
        "emotions": { ... }
      }
    }
  }
  ```

#### TTS Synthesis Function
```python
async def synthesize_tts(
    client: httpx.AsyncClient,
    *,
    host: str,
    model: str,
    text: str,
    voice: str,
    response_format: str = "mp3",
    speed: float = 1.0,
    lang_code: str = "en-US",
) -> bytes:
```
- Calls external TTS service at `{host}/v1/audio/speech`
- Returns raw MP3 audio bytes
- Handles errors gracefully without breaking chat functionality

#### WebSocket Audio Event
- **Event Order**: After streaming text and emotion classification, the backend:
  1. Synthesizes TTS audio for the complete assistant response
  2. Sends `{"type": "audio", "format": "mp3", "data": "<base64>"}` event
  3. Sends the complete text as a single chunk (synchronized with audio)
  4. Sends `{"type": "end"}` event

- **Synchronization**: Text streaming is buffered during LLM generation and only sent after TTS synthesis completes, ensuring text appears simultaneously with audio playback.

### Frontend Audio Playback (`frontend/src/components/ChatPanel.tsx`)

#### Audio Event Handling
```typescript
if (msg.type === 'audio') {
  try {
    if (msg.data) {
      const mime = msg.format === 'wav' ? 'audio/wav' : 'audio/mpeg'
      const audio = new Audio(`data:${mime};base64,${msg.data}`)
      let durationMs = 0
      
      audio.onloadedmetadata = () => {
        if (Number.isFinite(audio.duration) && audio.duration > 0) {
          durationMs = Math.round(audio.duration * 1000)
        }
      }
      
      audio.onplay = () => {
        const detail = { label: 'Mouth Move', durationMs: durationMs > 0 ? durationMs : undefined }
        appEvents.dispatchEvent(new CustomEvent('mouth', { detail }))
      }
      
      audio.play().catch(() => {})
    }
  } catch {}
  return
}
```

- **Audio Creation**: Creates an `Audio` element from base64 data URI
- **Duration Extraction**: Extracts audio duration from `onloadedmetadata` event
- **Mouth Event Dispatch**: Dispatches a `mouth` event with duration when audio starts playing

### Event Bus (`frontend/src/events.ts`)
Added new event type for mouth movement coordination:
```typescript
export type MouthEventDetail = { label: string; durationMs?: number }
```

### Live2D Mouth Movement (`frontend/src/components/Live2D.tsx`)

#### Mouth Event Handler
```typescript
const onMouth = async (evt: Event) => {
  const detail = (evt as CustomEvent).detail as { label?: string; durationMs?: number } | undefined
  const label = (detail?.label || 'Mouth Move').trim()
  const durationMs = typeof detail?.durationMs === 'number' && detail!.durationMs! > 0 ? detail!.durationMs! : 3000
  
  if (!spriteRef.current) return

  await applyExpressionByLabel(label)

  if (mouthTimerRef.current) window.clearTimeout(mouthTimerRef.current)
  mouthTimerRef.current = window.setTimeout(async () => {
    const defLabel = defaultEmotionRef.current
    await applyExpressionByLabel(defLabel)
  }, durationMs)
}
```

- **Expression Application**: Applies the "Mouth Move" expression immediately
- **Timed Reset**: Automatically reverts to default emotion after audio duration
- **Timer Management**: Cleans up timers on component unmount

#### Timer Management
- Added `mouthTimerRef` to track mouth movement timeout
- Proper cleanup in component unmount to prevent memory leaks

## Model-Specific Mouth Movement

### Ellot Model
- **Expression File**: `assets/models/ellot/runtime/expressions/exp_mouth_move.exp3.json`
- **Parameter**: `ParamMouthOpenY` (vertical mouth opening)
- **LipSync Group**: Configured in `ellot.model3.json` for programmatic control

### Mao Model  
- **Expression File**: `assets/models/mao_pro/runtime/expressions/exp_mouth_move.exp3.json`
- **Parameter**: `ParamA` (vowel shape)
- **LipSync Group**: Configured in `mao_pro.model3.json` for phoneme-based control

## Configuration Updates

### vtuber.config.json
Both models now include:
```json
{
  "models": {
    "ellot": {
      "ttsVoice": "af_heart",
      "emotions": {
        "Mouth Move": "exp_mouth_move",
        // ... existing emotions
      }
    },
    "mao": {
      "ttsVoice": "af_heart", 
      "emotions": {
        "Mouth Move": "exp_mouth_move",
        // ... existing emotions
      }
    }
  }
}
```

### Model Files
- Added `exp_mouth_move` expression references to both `*.model3.json` files
- Frontend public model updated via `frontend/scripts/sync-assets.mjs`

## Data Flow

### Complete TTS Flow
1. **User Input**: User sends message via WebSocket
2. **LLM Processing**: Backend streams LLM response tokens
3. **Text Buffering**: Text is buffered but not sent to frontend yet
4. **TTS Synthesis**: Backend calls external TTS service with complete response
5. **Audio Event**: `{"type": "audio", "format": "mp3", "data": "<base64>"}` sent
6. **Text Delivery**: Complete text sent as single chunk (synchronized with audio)
7. **Frontend Playback**: Audio plays and triggers mouth movement
8. **Mouth Animation**: "Mouth Move" expression applied for audio duration
9. **Reset**: Expression reverts to default emotion

### Event Sequence
```
WebSocket: {"type": "start"}
WebSocket: {"type": "audio", "format": "mp3", "data": "<base64>"}
WebSocket: {"type": "chunk", "data": "Complete assistant response..."}
WebSocket: {"type": "emotion", "emotion": "Happy"}
WebSocket: {"type": "end"}
```

## Error Handling

### Backend TTS Failures
- TTS errors don't break chat functionality
- Audio events are optional; chat continues without speech
- Graceful fallback to text-only responses

### Frontend Audio Failures
- Audio playback errors are caught and logged
- Mouth movement still triggers even if audio fails
- Default 3-second duration if audio metadata unavailable

## Environment Variables

### TTS Configuration
```bash
TTS_HOST=https://tts.tarunravi.com      # TTS service endpoint
TTS_MODEL=kokoro                        # TTS model name
TTS_SPEED=1.0                          # Speech speed multiplier
TTS_LANG_CODE=en-US                    # Language code
```

### Backend Configuration
```bash
LLM_HOST=http://127.0.0.1:11434        # LLM service host
LLM_MEMORY_TURNS=8                     # Conversation memory turns
LLM_MEMORY_CHARS=4000                  # Conversation memory characters
```

## Future Enhancements

### Advanced Lip Sync
- **Real-time Parameter Driving**: Use WebAudio analyser for amplitude-based mouth movement
- **Phoneme Detection**: Implement phoneme recognition for more accurate mouth shapes
- **Expression Blending**: Smooth transitions between mouth and emotion expressions

### Audio Features
- **Audio Queuing**: Support multiple audio clips in sequence
- **Volume Control**: User-adjustable audio volume
- **Audio Effects**: Pitch shifting, speed control, etc.

### Performance Optimizations
- **Audio Caching**: Cache generated audio to avoid re-synthesis
- **Streaming Audio**: Progressive audio delivery for long responses
- **Background Synthesis**: Pre-generate audio while streaming text

## Testing

### Manual Testing
1. **Start Application**: Run `./start.sh` from project root
2. **Send Message**: Type a message that should generate a response
3. **Verify Audio**: Check that audio plays and mouth moves
4. **Check Synchronization**: Ensure text appears with audio start
5. **Verify Reset**: Confirm mouth returns to default after audio ends

### Debug Information
- Browser console shows audio duration and mouth events
- WebSocket events logged for debugging
- Expression application success/failure logged

## Integration Points

### External TTS Service
- **Endpoint**: `https://tts.tarunravi.com/v1/audio/speech`
- **Format**: JSON request with MP3 response
- **Parameters**: model, input text, voice, speed, language
- **Authentication**: None required (public service)

### Live2D Framework
- **Expression System**: Uses existing expression infrastructure
- **Parameter Access**: Direct access to model parameters for future enhancements
- **Timer Integration**: Leverages existing emotion timer system

This TTS integration provides a foundation for creating more immersive VTuber experiences with synchronized speech and visual feedback.
