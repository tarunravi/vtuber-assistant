# Asset Management and Synchronization System

## Overview
This codebase uses an automated asset synchronization system to manage Live2D model files between the source assets directory and the frontend public directory. The system ensures that the correct model files are always available to the frontend and automatically generates the necessary configuration files.

## Core Components

### 1. Asset Synchronization Script
**File**: `frontend/scripts/sync-assets.mjs`

#### Purpose
- Automatically copies the selected Live2D model's runtime files to the frontend public directory
- Generates `app-config.json` with the correct model configuration
- Ensures the frontend always has access to the right model files

#### How It Works
```javascript
// Model mapping configuration
const modelMap = {
  mao: {
    src: join(projectRoot, 'assets/models/mao_pro/runtime'),
    entry: 'mao_pro.model3.json'
  },
  shizuku: {
    src: join(projectRoot, 'assets/models/shizuku/runtime'),
    entry: 'shizuku.model3.json'
  },
  ellot: {
    src: join(projectRoot, 'assets/models/ellot/runtime'),
    entry: 'ellot.model3.json'
  }
}
```

#### Sync Process
1. **Read Configuration**: Parses `vtuber.config.json` to determine the selected model
2. **Select Model**: Chooses from available models (mao, shizuku, ellot) with fallback to 'mao'
3. **Copy Assets**: Copies the selected model's runtime directory to `frontend/public/model/`
4. **Generate Config**: Creates `app-config.json` with:
   - Selected model name
   - Model entry point path
   - Time scale settings
   - Emotion configurations
   - WebSocket backend URL

### 2. Configuration Files

#### Root Configuration (`vtuber.config.json`)
```json
{
  "model": "ellot",
  "timeScale": 1.0,
  "models": {
    "ellot": {
      "emotions": {
        "Happy": "exp_03",
        "Searching": "exp_01"
      },
      "timeScale": 1.2
    }
  },
  "llm": {
    "wsPath": "/ws"
  }
}
```

#### Generated Frontend Config (`frontend/public/app-config.json`)
```json
{
  "model": "ellot",
  "entry": "/model/ellot.model3.json",
  "timeScale": 1.2,
  "emotions": {
    "Happy": "exp_03",
    "Searching": "exp_01"
  },
  "llm": {
    "backendWsUrl": "ws://127.0.0.1:8000/ws"
  }
}
```

### 3. Asset Directory Structure

#### Source Assets
```
assets/models/
├── ellot/
│   └── runtime/
│       ├── ellot.model3.json
│       ├── ellot.moc3
│       ├── ellot.physics3.json
│       ├── expressions/
│       └── motions/
├── mao_pro/
│   └── runtime/
└── shizuku/
    └── runtime/
```

#### Frontend Public Assets
```
frontend/public/
├── model/          # Copied from selected model's runtime
│   ├── ellot.model3.json
│   ├── ellot.moc3
│   ├── expressions/
│   └── motions/
└── app-config.json # Generated configuration
```

## Integration with Development Workflow

### 1. Start Script Integration
**File**: `start.sh`

The start script now automatically runs asset synchronization before starting the frontend:

```bash
start_frontend() {
  log "Starting frontend dev server..."
  cd "$FRONTEND_DIR"
  
  # Sync assets before starting
  log "Syncing model assets..."
  node scripts/sync-assets.mjs
  
  if [ ! -d node_modules ]; then
    log "Installing npm dependencies"
    npm install --no-fund --no-audit
  fi
  npm run dev
}
```

#### Benefits
- **Automatic Setup**: No manual asset syncing required
- **Consistent State**: Frontend always has the correct model files
- **Better UX**: Eliminates "model not found" errors
- **Streamlined Workflow**: Single command to start everything

### 2. Development Workflow
1. **Change Model**: Update `vtuber.config.json` to select a different model
2. **Start Application**: Run `./start.sh`
3. **Automatic Sync**: Assets are automatically copied and configured
4. **Frontend Ready**: Frontend loads with the correct model

### 3. Build Process Integration
The sync-assets script is also integrated into the build process:
- **Development**: Runs automatically via `start.sh`
- **Build**: Runs before `npm run build`
- **Deployment**: Ensures production builds have correct assets

## Model Switching

### How to Change Models
1. **Edit Configuration**: Modify `vtuber.config.json`
   ```json
   {
     "model": "shizuku"  // Change from "ellot" to "shizuku"
   }
   ```

2. **Restart Application**: Run `./start.sh` again
   - Assets are automatically synced
   - Frontend loads the new model
   - Configuration is updated

### Model-Specific Settings
Each model can have custom configurations:

```json
{
  "models": {
    "ellot": {
      "emotions": {
        "Happy": "exp_03",
        "Searching": "exp_01"
      },
      "timeScale": 1.2
    },
    "mao": {
      "emotions": {
        "Creative": "exp_01",
        "Focused": "exp_02"
      },
      "timeScale": 1.0
    }
  }
}
```

## Error Handling and Fallbacks

### Default Behavior
- **Model Selection**: Falls back to 'mao' if specified model doesn't exist
- **Time Scale**: Uses root `timeScale` if model-specific value is missing
- **Emotions**: Empty object if no emotions are configured

### Validation
- **Model Existence**: Checks if the selected model's runtime directory exists
- **File Integrity**: Ensures all necessary model files are present
- **Configuration**: Validates JSON structure and required fields

## Performance Considerations

### Asset Copying
- **Incremental**: Only copies when starting the application
- **Efficient**: Uses `fs-extra` for optimized file operations
- **Clean**: Removes old model files before copying new ones

### Frontend Loading
- **Optimized Paths**: Uses relative paths for faster asset loading
- **Caching**: Browser caching of model files for subsequent loads
- **Lazy Loading**: Model files are loaded only when needed

## Troubleshooting

### Common Issues
1. **Model Not Loading**
   - Check if `vtuber.config.json` has the correct model name
   - Verify the model's runtime directory exists in `assets/models/`
   - Ensure `./start.sh` was run to sync assets

2. **Missing Assets**
   - Run `node frontend/scripts/sync-assets.mjs` manually
   - Check file permissions on the assets directory
   - Verify the model's runtime directory structure

3. **Configuration Errors**
   - Validate JSON syntax in `vtuber.config.json`
   - Check that required fields are present
   - Ensure emotion mappings match actual expression files

### Debug Steps
1. **Check Logs**: Look for sync-assets output in the start script
2. **Verify Files**: Check if `frontend/public/model/` contains the expected files
3. **Validate Config**: Ensure `app-config.json` was generated correctly
4. **Test Model**: Try switching to a different model to isolate the issue

## Future Enhancements

### Potential Improvements
1. **Hot Reloading**: Watch for configuration changes and auto-sync
2. **Model Validation**: Verify model file integrity during sync
3. **Asset Compression**: Optimize model files for web delivery
4. **Multiple Models**: Support for loading multiple models simultaneously
5. **Remote Assets**: Fetch models from remote repositories

### Integration Opportunities
1. **Backend API**: REST endpoints for model management
2. **User Interface**: Web-based model selection and configuration
3. **Version Control**: Track model changes and rollback capabilities
4. **Performance Monitoring**: Asset loading time and optimization metrics

This asset management system provides a robust foundation for managing Live2D models in the VTuber application, ensuring consistent behavior and easy model switching while maintaining clean separation of concerns between asset storage and frontend delivery.
