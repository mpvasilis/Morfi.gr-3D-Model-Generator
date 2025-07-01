#!/usr/bin/env python3
"""
3D Model Creation Automation Script for RealityCapture and RealityScan
Processes directories containing 3D scanner photos and creates 3D models
Includes automatic exposure correction using ImageMagick
Updated with official CLI commands (2024/2025)
"""

import os
import sys
import json
import subprocess
import logging
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import argparse

class PhotogrammetryAutomator:
    def __init__(self, 
                 input_dir: str, 
                 output_dir: str, 
                 software_exe: str,
                 software_type: str = "auto",
                 checkpoint_file: str = "processing_checkpoint.json",
                 min_images: int = 300,
                 queue_check_interval: int = 300,
                 enable_exposure_correction: bool = True,
                 imagemagick_path: str = "magick",
                 exposure_adjustment: float = -0.5,
                 keep_originals: bool = True,
                 max_workers: int = 4):
        """
        Initialize the photogrammetry automation system
        
        Args:
            input_dir: Directory containing photo folders (e.g., D:\\PhotosSSD)
            output_dir: Directory where 3D models will be saved
            software_exe: Path to RealityCapture.exe or RealityScan.exe
            software_type: "realitycapture", "realityscan", or "auto" for detection
            checkpoint_file: File to store processing progress
            min_images: Minimum number of images required to process a directory
            queue_check_interval: Time in seconds between queue checks
            enable_exposure_correction: Whether to apply exposure correction
            imagemagick_path: Path to ImageMagick (magick.exe or just "magick" if in PATH)
            exposure_adjustment: Exposure adjustment (-2.0 to +2.0, negative = darker)
            keep_originals: Whether to keep original photos alongside corrected ones
            max_workers: Number of parallel threads for image processing (default: 4)
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.software_exe = software_exe
        self.checkpoint_file = checkpoint_file
        self.min_images = min_images
        self.queue_check_interval = queue_check_interval
        self.enable_exposure_correction = enable_exposure_correction
        self.imagemagick_path = imagemagick_path
        self.exposure_adjustment = exposure_adjustment
        self.keep_originals = keep_originals
        self.max_workers = max_workers
        
        # Thread safety
        self.log_lock = Lock()
        self.progress_lock = Lock()
        
        # Detect software type
        if software_type == "auto":
            if "realityscan" in software_exe.lower():
                self.software_type = "realityscan"
            else:
                self.software_type = "realitycapture"
        else:
            self.software_type = software_type
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.setup_logging()
        
        # Test ImageMagick if exposure correction is enabled
        if self.enable_exposure_correction:
            self.test_imagemagick()
        
        # Load checkpoint data
        self.checkpoint_data = self.load_checkpoint()
        
        # Queue for directories with insufficient images
        self.pending_queue = []
        
        self.logger.info(f"Initialized with {self.software_type.upper()} at {self.software_exe}")
        if self.enable_exposure_correction:
            self.logger.info(f"Exposure correction enabled: {self.exposure_adjustment} stops using {self.max_workers} threads")
        else:
            self.logger.info("Exposure correction disabled")
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler('photogrammetry_automation.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_checkpoint(self) -> Dict:
        """Load checkpoint data from file"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                    self.logger.info(f"Loaded checkpoint with {len(data.get('processed', []))} processed directories")
                    return data
            except Exception as e:
                self.logger.warning(f"Could not load checkpoint file: {e}")
        
        return {
            'processed': [],
            'failed': [],
            'queued': [],  # Directories waiting for more images
            'exposure_corrected': [],  # Directories that have had exposure correction applied
            'last_updated': None
        }
    
    def test_imagemagick(self):
        """Test if ImageMagick is available and working"""
        try:
            result = subprocess.run(
                [self.imagemagick_path, '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version_info = result.stdout.split('\n')[0]
                self.logger.info(f"ImageMagick found: {version_info}")
            else:
                self.logger.error("ImageMagick test failed")
                self.logger.error(f"Error: {result.stderr}")
                raise Exception("ImageMagick not working properly")
                
        except FileNotFoundError:
            self.logger.error(f"ImageMagick not found at: {self.imagemagick_path}")
            self.logger.error("Please install ImageMagick or provide correct path")
            raise Exception("ImageMagick not found")
        except Exception as e:
            self.logger.error(f"ImageMagick test error: {e}")
            raise

    def analyze_image_exposure(self, image_path: Path) -> Dict:
        """
        Analyze image exposure using ImageMagick to detect overexposure
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict with exposure analysis results
        """
        try:
            # Get image statistics
            result = subprocess.run([
                self.imagemagick_path, str(image_path),
                '-colorspace', 'HSL',
                '-channel', 'L',
                '-format', '%[fx:mean*100],%[fx:maxima*100]',
                'info:'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                mean_brightness, max_brightness = map(float, result.stdout.strip().split(','))
                
                # Detect overexposure
                is_overexposed = max_brightness > 95 or mean_brightness > 70
                
                return {
                    'mean_brightness': mean_brightness,
                    'max_brightness': max_brightness,
                    'is_overexposed': is_overexposed
                }
            else:
                self.logger.warning(f"Failed to analyze exposure for {image_path.name}")
                return {'mean_brightness': 50, 'max_brightness': 80, 'is_overexposed': False}
                
        except Exception as e:
            self.logger.warning(f"Error analyzing exposure for {image_path.name}: {e}")
            return {'mean_brightness': 50, 'max_brightness': 80, 'is_overexposed': False}

    def safe_log(self, level: str, message: str):
        """Thread-safe logging"""
        with self.log_lock:
            if level.lower() == 'info':
                self.logger.info(message)
            elif level.lower() == 'error':
                self.logger.error(message)
            elif level.lower() == 'warning':
                self.logger.warning(message)
            else:
                self.logger.info(message)

    def process_single_image(self, task_data: Dict) -> Dict:
        """
        Process a single image for exposure correction (thread worker function)
        
        Args:
            task_data: Dict containing image processing information
            
        Returns:
            Dict with processing results
        """
        image_file = Path(task_data['image_path'])
        output_file = Path(task_data['output_path'])
        adjustment = task_data['adjustment']
        task_id = task_data['task_id']
        
        result = {
            'task_id': task_id,
            'image_name': image_file.name,
            'success': False,
            'was_overexposed': False,
            'corrected': False,
            'brightness_before': 0,
            'brightness_after': 0
        }
        
        try:
            # Analyze exposure
            exposure_info = self.analyze_image_exposure(image_file)
            result['brightness_before'] = exposure_info['mean_brightness']
            result['was_overexposed'] = exposure_info['is_overexposed']
            
            if exposure_info['is_overexposed']:
                # Apply exposure correction
                success = self.correct_image_exposure(image_file, output_file, adjustment)
                
                if success:
                    result['corrected'] = True
                    result['success'] = True
                    
                    # Check brightness after correction
                    new_exposure_info = self.analyze_image_exposure(output_file)
                    result['brightness_after'] = new_exposure_info['mean_brightness']
                    
                    self.safe_log('info', f"[OK] Thread {task_id}: Corrected {image_file.name} ({exposure_info['mean_brightness']:.1f}% -> {new_exposure_info['mean_brightness']:.1f}%)")
                else:
                    # Copy original if correction failed
                    if not output_file.exists():
                        shutil.copy2(image_file, output_file)
                    result['success'] = True  # Still successful, just not corrected
                    self.safe_log('error', f"[FAIL] Thread {task_id}: Failed to correct {image_file.name}, using original")
            else:
                # Image is not overexposed, just copy
                if not output_file.exists():
                    shutil.copy2(image_file, output_file)
                result['success'] = True
                
        except Exception as e:
            self.safe_log('error', f"[ERROR] Thread {task_id}: Error processing {image_file.name}: {e}")
            # Try to copy original as fallback
            try:
                if not output_file.exists():
                    shutil.copy2(image_file, output_file)
                result['success'] = True
            except Exception as copy_error:
                self.safe_log('error', f"[ERROR] Thread {task_id}: Failed to copy {image_file.name}: {copy_error}")
        
        return result
    def correct_image_exposure(self, input_path: Path, output_path: Path, adjustment: float = None) -> bool:
        """
        Correct image exposure using ImageMagick
        
        Args:
            input_path: Path to input image
            output_path: Path to output image
            adjustment: Exposure adjustment override (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if adjustment is None:
                adjustment = self.exposure_adjustment
            
            # ImageMagick command for exposure correction
            # Also includes highlight recovery and shadow enhancement
            cmd = [
                self.imagemagick_path, str(input_path),
                '-modulate', '100,110,100',  # Slightly increase saturation
                '-evaluate', 'multiply', str(2**(adjustment)),  # Exposure adjustment
                '-sigmoidal-contrast', '3,50%',  # Reduce highlights, enhance midtones
                '-auto-level',  # Auto-adjust levels
                '-unsharp', '0x1',  # Slight sharpening
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return True
            else:
                return False
                
        except subprocess.TimeoutExpired:
            return False
        except Exception as e:
            return False

    def process_directory_exposure_correction_parallel(self, photo_dir: Path) -> Path:
        """
        Apply exposure correction to all images in a directory using parallel processing
        
        Args:
            photo_dir: Directory containing photos
            
        Returns:
            Path: Directory containing corrected images (same as input or new corrected folder)
        """
        if not self.enable_exposure_correction:
            return photo_dir
        
        dir_name = photo_dir.name
        
        # Check if already processed
        if dir_name in self.checkpoint_data.get('exposure_corrected', []):
            corrected_dir = photo_dir.parent / f"{dir_name}_corrected"
            if corrected_dir.exists():
                self.logger.info(f"Using existing exposure-corrected images for {dir_name}")
                return corrected_dir
        
        self.logger.info(f"Starting parallel exposure correction for {dir_name} using {self.max_workers} threads")
        
        # Create corrected images directory
        if self.keep_originals:
            corrected_dir = photo_dir.parent / f"{dir_name}_corrected"
            corrected_dir.mkdir(exist_ok=True)
        else:
            corrected_dir = photo_dir
        
        image_files = self.get_image_files(photo_dir)
        
        if not image_files:
            self.logger.warning(f"No images found for exposure correction in {dir_name}")
            return photo_dir
        
        # Prepare tasks for parallel processing
        tasks = []
        for i, image_file in enumerate(image_files):
            # Determine output path
            if self.keep_originals:
                output_file = corrected_dir / image_file.name
            else:
                # Create backup first for in-place processing
                backup_file = photo_dir / f"{image_file.stem}_original{image_file.suffix}"
                if not backup_file.exists():  # Don't overwrite existing backups
                    shutil.copy2(image_file, backup_file)
                output_file = image_file
            
            task_data = {
                'image_path': str(image_file),
                'output_path': str(output_file),
                'adjustment': self.exposure_adjustment,
                'task_id': i + 1
            }
            tasks.append(task_data)
        
        # Process images in parallel
        corrected_count = 0
        overexposed_count = 0
        processed_count = 0
        
        self.logger.info(f"Processing {len(tasks)} images with {self.max_workers} parallel threads...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {executor.submit(self.process_single_image, task): task for task in tasks}
            
            # Process completed tasks
            for future in as_completed(future_to_task):
                result = future.result()
                processed_count += 1
                
                if result['success']:
                    if result['was_overexposed']:
                        overexposed_count += 1
                        if result['corrected']:
                            corrected_count += 1
                
                # Progress update every 10 images or at the end
                with self.progress_lock:
                    if processed_count % 10 == 0 or processed_count == len(tasks):
                        progress_pct = (processed_count / len(tasks)) * 100
                        self.logger.info(f"Progress: {processed_count}/{len(tasks)} images ({progress_pct:.1f}%)")
        
        # Update checkpoint
        if dir_name not in self.checkpoint_data.get('exposure_corrected', []):
            if 'exposure_corrected' not in self.checkpoint_data:
                self.checkpoint_data['exposure_corrected'] = []
            self.checkpoint_data['exposure_corrected'].append(dir_name)
            self.save_checkpoint()
        
        self.logger.info(f"Parallel exposure correction complete for {dir_name}:")
        self.logger.info(f"  Total images: {len(image_files)}")
        self.logger.info(f"  Overexposed detected: {overexposed_count}")
        self.logger.info(f"  Successfully corrected: {corrected_count}")
        self.logger.info(f"  Processing time saved with {self.max_workers} threads!")
        
        return corrected_dir
        """
        Apply exposure correction to all images in a directory
        
        Args:
            photo_dir: Directory containing photos
            
        Returns:
            Path: Directory containing corrected images (same as input or new corrected folder)
        """
        if not self.enable_exposure_correction:
            return photo_dir
        
        dir_name = photo_dir.name
        
        # Check if already processed
        if dir_name in self.checkpoint_data.get('exposure_corrected', []):
            corrected_dir = photo_dir.parent / f"{dir_name}_corrected"
            if corrected_dir.exists():
                self.logger.info(f"Using existing exposure-corrected images for {dir_name}")
                return corrected_dir
        
        self.logger.info(f"Starting exposure correction for {dir_name}")
        
        # Create corrected images directory
        if self.keep_originals:
            corrected_dir = photo_dir.parent / f"{dir_name}_corrected"
            corrected_dir.mkdir(exist_ok=True)
        else:
            corrected_dir = photo_dir
        
        image_files = self.get_image_files(photo_dir)
        
        if not image_files:
            self.logger.warning(f"No images found for exposure correction in {dir_name}")
            return photo_dir
        
        corrected_count = 0
        overexposed_count = 0
        
        for i, image_file in enumerate(image_files, 1):
            self.logger.info(f"Processing image {i}/{len(image_files)}: {image_file.name}")
            
            # Analyze exposure
            exposure_info = self.analyze_image_exposure(image_file)
            
            if exposure_info['is_overexposed']:
                overexposed_count += 1
                
                # Determine output path
                if self.keep_originals:
                    output_file = corrected_dir / image_file.name
                else:
                    # Create backup first
                    backup_file = photo_dir / f"{image_file.stem}_original{image_file.suffix}"
                    shutil.copy2(image_file, backup_file)
                    output_file = image_file
                
                # Apply exposure correction
                success = self.correct_image_exposure(image_file, output_file)
                
                if success:
                    corrected_count += 1
                    self.logger.info(f"✅ Corrected exposure for {image_file.name} (brightness: {exposure_info['mean_brightness']:.1f}%)")
                else:
                    self.logger.error(f"❌ Failed to correct {image_file.name}")
                    # Copy original if correction failed
                    if self.keep_originals and not output_file.exists():
                        shutil.copy2(image_file, output_file)
            else:
                # Image is not overexposed, just copy if needed
                if self.keep_originals:
                    output_file = corrected_dir / image_file.name
                    if not output_file.exists():
                        shutil.copy2(image_file, output_file)
        
        # Update checkpoint
        if dir_name not in self.checkpoint_data.get('exposure_corrected', []):
            if 'exposure_corrected' not in self.checkpoint_data:
                self.checkpoint_data['exposure_corrected'] = []
            self.checkpoint_data['exposure_corrected'].append(dir_name)
            self.save_checkpoint()
        
        self.logger.info(f"Exposure correction complete for {dir_name}:")
        self.logger.info(f"  Total images: {len(image_files)}")
        self.logger.info(f"  Overexposed: {overexposed_count}")
        self.logger.info(f"  Corrected: {corrected_count}")
        
        return corrected_dir
        """Save current progress to checkpoint file"""
        self.checkpoint_data['last_updated'] = datetime.now().isoformat()
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.checkpoint_data, f, indent=2)
            self.logger.info("Checkpoint saved successfully")
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")
    
    def check_directory_ready(self, directory: Path) -> tuple[bool, int]:
        """
        Check if directory has enough images and is ready for processing
        
        Args:
            directory: Directory to check
            
        Returns:
            tuple: (is_ready, image_count)
        """
        image_files = self.get_image_files(directory)
        image_count = len(image_files)
        
        if image_count >= self.min_images:
            return True, image_count
        else:
            self.logger.info(f"Directory {directory.name} has only {image_count} images (minimum: {self.min_images})")
            return False, image_count
    
    def update_queue_status(self, directory: Path):
        """Add directory to queue if not enough images"""
        dir_name = directory.name
        
        # Check if already in queue
        queued_dirs = [item['name'] for item in self.pending_queue]
        if dir_name not in queued_dirs:
            self.pending_queue.append({
                'name': dir_name,
                'path': str(directory),
                'first_check': datetime.now().isoformat(),
                'last_check': datetime.now().isoformat(),
                'check_count': 1
            })
            
            # Also update checkpoint
            if dir_name not in self.checkpoint_data.get('queued', []):
                if 'queued' not in self.checkpoint_data:
                    self.checkpoint_data['queued'] = []
                self.checkpoint_data['queued'].append(dir_name)
                
            self.logger.info(f"Added {dir_name} to pending queue")
        else:
            # Update existing queue entry
            for item in self.pending_queue:
                if item['name'] == dir_name:
                    item['last_check'] = datetime.now().isoformat()
                    item['check_count'] += 1
                    break
    
    def process_pending_queue(self) -> List[Path]:
        """
        Check pending queue for directories that now have enough images
        
        Returns:
            List of directories ready for processing
        """
        ready_directories = []
        still_pending = []
        
        self.logger.info(f"Checking {len(self.pending_queue)} directories in pending queue...")
        
        for item in self.pending_queue:
            directory = Path(item['path'])
            
            if not directory.exists():
                self.logger.warning(f"Directory {item['name']} no longer exists, removing from queue")
                continue
            
            is_ready, image_count = self.check_directory_ready(directory)
            
            if is_ready:
                self.logger.info(f"[READY] Directory {item['name']} now has {image_count} images - ready for processing!")
                ready_directories.append(directory)
                
                # Remove from checkpoint queued list
                if 'queued' in self.checkpoint_data and item['name'] in self.checkpoint_data['queued']:
                    self.checkpoint_data['queued'].remove(item['name'])
            else:
                self.logger.info(f"[PENDING] Directory {item['name']} still has only {image_count} images (check #{item['check_count']})")
                item['last_check'] = datetime.now().isoformat()
                item['check_count'] += 1
                still_pending.append(item)
        
        # Update pending queue
        self.pending_queue = still_pending
        
        if ready_directories:
            self.save_checkpoint()
        
        return ready_directories

    def get_photo_directories(self) -> tuple[List[Path], List[Path]]:
        """
        Get all directories containing photos
        
        Returns:
            tuple: (ready_directories, pending_directories)
        """
        ready_directories = []
        pending_directories = []
        
        for item in self.input_dir.iterdir():
            if item.is_dir():
                # Check if directory contains image files
                image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.raw'}
                has_images = any(
                    file.suffix.lower() in image_extensions 
                    for file in item.iterdir() 
                    if file.is_file()
                )
                
                if has_images:
                    is_ready, image_count = self.check_directory_ready(item)
                    
                    if is_ready:
                        ready_directories.append(item)
                    else:
                        pending_directories.append(item)
                        self.update_queue_status(item)
        
        return sorted(ready_directories), sorted(pending_directories)
    
    def get_image_files(self, directory: Path) -> List[Path]:
        """Get all image files from a directory"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.raw'}
        image_files = []
        
        for file in directory.iterdir():
            if file.is_file() and file.suffix.lower() in image_extensions:
                image_files.append(file)
        
        return sorted(image_files)
    
    def create_realitycapture_project(self, photo_dir: Path, output_path: Path) -> bool:
        """
        Create 3D model using RealityCapture CLI
        
        Args:
            photo_dir: Directory containing photos
            output_path: Path for output model
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get all image files
            image_files = self.get_image_files(photo_dir)
            
            if not image_files:
                self.logger.warning(f"No image files found in {photo_dir}")
                return False
            
            self.logger.info(f"Processing {len(image_files)} images from {photo_dir.name}")
            
            # Create RealityCapture project file path
            project_file = output_path / f"{photo_dir.name}.rcproj"
            
            # RealityCapture CLI commands based on official documentation
            commands = [
                f'"{self.software_exe}"',
                '-headless',  # Run without UI for automation
                f'-addFolder "{photo_dir}"',
                f'-save "{project_file}"',
                '-align',  # Align images
                '-selectMaximalComponent',  # Select largest component
                '-calculateNormalModel',  # Calculate 3D model
                f'-exportSelectedModel "{output_path / (photo_dir.name + ".obj")}" -exportFormat obj',
                '-calculateTexture',  # Calculate texture
                f'-exportSelectedModel "{output_path / (photo_dir.name + "_textured.obj")}" -exportFormat obj',
                f'-save "{project_file}"',
                '-quit'
            ]
            
            # Combine commands into single command line
            full_command = ' '.join(commands)
            
            self.logger.info(f"Executing RealityCapture command for {photo_dir.name}")
            self.logger.debug(f"Command: {full_command}")
            
            # Execute RealityCapture
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=7200  # 2 hour timeout for large datasets
            )
            
            if result.returncode == 0:
                self.logger.info(f"Successfully processed {photo_dir.name}")
                
                # Check if output files were created
                obj_file = output_path / f"{photo_dir.name}.obj"
                textured_obj_file = output_path / f"{photo_dir.name}_textured.obj"
                
                if obj_file.exists():
                    self.logger.info(f"[SUCCESS] Model exported: {obj_file.name}")
                if textured_obj_file.exists():
                    self.logger.info(f"[SUCCESS] Textured model exported: {textured_obj_file.name}")
                
                return True
            else:
                self.logger.error(f"RealityCapture failed for {photo_dir.name}")
                self.logger.error(f"Return code: {result.returncode}")
                self.logger.error(f"Error output: {result.stderr}")
                if result.stdout:
                    self.logger.info(f"Standard output: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"RealityCapture timed out for {photo_dir.name}")
            return False
        except Exception as e:
            self.logger.error(f"Error processing {photo_dir.name}: {str(e)}")
            return False

    def create_realityscan_project(self, photo_dir: Path, output_path: Path) -> bool:
        """
        Create 3D model using RealityScan CLI
        
        Args:
            photo_dir: Directory containing photos
            output_path: Path for output model
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get all image files
            image_files = self.get_image_files(photo_dir)
            
            if not image_files:
                self.logger.warning(f"No image files found in {photo_dir}")
                return False
            
            self.logger.info(f"Processing {len(image_files)} images from {photo_dir.name}")
            
            # Create RealityScan project file path
            project_file = output_path / f"{photo_dir.name}.rsproj"
            
            # RealityScan CLI commands based on official documentation
            # RealityScan uses similar commands to RealityCapture but with different file extensions
            commands = [
                f'"{self.software_exe}"',
                '-headless',  # Run without UI for automation  
                f'-addFolder "{photo_dir}"',
                f'-save "{project_file}"',
                '-align',  # Align images
                '-selectMaximalComponent',  # Select largest component
                '-setReconstructionRegionAuto',  # Set reconstruction region automatically
                '-calculateNormalModel',  # Calculate 3D model
                f'-exportModel "Model 1" "{output_path / (photo_dir.name + ".obj")}"',
                '-calculateTexture',  # Calculate texture
                f'-exportModel "Model 1" "{output_path / (photo_dir.name + "_textured.obj")}"',
                f'-save "{project_file}"',
                '-quit'
            ]
            
            # Combine commands into single command line
            full_command = ' '.join(commands)
            
            self.logger.info(f"Executing RealityScan command for {photo_dir.name}")
            self.logger.debug(f"Command: {full_command}")
            
            # Execute RealityScan
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=7200  # 2 hour timeout for large datasets
            )
            
            if result.returncode == 0:
                self.logger.info(f"Successfully processed {photo_dir.name}")
                
                # Check if output files were created
                obj_file = output_path / f"{photo_dir.name}.obj"
                textured_obj_file = output_path / f"{photo_dir.name}_textured.obj"
                
                if obj_file.exists():
                    self.logger.info(f"[SUCCESS] Model exported: {obj_file.name}")
                if textured_obj_file.exists():
                    self.logger.info(f"[SUCCESS] Textured model exported: {textured_obj_file.name}")
                
                return True
            else:
                self.logger.error(f"RealityScan failed for {photo_dir.name}")
                self.logger.error(f"Return code: {result.returncode}")
                self.logger.error(f"Error output: {result.stderr}")
                if result.stdout:
                    self.logger.info(f"Standard output: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"RealityScan timed out for {photo_dir.name}")
            return False
        except Exception as e:
            self.logger.error(f"Error processing {photo_dir.name} with RealityScan: {str(e)}")
            return False
    
    def process_directory(self, photo_dir: Path) -> bool:
        """Process a single directory"""
        dir_name = photo_dir.name
        
        # Check if already processed
        if dir_name in self.checkpoint_data['processed']:
            self.logger.info(f"Skipping {dir_name} (already processed)")
            return True
        
        # Double-check image count before processing
        is_ready, image_count = self.check_directory_ready(photo_dir)
        if not is_ready:
            self.logger.warning(f"Directory {dir_name} no longer meets minimum image requirement ({image_count} < {self.min_images})")
            self.update_queue_status(photo_dir)
            return False
        
        # Apply exposure correction if enabled (now using parallel processing)
        try:
            corrected_photo_dir = self.process_directory_exposure_correction_parallel(photo_dir)
        except Exception as e:
            self.logger.error(f"Parallel exposure correction failed for {dir_name}: {e}")
            self.logger.info("Proceeding with original images...")
            corrected_photo_dir = photo_dir
        
        # Create output subdirectory
        output_subdir = self.output_dir / dir_name
        output_subdir.mkdir(exist_ok=True)
        
        self.logger.info(f"Starting 3D processing of {dir_name} ({image_count} images)")
        
        # Process with appropriate software
        if self.software_type == "realitycapture":
            success = self.create_realitycapture_project(corrected_photo_dir, output_subdir)
        elif self.software_type == "realityscan":
            success = self.create_realityscan_project(corrected_photo_dir, output_subdir)
        else:
            self.logger.error(f"Unknown software type: {self.software_type}")
            success = False
        
        # Update checkpoint
        if success:
            self.checkpoint_data['processed'].append(dir_name)
            self.logger.info(f"[SUCCESS] Successfully processed {dir_name}")
        else:
            self.checkpoint_data['failed'].append(dir_name)
            self.logger.error(f"[FAILED] Failed to process {dir_name}")
        
        self.save_checkpoint()
        return success
    
    def run(self):
        """Main processing loop with queue management"""
        self.logger.info("Starting 3D model automation")
        self.logger.info(f"Input directory: {self.input_dir}")
        self.logger.info(f"Output directory: {self.output_dir}")
        self.logger.info(f"Software: {self.software_type.upper()}")
        self.logger.info(f"Minimum images required: {self.min_images}")
        
        # Get initial photo directories
        ready_directories, pending_directories = self.get_photo_directories()
        
        self.logger.info(f"Found {len(ready_directories)} directories ready for processing")
        self.logger.info(f"Found {len(pending_directories)} directories with insufficient images (queued)")
        
        if not ready_directories and not pending_directories:
            self.logger.warning("No photo directories found!")
            return
        
        processed_count = len(self.checkpoint_data['processed'])
        self.logger.info(f"Already processed: {processed_count}")
        
        # Process ready directories first
        successful = 0
        failed = 0
        
        if ready_directories:
            self.logger.info(f"\n{'='*60}")
            self.logger.info("PROCESSING READY DIRECTORIES")
            self.logger.info(f"{'='*60}")
            
            for i, photo_dir in enumerate(ready_directories, 1):
                if photo_dir.name in self.checkpoint_data['processed']:
                    continue
                    
                self.logger.info(f"\nProcessing directory {i}/{len(ready_directories)}: {photo_dir.name}")
                self.logger.info(f"Progress: {i/len(ready_directories)*100:.1f}%")
                
                if self.process_directory(photo_dir):
                    successful += 1
                else:
                    failed += 1
        
        # Monitor queue for directories with growing image counts
        if self.pending_queue or pending_directories:
            self.logger.info(f"\n{'='*60}")
            self.logger.info("MONITORING PENDING QUEUE")
            self.logger.info(f"Queue check interval: {self.queue_check_interval} seconds")
            self.logger.info(f"{'='*60}")
            
            queue_check_count = 0
            last_queue_size = len(self.pending_queue)
            
            while self.pending_queue:
                queue_check_count += 1
                self.logger.info(f"\n--- Queue Check #{queue_check_count} ---")
                self.logger.info(f"Pending directories: {len(self.pending_queue)}")
                
                # Check if any queued directories are now ready
                newly_ready = self.process_pending_queue()
                
                if newly_ready:
                    self.logger.info(f"Processing {len(newly_ready)} newly ready directories...")
                    
                    for photo_dir in newly_ready:
                        self.logger.info(f"\nProcessing queued directory: {photo_dir.name}")
                        
                        if self.process_directory(photo_dir):
                            successful += 1
                        else:
                            failed += 1
                
                # Break if queue hasn't changed for several checks (no new files being copied)
                current_queue_size = len(self.pending_queue)
                if current_queue_size == last_queue_size and queue_check_count > 5:
                    time_waiting = queue_check_count * self.queue_check_interval
                    self.logger.info(f"Queue size unchanged for {time_waiting} seconds. Assuming copy operations complete.")
                    
                    # Log remaining directories that didn't meet threshold
                    if self.pending_queue:
                        self.logger.info("Directories still below minimum image threshold:")
                        for item in self.pending_queue:
                            dir_path = Path(item['path'])
                            if dir_path.exists():
                                _, current_count = self.check_directory_ready(dir_path)
                                self.logger.info(f"  - {item['name']}: {current_count} images")
                    break
                
                last_queue_size = current_queue_size
                
                if self.pending_queue:  # Only sleep if there are still pending items
                    self.logger.info(f"Waiting {self.queue_check_interval} seconds before next check...")
                    time.sleep(self.queue_check_interval)
        
        # Final summary
        total_processed = successful + failed
        self.logger.info(f"\n{'='*60}")
        self.logger.info("PROCESSING COMPLETE")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Directories processed this session: {total_processed}")
        self.logger.info(f"Successfully processed: {successful}")
        self.logger.info(f"Failed: {failed}")
        
        if total_processed > 0:
            self.logger.info(f"Success rate: {successful/total_processed*100:.1f}%")
        
        total_in_checkpoint = len(self.checkpoint_data['processed'])
        self.logger.info(f"Total processed (including previous runs): {total_in_checkpoint}")
        
        if self.checkpoint_data.get('failed'):
            self.logger.info(f"Failed directories: {', '.join(self.checkpoint_data['failed'])}")
        
        if self.pending_queue:
            pending_names = [item['name'] for item in self.pending_queue]
            self.logger.info(f"Still pending (insufficient images): {', '.join(pending_names)}")
            self.logger.info("Tip: Run the script again later if copy operations are still in progress")

def main():
    parser = argparse.ArgumentParser(description='Automate 3D model creation with RealityCapture or RealityScan')
    parser.add_argument('input_dir', help='Input directory containing photo folders')
    parser.add_argument('output_dir', help='Output directory for 3D models')
    parser.add_argument('software_exe', help='Path to RealityCapture.exe or RealityScan.exe')
    parser.add_argument('--software-type', choices=['realitycapture', 'realityscan', 'auto'], 
                       default='auto', help='Software type (default: auto-detect)')
    parser.add_argument('--checkpoint', default='processing_checkpoint.json', 
                       help='Checkpoint file path (default: processing_checkpoint.json)')
    parser.add_argument('--min-images', type=int, default=300,
                       help='Minimum number of images required (default: 300)')
    parser.add_argument('--queue-interval', type=int, default=300,
                       help='Queue check interval in seconds (default: 300)')
    
    # Exposure correction arguments
    parser.add_argument('--disable-exposure-correction', action='store_true',
                       help='Disable automatic exposure correction')
    parser.add_argument('--imagemagick-path', default='magick',
                       help='Path to ImageMagick executable (default: magick)')
    parser.add_argument('--exposure-adjustment', type=float, default=-0.5,
                       help='Exposure adjustment in stops, negative = darker (default: -0.5)')
    parser.add_argument('--no-keep-originals', action='store_true',
                       help='Overwrite original images instead of creating copies')
    # Threading arguments
    parser.add_argument('--max-workers', type=int, default=4,
                       help='Number of parallel threads for image processing (default: 4)')
    
    args = parser.parse_args()
    
    # Validate paths
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        sys.exit(1)
    
    if not os.path.exists(args.software_exe):
        print(f"Error: Software executable '{args.software_exe}' does not exist")
        sys.exit(1)
    
    # Test ImageMagick if exposure correction is enabled
    if not args.disable_exposure_correction:
        try:
            result = subprocess.run([args.imagemagick_path, '-version'], 
                                   capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print(f"Error: ImageMagick not found at '{args.imagemagick_path}'")
                print("Install ImageMagick or use --disable-exposure-correction")
                sys.exit(1)
        except FileNotFoundError:
            print(f"Error: ImageMagick not found at '{args.imagemagick_path}'")
            print("Install ImageMagick or use --disable-exposure-correction")
            sys.exit(1)
        except Exception as e:
            print(f"Error testing ImageMagick: {e}")
            sys.exit(1)
    
    # Create and run automator
    automator = PhotogrammetryAutomator(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        software_exe=args.software_exe,
        software_type=args.software_type,
        checkpoint_file=args.checkpoint,
        min_images=args.min_images,
        queue_check_interval=args.queue_interval,
        enable_exposure_correction=not args.disable_exposure_correction,
        imagemagick_path=args.imagemagick_path,
        exposure_adjustment=args.exposure_adjustment,
        keep_originals=not args.no_keep_originals,
        max_workers=args.max_workers
    )
    
    try:
        automator.run()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()