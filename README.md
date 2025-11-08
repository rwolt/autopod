# autopod

A lightweight CLI controller for automating ComfyUI workflows on RunPod instances.

## Overview

autopod automates the process of running ComfyUI image-to-video workflows in the cloud, helping you save money on compute costs through intelligent pod lifecycle management.

**Status:** Version 1 (MVP) - In Development

## Quick Start

Coming soon...

## Features (V1)

- Create RunPod pods programmatically
- SSH tunnel to ComfyUI instances
- Transfer files via SCP
- Submit jobs using workflow templates
- Rich terminal UI with live progress
- Interactive controls (open GUI, kill/stop pod, view logs)
- Cost safety features

## Project Structure

```
autopod/
├── CLAUDE.md              # Development workflow guide
├── README.md              # This file
├── tasks/                 # PRDs and task lists
├── src/autopod/          # Main package
├── templates/             # ComfyUI workflow templates (API format)
├── jobs/                  # Job specifications (JSON)
├── inputs/                # Input files
└── outputs/               # Rendered outputs
```

## Development

See [CLAUDE.md](./CLAUDE.md) for detailed development workflow and architecture documentation.

## License

TBD
