# Emotion Parsing and Live2D Integration

## Overview
This document describes the emotion parsing system that automatically extracts emotion tags from LLM responses and drives Live2D model expressions. The system parses the leading `[Emotion]` tag from assistant messages, applies the corresponding expression to the avatar, and automatically resets to a default emotion after 5 seconds.

## Architecture

### Backend Changes

#### LLM Client (`backend/llm_client.py`)
The `LLMClient.stream()` method now yields structured events instead of raw text:

```python
async def stream(self, user_text: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream events from the LLM while parsing the leading [Emotion] tag.
    
    Yields structured events:
    - {"type": "emotion", "emotion": str}
    - {"type": "text", "data": str}
    """
```

**Key Changes:**
- Parses the first `[Emotion]` tag from the LLM response
- Validates the emotion against allowed emotions from the model configuration
- Falls back to default emotion (prefers "Happy") if the parsed emotion is invalid
- Emits a single `emotion` event followed by `text` events containing only the message content
- Removes the emotion tag from the displayed text

**Event Flow:**
1. **Emotion Event**: `{"type": "emotion", "emotion": "Happy"}` - emitted once per response
2. **Text Events**: `{"type": "text", "data": "Hello there!"}` - repeated for each text chunk

#### WebSocket Server (`backend/server.py`)
The WebSocket handler now processes structured events from the LLM client:

```python
async for event in llm.stream(user_text):
    try:
        if isinstance(event, dict):
            et = event.get("type")
            if et == "emotion":
                await websocket.send_text(json.dumps({"type": "emotion", "emotion": event.get("emotion")}))
            elif et == "text":
                data = event.get("data")
                if data:
                    await websocket.send_text(json.dumps({"type": "chunk", "data": data}))
```

**Protocol Changes:**
- New message type: `{"type": "emotion", "emotion": string}`
- Existing `{"type": "chunk", "data": string}` now contains only the text content (no emotion tag)
- Maintains backward compatibility with existing start/end/error message types

### Frontend Changes

#### Event Bus (`frontend/src/events.ts`)
Added a centralized event bus for cross-component communication:

```typescript
// Central event bus for cross-component communication
export const appEvents = new EventTarget()

export type EmotionEventDetail = { label: string }
```

**Purpose:**
- Decouples ChatPanel from Live2D component
- Allows for future expansion to other components
- Maintains clean separation of concerns

#### Chat Panel (`frontend/src/components/ChatPanel.tsx`)
Enhanced to handle emotion events and maintain debug logging:

**New Features:**
- Listens for `{"type": "emotion"}` WebSocket messages
- Dispatches `emotion` events to the event bus
- Maintains a raw buffer that includes the emotion tag for debugging
- Logs the complete raw assistant output (including emotion tag) to console on completion

**Event Handling:**
```typescript
if (msg.type === 'emotion') {
  // Broadcast emotion to Live2D component
  if (msg.emotion && typeof msg.emotion === 'string') {
    appEvents.dispatchEvent(new CustomEvent('emotion', { detail: { label: msg.emotion } }))
    // Keep raw transcript with the tag for debugging
    pendingRawRef.current += `[${msg.emotion}] `
  }
  return
}
```

**Debug Logging:**
```typescript
if (msg.type === 'end') {
  setStreaming(false)
  // Debug: print full raw output with emotion tag intact
  if (pendingRawRef.current) {
    console.log('[Assistant raw]', pendingRawRef.current)
  }
  return
}
```

#### Live2D Component (`frontend/src/components/Live2D.tsx`)
Enhanced to respond to emotion events and manage expression lifecycle:

**New Features:**
- Listens for `emotion` events from the event bus
- Maps emotion labels to expression IDs using the model's emotion configuration
- Applies expressions immediately when received
- Automatically resets to default emotion after 5 seconds
- Handles race conditions where emotion events arrive before the model is ready

**Emotion Event Handling:**
```typescript
const onEmotion = async (evt: Event) => {
  const detail = (evt as CustomEvent).detail as { label?: string } | undefined
  const label = (detail?.label || '').trim()
  if (!label) return

  // If sprite not ready yet, queue the emotion
  if (!spriteRef.current) {
    pendingEmotionRef.current = label
    return
  }

  await applyExpressionByLabel(label)

  // Reset to default after 5 seconds
  if (emotionResetTimerRef.current) window.clearTimeout(emotionResetTimerRef.current)
  emotionResetTimerRef.current = window.setTimeout(async () => {
    const defLabel = defaultEmotionRef.current
    await applyExpressionByLabel(defLabel)
  }, 5000)
}
```

