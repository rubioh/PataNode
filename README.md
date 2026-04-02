# PataNode - Node-Based Shader Editor

![PataNode Logo](gui/image/PataNode.png)

**PataNode** is a powerful node-based shader editor designed for creating real-time audio-reactive visuals. Built with PyQt5 and ModernGL, it provides an intuitive interface for building complex shader programs through a visual node graph system.

## Features

### 🎨 Visual Shader Programming
- **Node-based interface** for creating shader programs without writing code
- **70+ built-in shader nodes** including colors, effects, textures, and transformations
- **Real-time preview** with immediate feedback
- **Multi-window MDI interface** for managing multiple shader graphs

### 🎵 Audio Reactive Visuals
- **Real-time audio analysis** with feature extraction
- **Beat detection** for kick, snare, and hat sounds
- **Audio feature mapping** to shader parameters
- **Audio engine** with configurable processing pipeline

### 💡 Light Control Integration
- **Light engine** for controlling external lighting systems
- **Color synchronization** between visuals and lights
- **ArtNet support** for professional lighting control

### 🌐 Network Capabilities
- **Built-in server mode** for remote control
- **Network synchronization** of parameters
- **Multi-device coordination** for live performances

### 🔧 Professional Tools
- **Scene management** with save/load functionality
- **Mapping system** for LED and projection mapping
- **Particle systems** and physics simulations
- **Transition effects** for smooth scene changes

## Architecture

```
PataNode Architecture
├── Core Application (app.py)
├── Node Editor Framework (nodeeditor/)
├── Shader Programs (program/)
│   ├── Base programs
│   ├── Colors & effects
│   ├── Textures & patterns
│   ├── Transitions
│   └── Particle systems
├── Audio Processing (audio/)
├── Light Control (light/)
└── Network Server (server/)
```


## Installation

```bash
# Install dependencies using UV
uv pip install -r requirements.txt

# Run the application
uv run main.py
```

## Development

### Project Structure
- `app.py` - Main application class
- `gui/` - User interface components
- `node/` - Node definitions and base classes
- `program/` - Shader program implementations
- `audio/` - Audio processing pipeline
- `light/` - Light control system
- `server/` - Network server functionality


