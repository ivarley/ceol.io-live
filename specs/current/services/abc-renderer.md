# ABC Renderer Service

Node.js microservice for converting ABC notation to PNG images.

## Overview

**Location**: `abc-renderer/`
**Technology**: Node.js + Express + abcjs + Sharp + JSDOM
**Deployment**: Separate Render web service
**Communication**: Render private network

## Purpose

- Convert ABC notation (text-based music notation) to PNG images
- Server-side rendering for tune sheet music display
- Used by main Flask app to display tune notation

## API

### POST `/api/render`

Renders ABC notation to a PNG image.

**Request**:
```json
{
  "abc": "X:1\nT:The Banshee\nM:4/4\nL:1/8\nK:Emin\n|:EBBA B2 EB|...",
  "width": 800,        // optional, default: 800, max: 2000
  "scale": 1.5,        // optional, default: 1.5, max: 3.0
  "isIncipit": false   // optional, default: false, renders compact preview
}
```

**Response**: Binary PNG image data (`Content-Type: image/png`)

**Incipit Mode** (`isIncipit: true`):
- Renders first 2 bars only
- Minimal padding for compact display
- Hides clef and time signature
- Smaller default width (400px)
- Reduced scale (1.2)

**Errors**:
- 400: Invalid ABC notation or parameters
- 500: Rendering failure

### GET `/api/health`

Health check endpoint for monitoring.

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 12345.67
}
```

### GET `/test`

Web-based test form for manual testing.

## Architecture

```
Client Request (ABC notation)
       ↓
Express Server
       ↓
abcjs (ABC → SVG via JSDOM)
       ↓
Sharp (SVG → PNG)
       ↓
PNG Image Response
```

## Integration with Flask App

**Flask Configuration**:
```python
import os
import requests

ABC_RENDERER_URL = os.getenv('ABC_RENDERER_URL', 'http://abc-renderer:10000')

# Render ABC to PNG
response = requests.post(
    f'{ABC_RENDERER_URL}/api/render',
    json={'abc': abc_notation, 'width': 800, 'scale': 1.5},
    timeout=10
)

if response.status_code == 200:
    image_data = response.content
```

**Environment Variable**: `ABC_RENDERER_URL` - Internal Render hostname (e.g., `abc-renderer-2j3e:10000`)

## ABC Notation Format

Text-based music notation for traditional music.

**Required Headers**:
- `X:` - Reference number
- `T:` - Title
- `M:` - Meter (time signature)
- `L:` - Default note length
- `K:` - Key signature

**Example**:
```
X:1
T:The Butterfly
M:9/8
L:1/8
K:Em
|:EBBA B2 EB|B2 AB dBAG|FDAD BDAD|FDAD dAFD|
EBBA B2 EB|B2 AB defg|afec dBAF|DEFD E2:|
```

**Resources**:
- [ABC Notation Standard](http://abcnotation.com/)
- [abcjs Documentation](https://www.abcjs.net/)

## Performance

- **Rendering time**: 50-200ms per image
- **Image size**: 20-50KB per tune (PNG)
- **Memory usage**: ~100-200MB baseline

## Deployment

Configured in `render.yaml`:

```yaml
services:
  - type: web
    name: abc-renderer
    runtime: node
    rootDir: abc-renderer
    buildCommand: "npm install"
    startCommand: "npm start"
    plan: free
    envVars:
      - key: NODE_VERSION
        value: "18"
      - key: PORT
        value: "10000"
```

## Local Development

```bash
cd abc-renderer
npm install
npm start  # Port 10000
```

**Test endpoints**:
- Health: `curl http://localhost:10000/api/health`
- Test UI: Open `http://localhost:10000/test` in browser
- Render:
  ```bash
  curl -X POST http://localhost:10000/api/render \
    -H "Content-Type: application/json" \
    -d '{"abc": "X:1\nT:Test\nM:4/4\nL:1/8\nK:D\nDEFG ABCD|"}' \
    --output test.png
  ```

## Documentation

See `abc-renderer/README.md` for complete documentation.

## Related Specs

- [Session Logging UI](../ui/session-logging.md) - Uses ABC renderer for tune display
- [Tune Model](../data/tune-model.md) - Stores ABC notation from thesession.org
- [External APIs](../logic/external-apis.md) - thesession.org provides ABC notation
