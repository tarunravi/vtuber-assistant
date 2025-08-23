# How Live2D is Rendered in This Codebase

## Overview
This codebase implements a Live2D virtual character renderer using React, PixiJS, and the `easy-live2d` library. The system renders Live2D models (.model3 files) in a web browser with proper scaling, positioning, and responsive behavior.

## Architecture Overview

### Frontend Structure
- **Location**: `vtuber/frontend/`
- **Framework**: React 19 + TypeScript + Vite
- **Rendering Engine**: PixiJS 8.12.0
- **Live2D Library**: `easy-live2d` 0.4.0-1

## Core Rendering Flow

### 1. Application Entry Point
**File**: `vtuber/frontend/src/main.tsx`
- Initializes React application
- Sets up StrictMode for development

### 2. Main App Component
**File**: `vtuber/frontend/src/App.tsx`
- Simple wrapper that renders the Live2D component
- No additional logic or state management

### 3. Live2D Component (Core Logic)
**File**: `vtuber/frontend/src/components/Live2D.tsx`

#### Key Features:
- **Start Button**: User must click "Start" to initialize the renderer
- **Canvas Management**: Uses React refs to manage HTML canvas element
- **PixiJS Application**: Creates and manages PixiJS Application instance
- **Live2D Sprite**: Initializes Live2D model using `easy-live2d` library
- **Responsive Scaling**: Automatically scales model to fit viewport
- **Window Resize Handling**: Maintains proper scaling on window resize

#### Technical Implementation:
```typescript
// PixiJS Application setup
app = new Application()
await app.init({ view, backgroundAlpha: 0, resizeTo: window })

// Live2D Sprite initialization
sprite = new Live2DSprite()
await sprite.init({ modelPath: cfg.entry, ticker: Ticker.shared })

// Responsive scaling logic
const resize = () => {
  const w = app.renderer.width
  const h = app.renderer.height
  const sx = w / (sprite.width || 1)
  const sy = h / (sprite.height || 1)
  const s = Math.min(sx, sy) * 0.9
  sprite.scale.set(s)
  sprite.x = w / 2
  sprite.y = h / 2
  // Center anchor
  if (sprite.anchor && typeof sprite.anchor.set === 'function') 
    sprite.anchor.set(0.5, 0.5)
}
```

### 4. Configuration Management
**File**: `vtuber/frontend/public/app-config.json`
- **Content**: `{"model":"mao","entry":"/model/mao_pro.model3.json"}`
- **Purpose**: Specifies which model to load and its entry point
- **Generated**: Automatically created by asset sync script

### 5. Asset Synchronization
**File**: `vtuber/frontend/scripts/sync-assets.mjs`

#### Purpose:
- Synchronizes model assets from source to public directory
- Generates app-config.json based on root configuration
- Supports multiple models (mao, shizuku)

#### Model Mapping:
```javascript
const modelMap = {
  mao: {
    src: '/Users/tarun/Anime/vtuber/assets/models/mao_pro/runtime',
    entry: 'mao_pro.model3.json'
  },
  shizuku: {
    src: '/Users/tarun/Anime/vtuber/assets/models/shizuku/runtime',
    entry: 'shizuku.model3.json'
  }
}
```

#### Sync Process:
1. Reads root configuration from `vtuber.config.json`
2. Selects appropriate model (defaults to 'mao')
3. Copies model runtime files to `frontend/public/model/`
4. Generates `app-config.json` with correct entry path

### 6. Root Configuration
**File**: `vtuber/vtuber.config.json`
- **Content**: `{"model": "mao"}`
- **Purpose**: Controls which model is currently active
- **Usage**: Asset sync script reads this to determine model selection

## Model File Structure

### Source Models Location
**Base Path**: `vtuber/assets/models/`

#### Available Models:
1. **mao_pro** (`vtuber/assets/models/mao_pro/runtime/`)
   - Main model file: `mao_pro.model3.json`
   - Core data: `mao_pro.moc3`
   - Textures: `mao_pro.4096/texture_00.png`
   - Physics: `mao_pro.physics3.json`
   - Pose: `mao_pro.pose3.json`
   - Display info: `mao_pro.cdi3.json`
   - Expressions: 8 expression files in `expressions/` folder
   - Motions: 7 motion files in `motions/` folder

