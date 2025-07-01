# 3D Model Generator GUI

A modern, user-friendly interface for automating 3D model creation using RealityCapture and RealityScan.

## Features

- **Modern UI**: Clean, intuitive interface built with CustomTkinter
- **Automated Processing**: Batch process multiple photo directories
- **Exposure Correction**: Automatic overexposure detection and correction using ImageMagick
- **Progress Tracking**: Real-time log output and status updates
- **Settings Persistence**: Automatically saves and loads your configuration
- **Multi-threading**: Parallel image processing for faster execution
- **Queue Management**: Monitors directories with insufficient images

## Installation

1. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install ImageMagick** (optional, for exposure correction):
   - Windows: Download from https://imagemagick.org/script/download.php#windows
   - macOS: `brew install imagemagick`
   - Linux: `sudo apt-get install imagemagick`

3. **Install RealityCapture or RealityScan**:
   - Ensure you have a licensed copy of RealityCapture or RealityScan installed

## Usage

### Starting the GUI

Run the GUI application:
```bash
python ui.py
```

### Configuration

The left panel contains all configuration options:

#### Basic Settings
- **Input Directory**: Folder containing subdirectories of photos
- **Output Directory**: Where 3D models will be saved
- **Software Executable**: Path to RealityCapture.exe or RealityScan.exe
- **Software Type**: Auto-detect or manually specify (RealityCapture/RealityScan)
- **Minimum Images**: Required number of photos per directory (default: 300)
- **Queue Check Interval**: How often to check for new images (seconds)
- **Checkpoint File**: Progress tracking file

#### Exposure Correction Settings
- **Enable Exposure Correction**: Toggle automatic exposure correction
- **ImageMagick Path**: Path to ImageMagick executable (usually "magick")
- **Exposure Adjustment**: Correction amount in stops (-2.0 to +2.0)
- **Keep Original Images**: Whether to preserve original photos
- **Max Worker Threads**: Number of parallel threads for image processing

### Operation

1. **Configure Settings**: Fill in all required paths and adjust settings as needed
2. **Validate Settings**: Click "Validate Settings" to check configuration
3. **Start Processing**: Click "Start Processing" to begin automation
4. **Monitor Progress**: Watch the log output for real-time updates
5. **Stop if Needed**: Use "Stop Processing" to halt execution

### Settings Persistence

- Settings are automatically saved to `ui_settings.json`
- Configuration is restored when you restart the application
- Use "Save Settings" button to manually save current configuration

## Directory Structure

The application expects this structure:
```
Input Directory/
├── Object1_Photos/
│   ├── IMG_001.jpg
│   ├── IMG_002.jpg
│   └── ... (300+ images)
├── Object2_Photos/
│   ├── IMG_001.jpg
│   └── ... (300+ images)
└── ...
```

Output structure:
```
Output Directory/
├── Object1_Photos/
│   ├── Object1_Photos.obj
│   ├── Object1_Photos_textured.obj
│   ├── Object1_Photos.rcproj
│   └── textures/
├── Object2_Photos/
│   └── ...
└── ...
```

## Exposure Correction

When enabled, the application will:
1. Analyze each image for overexposure
2. Apply correction to overexposed images using ImageMagick
3. Process corrected images in parallel for speed
4. Keep original images (if configured)
5. Skip already-corrected directories

## Queue Management

The application monitors directories with insufficient images:
- Directories with fewer than minimum images are queued
- Periodic checks for new images being added
- Automatic processing when threshold is reached
- Useful for ongoing photo capture operations

## Logging

The right panel shows real-time log output including:
- Processing status and progress
- Error messages and warnings
- Exposure correction results
- Performance metrics

## Troubleshooting

### Common Issues

1. **ImageMagick Not Found**:
   - Ensure ImageMagick is installed and in PATH
   - Or provide full path to `magick.exe`
   - Disable exposure correction if not needed

2. **Software Executable Not Found**:
   - Verify RealityCapture/RealityScan installation
   - Check file path and permissions
   - Ensure license is valid

3. **Processing Fails**:
   - Check log output for specific errors
   - Verify image formats are supported
   - Ensure sufficient disk space
   - Check that photos are valid

4. **Slow Performance**:
   - Reduce number of worker threads
   - Disable exposure correction
   - Use SSD for faster I/O
   - Close other applications

### Performance Tips

- Use SSD storage for input/output directories
- Adjust worker threads based on CPU cores
- Pre-sort images by quality before processing
- Use consistent lighting to reduce exposure correction needs

## Command Line Alternative

You can still use the original command-line interface:
```bash
python main.py "C:\Photos" "C:\Output" "C:\Program Files\RealityCapture\RealityCapture.exe"
```

See `python main.py --help` for all command-line options.

## License

This tool is designed to work with licensed copies of RealityCapture or RealityScan. Ensure you have appropriate licenses for the software you intend to use. 