**Expression Application:**
The component uses a three-tier fallback system to apply expressions:

1. **Public API**: `spriteRef.current?.setExpression({ expressionId: exprId })`
2. **Internal Manager**: Direct access to the model's expression manager
3. **Lazy Loading**: Loads expression files from disk if not already registered

**Race Condition Handling:**
- Maintains a `pendingEmotionRef` for emotions received before the model is ready
- Once the model and emotion options are available, applies any pending emotions
- Uses refs to avoid stale closure issues in event listeners

## Data Flow

### Complete Flow Example
1. **User Input**: "How are you feeling today?"
2. **Backend Processing**:
   - LLM generates: `[Happy] I'm feeling great today! How about you?`
   - `LLMClient.stream()` parses and emits:
     - `{"type": "emotion", "emotion": "Happy"}`
     - `{"type": "text", "data": "I'm feeling great today! How about you?"}`
3. **WebSocket Transmission**:
   - `{"type": "emotion", "emotion": "Happy"}`
   - `{"type": "chunk", "data": "I'm feeling great today! How about you?"}`
4. **Frontend Processing**:
   - ChatPanel receives emotion event, dispatches to event bus
   - Live2D receives emotion event, applies "Happy" expression
   - ChatPanel displays only the text content (no emotion tag)
   - After 5 seconds, Live2D resets to default emotion
5. **Debug Output**: Console shows `[Assistant raw] [Happy] I'm feeling great today! How about you?`

## Configuration

### Model Emotion Mapping
The system relies on the emotion mapping defined in `vtuber.config.json`:

```json
{
  "models": {
    "ellot": {
      "emotions": {
        "Happy": "exp_03",
        "Sad": "exp_02",
        "Annoyed": "exp_09"
      }
    }
  }
}
```

**Requirements:**
- Emotion labels must match exactly (case-insensitive matching in the frontend)
- Expression IDs must correspond to actual `.exp3.json` files in the model
- The system will fall back to the first available emotion if "Happy" is not found

### Default Behavior
- **Default Emotion**: Prefers "Happy", falls back to first available emotion
- **Auto-reset Timer**: 5 seconds (configurable in the component)
- **Fallback Handling**: Gracefully handles missing expressions and invalid emotions

## Debugging

### Console Logging
The system provides comprehensive debug information:

1. **Raw Output Logging**: Each completed assistant response is logged with the emotion tag intact
2. **Event Flow**: Emotion events are logged when dispatched to the event bus
3. **Expression Application**: Failed expression applications are caught and logged

### Common Issues and Solutions

**Avatar Not Changing Emotions:**
1. Check browser console for `[Assistant raw]` logs to verify emotion parsing
2. Verify emotion labels in `vtuber.config.json` match the LLM output
3. Ensure expression files exist in the model's runtime directory
4. Check that the model has loaded completely before emotion events arrive

**Emotions Not Resetting:**
1. Verify the default emotion exists in the model's emotion mapping
2. Check for JavaScript errors in the console
3. Ensure the timeout is not being cleared prematurely

**Race Conditions:**
1. The system automatically queues emotions received before model readiness
2. Check that `pendingEmotionRef` is being processed once the model loads
3. Verify emotion options are properly loaded from configuration

## Future Enhancements

### Potential Improvements
1. **Configurable Reset Timer**: Make the 5-second reset configurable per model
2. **Emotion Transitions**: Add smooth transitions between expressions
3. **Emotion Persistence**: Allow certain emotions to persist longer
4. **Emotion Combinations**: Support for complex emotional states
5. **Performance Monitoring**: Track expression application success rates

### Integration Opportunities
1. **Voice Synthesis**: Sync emotions with speech patterns
2. **Gesture System**: Coordinate expressions with body language
3. **Context Awareness**: Adjust emotion duration based on conversation context
4. **User Preferences**: Allow users to customize emotion behavior

## Testing

### Manual Testing
1. **Start the application** and wait for the model to load completely
2. **Send a message** that should trigger an emotional response
3. **Observe the avatar** for expression changes
4. **Check the console** for debug output
5. **Wait 5 seconds** to verify auto-reset functionality

### Automated Testing Considerations
1. **WebSocket Mocking**: Mock the WebSocket server for unit tests
2. **Event Bus Testing**: Test emotion event dispatch and handling
3. **Expression Validation**: Verify expression application success
4. **Timer Testing**: Test auto-reset functionality with mocked timers

This emotion parsing system provides a robust foundation for creating emotionally responsive virtual characters while maintaining clean separation between the LLM response processing and the visual expression system.