2. **shizuku** (`vtuber/assets/models/shizuku/runtime/`)
   - Main model file: `shizuku.model3.json`
   - Core data: `shizuku.moc3`
   - Textures: 5 texture files in `shizuku.1024/` folder
   - Physics: `shizuku.physics3.json`
   - Pose: `shizuku.pose3.json`
   - Display info: `shizuku.cdi3.json`
   - Motions: 4 motion files in `motion/` folder

### Runtime Model Location
**Path**: `vtuber/frontend/public/model/`
- **Purpose**: Web-accessible model files for the frontend
- **Content**: Copied from source models during asset sync
- **Structure**: Mirrors source model runtime directories

## Dependencies and Libraries

### Core Dependencies
- **easy-live2d**: Live2D model rendering and animation
- **pixi.js**: 2D rendering engine
- **react**: UI framework
- **typescript**: Type safety and development experience

### External Dependencies
- **Live2D Cubism Core**: Loaded via CDN in `index.html`
  ```html
  <script src="https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js"></script>
  ```

## Build and Development Process

### Development Workflow
1. **Asset Sync**: `npm run dev` automatically runs `scripts/sync-assets.mjs`
2. **Model Selection**: Change `vtuber.config.json` to switch models
3. **Hot Reload**: Vite provides fast development experience
4. **Asset Updates**: Model changes require asset sync to propagate

### Build Process
1. **Asset Sync**: `npm run build` runs asset sync before building
2. **TypeScript Compilation**: `tsc -b` compiles TypeScript
3. **Vite Build**: Creates optimized production bundle

## Key Technical Details

### Canvas Management
- **Full Viewport**: Canvas fills entire viewport (100vw × 100vh)
- **Responsive**: Automatically adjusts to window size changes
- **Transparent Background**: `backgroundAlpha: 0` for transparent rendering

### Model Positioning
- **Centered**: Model is positioned at canvas center
- **Scaled**: Maintains aspect ratio while fitting viewport
- **Responsive**: 90% scale factor for optimal viewing

### Performance Considerations
- **Ticker Integration**: Uses PixiJS shared ticker for animation
- **Memory Management**: Proper cleanup of PixiJS application and event listeners
- **Asset Loading**: Asynchronous model loading with proper error handling

## File Locations Summary

### Core Application Files
- `vtuber/frontend/src/App.tsx` - Main app wrapper
- `vtuber/frontend/src/components/Live2D.tsx` - Core rendering logic
- `vtuber/frontend/src/main.tsx` - Application entry point
- `vtuber/frontend/index.html` - HTML template with Live2D SDK

### Configuration Files
- `vtuber/vtuber.config.json` - Root model selection
- `vtuber/frontend/public/app-config.json` - Generated frontend config
- `vtuber/frontend/package.json` - Dependencies and scripts

### Asset Management
- `vtuber/frontend/scripts/sync-assets.mjs` - Asset synchronization script
- `vtuber/assets/models/` - Source model files
- `vtuber/frontend/public/model/` - Runtime model files

### Build Configuration
- `vtuber/frontend/vite.config.ts` - Vite build configuration
- `vtuber/frontend/tsconfig.json` - TypeScript configuration

## Future Considerations

### Potential Enhancements
1. **Backend Integration**: The empty `backend/` directory suggests future server-side features
2. **Model Switching**: UI for runtime model selection
3. **Animation Controls**: User interaction with model animations
4. **Performance Optimization**: WebGL rendering optimizations
5. **Mobile Support**: Touch interaction and mobile-specific features

### Current Limitations
1. **Single Model**: Only one model can be active at a time
2. **Manual Start**: User must click start button to begin rendering
3. **Basic Interactions**: Limited user interaction with the model
4. **No Backend**: Currently client-side only

This architecture provides a solid foundation for a Live2D virtual character system with clean separation of concerns, proper asset management, and responsive rendering capabilities.
