import express from 'express';
import abcjs from 'abcjs';
import sharp from 'sharp';
import path from 'path';
import { fileURLToPath } from 'url';
import { JSDOM } from 'jsdom';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 10000;

// Middleware
app.use(express.json({ limit: '10mb' }));
app.use(express.static('public'));

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({
    status: 'healthy',
    version: '1.0.0',
    uptime: process.uptime()
  });
});

// ABC rendering endpoint
app.post('/api/render', async (req, res) => {
  try {
    const { abc, width = 800, scale = 1.5, isIncipit = false } = req.body;

    // Validate input
    if (!abc) {
      return res.status(400).json({
        success: false,
        error: 'ABC notation is required'
      });
    }

    if (typeof abc !== 'string') {
      return res.status(400).json({
        success: false,
        error: 'ABC notation must be a string'
      });
    }

    // Validate size parameters
    const maxWidth = 2000;
    const maxScale = 3.0;

    // Use smaller width for incipits to avoid excess whitespace
    const defaultWidth = isIncipit ? 400 : width;
    const finalWidth = Math.min(Math.max(defaultWidth, 100), maxWidth);
    const finalScale = Math.min(Math.max(scale, 0.5), maxScale);

    console.log(`Rendering ABC notation (width: ${finalWidth}, scale: ${finalScale}, isIncipit: ${isIncipit})`);

    // For incipits: modify ABC to hide clef and time signature
    let processedAbc = abc;
    if (isIncipit) {
      const lines = abc.split('\n');

      // Remove the M: (meter/time signature) line
      const meterIndex = lines.findIndex(line => line.match(/^M:/));
      if (meterIndex >= 0) {
        lines.splice(meterIndex, 1);
      }

      // Replace K: line with K:none clef=none to hide both key signature and clef
      const keyIndex = lines.findIndex(line => line.match(/^K:/));
      if (keyIndex >= 0) {
        lines[keyIndex] = 'K:none clef=none';
      }

      processedAbc = lines.join('\n');

      // For incipits: ensure there's a single barline at the start
      // Remove opening repeat signs (|: or [:) and replace with single barline
      processedAbc = processedAbc.replace(/(\n[^:\n]*)([\|\[][:])/, '$1|');

      // If there's no barline at all at the start, add one
      if (!processedAbc.match(/\n[^\n]*\|/)) {
        // Add | before the first note
        processedAbc = processedAbc.replace(/(\nK:[^\n]*\n)([^\n|])/, '$1|$2');
      }

      console.log('Modified ABC for incipit:', processedAbc);
    }

    // Create a virtual DOM for abcjs to render into
    const dom = new JSDOM('<!DOCTYPE html><html><body><div id="abc"></div></body></html>');
    global.window = dom.window;
    global.document = dom.window.document;

    // Set navigator if not already set (avoid read-only property error)
    if (!global.navigator) {
      try {
        global.navigator = {
          userAgent: 'node.js',
          platform: 'node'
        };
      } catch (e) {
        // Ignore if navigator is read-only
      }
    }

    const container = document.getElementById('abc');

    // Render ABC to SVG using abcjs
    // Use minimal padding for incipits to reduce whitespace
    const paddingOptions = isIncipit ? {
      paddingtop: 0,
      paddingbottom: 2,
      paddingleft: 5,
      paddingright: 5,
      stafftopmargin: 0
    } : {
      paddingtop: 10,
      paddingbottom: 15,
      paddingleft: 10,
      paddingright: 20
    };

    // For incipits: use slightly smaller scale
    const renderScale = isIncipit ? 1.2 : finalScale;

    const visualObj = abcjs.renderAbc(container, processedAbc, {
      staffwidth: finalWidth,
      responsive: 'resize',
      scale: renderScale,
      ...paddingOptions
    });

    if (!visualObj || visualObj.length === 0) {
      return res.status(400).json({
        success: false,
        error: 'Failed to parse ABC notation'
      });
    }

    // Extract SVG from the container
    const svgElement = container.querySelector('svg');

    // For incipits: crop top and left whitespace by finding minimum coordinates
    if (isIncipit && svgElement) {
      try {
        // Find all elements that might contain coordinates
        const contentElements = svgElement.querySelectorAll('path, text, rect, circle, ellipse, line');
        let minY = Infinity;
        let minX = Infinity;

        contentElements.forEach(element => {
          // Extract X and Y coordinates from different element types
          if (element.tagName === 'path') {
            const d = element.getAttribute('d');
            if (d) {
              // Parse path data for coordinates
              const coordMatches = d.match(/[ML]\s*([\d.-]+)\s+([\d.-]+)|[Hh]\s*([\d.-]+)|[Vv]\s*([\d.-]+)/g);
              if (coordMatches) {
                coordMatches.forEach(match => {
                  const xyMatch = match.match(/[ML]\s*([\d.-]+)\s+([\d.-]+)/);
                  if (xyMatch) {
                    const x = parseFloat(xyMatch[1]);
                    const y = parseFloat(xyMatch[2]);
                    if (!isNaN(x) && x < minX) minX = x;
                    if (!isNaN(y) && y < minY) minY = y;
                  }
                });
              }
            }
          } else if (element.tagName === 'text') {
            const x = parseFloat(element.getAttribute('x'));
            const y = parseFloat(element.getAttribute('y'));
            if (!isNaN(x) && x < minX) minX = x;
            if (!isNaN(y) && y < minY) minY = y;
          } else if (element.tagName === 'rect') {
            const x = parseFloat(element.getAttribute('x'));
            const y = parseFloat(element.getAttribute('y'));
            if (!isNaN(x) && x < minX) minX = x;
            if (!isNaN(y) && y < minY) minY = y;
          } else if (element.tagName === 'circle') {
            const cx = parseFloat(element.getAttribute('cx'));
            const cy = parseFloat(element.getAttribute('cy'));
            const r = parseFloat(element.getAttribute('r') || 0);
            const x = cx - r;
            const y = cy - r;
            if (!isNaN(x) && x < minX) minX = x;
            if (!isNaN(y) && y < minY) minY = y;
          } else if (element.tagName === 'line') {
            const x1 = parseFloat(element.getAttribute('x1'));
            const x2 = parseFloat(element.getAttribute('x2'));
            const y1 = parseFloat(element.getAttribute('y1'));
            const y2 = parseFloat(element.getAttribute('y2'));
            const x = Math.min(x1, x2);
            const y = Math.min(y1, y2);
            if (!isNaN(x) && x < minX) minX = x;
            if (!isNaN(y) && y < minY) minY = y;
          }
        });

        console.log(`Found ${contentElements.length} content elements, minX=${minX}, minY=${minY}`);

        // If we found actual content, adjust viewBox to crop top and left
        const viewBox = svgElement.getAttribute('viewBox');
        if (viewBox) {
          const [x, y, width, height] = viewBox.split(' ').map(Number);

          // Crop top if there's whitespace
          let newY = y;
          let newHeight = height;
          if (minY !== Infinity && minY > 5) {
            // Leave a small margin (3px) above the content
            newY = Math.max(0, minY - 3);
            const cropTop = newY - y;
            newHeight = height - cropTop;
          }

          // Crop left if there's whitespace
          let newX = x;
          let newWidth = width;
          if (minX !== Infinity && minX > 2) {
            // Leave minimal margin (1px) to the left
            newX = Math.max(0, minX - 1);
            const cropLeft = newX - x;
            newWidth = width - cropLeft;
          }

          svgElement.setAttribute('viewBox', `${newX} ${newY} ${newWidth} ${newHeight}`);
          console.log(`Cropped incipit: X ${x}->${newX} (content at ${minX}), Y ${y}->${newY} (content at ${minY})`);
        }
      } catch (error) {
        console.error('Error cropping incipit:', error);
      }
    }

    if (!svgElement) {
      return res.status(500).json({
        success: false,
        error: 'Failed to generate SVG from ABC notation'
      });
    }

    const svgString = svgElement.outerHTML;

    // Clean up global DOM
    delete global.window;
    delete global.document;
    try { delete global.navigator; } catch (e) { /* ignore */ }

    console.log(`Generated SVG (${svgString.length} characters)`);

    // Convert SVG to PNG using Sharp
    const pngBuffer = await sharp(Buffer.from(svgString))
      .png()
      .toBuffer();

    console.log(`Successfully rendered ABC notation to PNG (${pngBuffer.length} bytes)`);

    // Send PNG image
    res.set('Content-Type', 'image/png');
    res.send(pngBuffer);

  } catch (error) {
    // Clean up global DOM in case of error
    delete global.window;
    delete global.document;
    try { delete global.navigator; } catch (e) { /* ignore */ }

    console.error('Error rendering ABC notation:', error);
    res.status(500).json({
      success: false,
      error: error.message || 'Internal server error'
    });
  }
});

// Test form endpoint
app.get('/test', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'test-form.html'));
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`ABC Renderer Service listening on port ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/api/health`);
  console.log(`Test form: http://localhost:${PORT}/test`);
});
