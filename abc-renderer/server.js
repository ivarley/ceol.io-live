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
    const { abc, width = 800, scale = 1.5 } = req.body;

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
    const finalWidth = Math.min(Math.max(width, 100), maxWidth);
    const finalScale = Math.min(Math.max(scale, 0.5), maxScale);

    console.log(`Rendering ABC notation (width: ${finalWidth}, scale: ${finalScale})`);

    // Create a virtual DOM for abcjs to render into
    const dom = new JSDOM('<!DOCTYPE html><html><body><div id="abc"></div></body></html>');
    global.window = dom.window;
    global.document = dom.window.document;

    const container = document.getElementById('abc');

    // Render ABC to SVG using abcjs
    const visualObj = abcjs.renderAbc(container, abc, {
      staffwidth: finalWidth,
      scale: finalScale,
      responsive: 'resize'
    });

    if (!visualObj || visualObj.length === 0) {
      return res.status(400).json({
        success: false,
        error: 'Failed to parse ABC notation'
      });
    }

    // Extract SVG from the container
    const svgElement = container.querySelector('svg');

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
