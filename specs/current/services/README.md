# Services Layer

Internal services and background jobs running as separate processes.

## Overview

Services that run independently from the main Flask app, either as separate Render services or scheduled cron jobs.

## Components

### [ABC Renderer](abc-renderer.md)
Microservice for converting ABC notation to PNG images (Node.js + abcjs)

### [Active Sessions Cron](active-sessions-cron.md)
Scheduled job tracking which sessions are currently happening (runs every 15 minutes)

## Deployment

All services defined in `render.yaml`:
- **abc-renderer**: Web service (Node.js)
- **ceol-io-active-sessions**: Cron job (Python)
