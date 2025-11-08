# ABC Notation Renderer Service

A lightweight Node.js microservice that converts ABC notation to PNG images using [abcjs](https://abcjs.net/) and [Sharp](https://sharp.pixelplumbing.com/).

## Overview

This service provides a simple REST API for rendering ABC notation (a text-based music notation format commonly used for traditional music) into PNG images. It's designed to be deployed as a separate service on Render and communicate with the main Flask application over Render's private network.

## Features

- **Simple API**: Single endpoint that accepts ABC notation and returns PNG images
- **High Performance**: Uses Sharp for fast SVG-to-PNG conversion
- **Server-Side Rendering**: Uses JSDOM for headless rendering of ABC notation
- **Configurable Output**: Supports custom width and scale parameters
- **Test Interface**: Built-in web form for manual testing
- **Health Checks**: Endpoint for monitoring and uptime checks

## Installation

```bash
cd abc-renderer
npm install
```

## Usage

### Start the Server

```bash
# Production
npm start

# Development (with auto-reload)
npm run dev
```

The server will start on port 10000 (or the port specified in the `PORT` environment variable).

### API Endpoints

#### POST /api/render

Renders ABC notation to a PNG image.

**Request:**

```json
{
  "abc": "X:1\nT:The Banshee\nM:4/4\nL:1/8\nK:Emin\n|:EBBA B2 EB|...",
  "width": 800,     // optional, default: 800, max: 2000
  "scale": 1.5      // optional, default: 1.5, max: 3.0
}
```

**Response:**

- **Success (200)**: Binary PNG image data with `Content-Type: image/png`
- **Error (400)**: Invalid ABC notation or parameters
- **Error (500)**: Internal server error

**Example with curl:**

```bash
curl -X POST http://localhost:10000/api/render \
  -H "Content-Type: application/json" \
  -d '{"abc": "X:1\nT:Test\nM:4/4\nL:1/8\nK:D\nDEFG ABCD|"}' \
  --output test.png
```

**Example with JavaScript:**

```javascript
const response = await fetch('http://localhost:10000/api/render', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    abc: 'X:1\nT:Test\nM:4/4\nL:1/8\nK:D\nDEFG ABCD|',
    width: 800,
    scale: 1.5
  })
});

const blob = await response.blob();
const imageUrl = URL.createObjectURL(blob);
```

#### GET /api/health

Health check endpoint for monitoring.

**Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 12345.67
}
```

#### GET /test

Web-based test form for manual testing. Open in a browser to interactively test the rendering service.

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

### Technology Stack

- **Express**: Web framework for handling HTTP requests
- **abcjs**: ABC notation parser and SVG renderer
- **JSDOM**: Virtual DOM for server-side rendering
- **Sharp**: High-performance image processing library

## Deployment on Render

This service is designed to be deployed as a separate web service on Render.

### render.yaml Configuration

Add this to your project's `render.yaml`:

```yaml
services:
  - type: web
    name: abc-renderer
    env: node
    buildCommand: "cd abc-renderer && npm install"
    startCommand: "cd abc-renderer && npm start"
    plan: free
    envVars:
      - key: NODE_VERSION
        value: "18"
      - key: PORT
        value: "10000"
```

### Private Network Communication

After deployment, Render will provide an internal hostname (e.g., `abc-renderer-2j3e:10000`). This can be used by other services in the same Render region to communicate over the private network.

In your Flask app:

```python
import os
import requests

ABC_RENDERER_URL = os.getenv('ABC_RENDERER_URL', 'http://abc-renderer-2j3e:10000')

# Call the renderer
response = requests.post(
    f'{ABC_RENDERER_URL}/api/render',
    json={'abc': abc_notation},
    timeout=10
)

if response.status_code == 200:
    image_data = response.content
```

## Local Development

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the server:
   ```bash
   npm start
   ```

3. Test the health endpoint:
   ```bash
   curl http://localhost:10000/api/health
   ```

4. Open the test form in your browser:
   ```
   http://localhost:10000/test
   ```

5. Test rendering with sample ABC notation:
   ```bash
   curl -X POST http://localhost:10000/api/render \
     -H "Content-Type: application/json" \
     -d '{"abc": "X:1\nT:Test\nM:4/4\nL:1/8\nK:D\nDEFG ABCD|"}' \
     --output test.png
   ```

## Error Handling

The service implements comprehensive error handling:

- **Invalid ABC notation**: Returns 400 with error message
- **Missing required fields**: Returns 400 with error message
- **Rendering failures**: Returns 500 with error details
- **Invalid parameters**: Validates and constrains width/scale values

All errors are logged to the console for debugging.

## Performance

Typical performance metrics:

- **Rendering time**: 50-200ms per image
- **Image size**: 20-50KB per tune (PNG format)
- **Memory usage**: ~100-200MB baseline

The service uses:
- **JSDOM** for virtual DOM (lighter than headless Chrome)
- **Sharp** for high-performance image conversion (libvips-based)

## Troubleshooting

### Service won't start

- Check that Node.js 18+ is installed: `node --version`
- Verify all dependencies are installed: `npm install`
- Check for port conflicts: `lsof -i :10000`

### Rendering produces errors

- Verify ABC notation is valid (must include header fields like X:, T:, M:, L:, K:)
- Check the error message in the JSON response
- Review server logs for detailed error information

### Images are blank or corrupted

- Ensure Sharp is properly installed (may require rebuilding: `npm rebuild sharp`)
- Verify JSDOM is functioning correctly
- Check that SVG is being generated by abcjs (review server logs)

## ABC Notation Format

ABC notation is a text-based music notation format. Example:

```
X:1
T:The Banshee
M:4/4
L:1/8
K:Emin
|:EBBA B2 EB|B2 AB dBAG|FDAD BDAD|FDAD dAFD|
EBBA B2 EB|B2 AB defg|afec dBAF|DEFD E2:|
```

Required header fields:
- `X:` - Reference number
- `T:` - Title
- `M:` - Meter (time signature)
- `L:` - Default note length
- `K:` - Key signature

For more information, see:
- [ABC Notation Standard](http://abcnotation.com/)
- [abcjs Documentation](https://www.abcjs.net/)

## License

ISC
