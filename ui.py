#!/usr/bin/env python3
"""
Modern GUI for 3D Model Creation Automation Script
Provides a user-friendly interface for RealityCapture and RealityScan automation
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import queue
import os
import sys
import json
from pathlib import Path
import logging
from datetime import datetime
from PIL import Image, ImageTk
import math

# Import our main automation class
from main import PhotogrammetryAutomator

# Set appearance mode and color theme
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class LogHandler(logging.Handler):
    """Custom logging handler to redirect logs to UI"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        log_entry = self.format(record)
        self.log_queue.put(log_entry)

class PhotogrammetryUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Morfi.gr - 3D Model Generator")
        self.root.geometry("1600x900")
        self.root.minsize(1400, 800)
        
        # Initialize variables
        self.automator = None
        self.processing_thread = None
        self.is_processing = False
        self.log_queue = queue.Queue()
        
        # Load saved settings
        self.settings_file = "ui_settings.json"
        self.settings = self.load_settings()
        
        # Setup UI
        self.setup_ui()
        
        # Setup logging
        self.setup_logging()
        
        # Start log update timer
        self.update_logs()
        
        # Apply saved settings
        self.apply_settings()
        
    def load_settings(self):
        """Load UI settings from file"""
        default_settings = {
            "input_dir": "",
            "output_dir": "",
            "software_exe": "",
            "software_type": "auto",
            "min_images": 300,
            "queue_interval": 300,
            "enable_exposure_correction": True,
            "imagemagick_path": "magick",
            "exposure_adjustment": -0.5,
            "keep_originals": True,
            "max_workers": 4,
            "checkpoint_file": "processing_checkpoint.json",
            "database_file": "processing_database.db"
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    saved_settings = json.load(f)
                    default_settings.update(saved_settings)
        except Exception as e:
            print(f"Error loading settings: {e}")
        
        return default_settings
    
    def save_settings(self):
        """Save current UI settings"""
        settings = {
            "input_dir": self.input_dir_var.get(),
            "output_dir": self.output_dir_var.get(),
            "software_exe": self.software_exe_var.get(),
            "software_type": self.software_type_var.get(),
            "min_images": self.min_images_var.get(),
            "queue_interval": self.queue_interval_var.get(),
            "enable_exposure_correction": self.enable_exposure_var.get(),
            "imagemagick_path": self.imagemagick_path_var.get(),
            "exposure_adjustment": self.exposure_adjustment_var.get(),
            "keep_originals": self.keep_originals_var.get(),
            "max_workers": self.max_workers_var.get(),
            "checkpoint_file": self.checkpoint_file_var.get(),
            "database_file": self.database_file_var.get()
        }
        
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def setup_ui(self):
        """Setup the main UI components"""
        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        
        # Title
        title_label = ctk.CTkLabel(
            self.root, 
            text="Morfi.gr - 3D Model Generator", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.grid(row=0, column=0, pady=20, padx=20, sticky="ew")
        
        # Main container
        main_frame = ctk.CTkFrame(self.root)
        main_frame.grid(row=1, column=0, pady=(0, 20), padx=20, sticky="nsew")
        main_frame.grid_columnconfigure((0, 1, 2), weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # Left panel for settings
        self.setup_settings_panel(main_frame)
        
        # Middle panel for photo preview
        self.setup_preview_panel(main_frame)
        
        # Right panel for logs and controls
        self.setup_control_panel(main_frame)
        
    def setup_settings_panel(self, parent):
        """Setup the settings configuration panel"""
        settings_frame = ctk.CTkScrollableFrame(parent, label_text="Configuration")
        settings_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        settings_frame.grid_columnconfigure(1, weight=1)
        
        # Initialize StringVars and other variables
        self.input_dir_var = ctk.StringVar()
        self.output_dir_var = ctk.StringVar()
        self.software_exe_var = ctk.StringVar()
        self.software_type_var = ctk.StringVar(value="auto")
        self.min_images_var = ctk.IntVar(value=300)
        self.queue_interval_var = ctk.IntVar(value=300)
        self.enable_exposure_var = ctk.BooleanVar(value=True)
        self.imagemagick_path_var = ctk.StringVar(value="magick")
        self.exposure_adjustment_var = ctk.DoubleVar(value=-0.5)
        self.keep_originals_var = ctk.BooleanVar(value=True)
        self.max_workers_var = ctk.IntVar(value=4)
        self.checkpoint_file_var = ctk.StringVar(value="processing_checkpoint.json")
        self.database_file_var = ctk.StringVar(value="processing_database.db")
        
        row = 0
        
        # Input Directory
        ctk.CTkLabel(settings_frame, text="Input Directory:").grid(row=row, column=0, sticky="w", pady=5)
        input_frame = ctk.CTkFrame(settings_frame)
        input_frame.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
        input_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(input_frame, textvariable=self.input_dir_var).grid(row=0, column=0, sticky="ew", padx=(5, 0))
        ctk.CTkButton(
            input_frame, 
            text="Browse", 
            command=self.browse_input_dir,
            width=80
        ).grid(row=0, column=1, padx=5)
        row += 1
        
        # Output Directory
        ctk.CTkLabel(settings_frame, text="Output Directory:").grid(row=row, column=0, sticky="w", pady=5)
        output_frame = ctk.CTkFrame(settings_frame)
        output_frame.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
        output_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(output_frame, textvariable=self.output_dir_var).grid(row=0, column=0, sticky="ew", padx=(5, 0))
        ctk.CTkButton(
            output_frame, 
            text="Browse", 
            command=self.browse_output_dir,
            width=80
        ).grid(row=0, column=1, padx=5)
        row += 1
        
        # Software Executable
        ctk.CTkLabel(settings_frame, text="Software Executable:").grid(row=row, column=0, sticky="w", pady=5)
        software_frame = ctk.CTkFrame(settings_frame)
        software_frame.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
        software_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(software_frame, textvariable=self.software_exe_var).grid(row=0, column=0, sticky="ew", padx=(5, 0))
        ctk.CTkButton(
            software_frame, 
            text="Browse", 
            command=self.browse_software_exe,
            width=80
        ).grid(row=0, column=1, padx=5)
        row += 1
        
        # Software Type
        ctk.CTkLabel(settings_frame, text="Software Type:").grid(row=row, column=0, sticky="w", pady=5)
        ctk.CTkOptionMenu(
            settings_frame, 
            values=["auto", "realitycapture", "realityscan"],
            variable=self.software_type_var
        ).grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
        row += 1
        
        # Separator
        ctk.CTkLabel(settings_frame, text="Basic Settings", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(20, 10)
        )
        row += 1
        
        # Minimum Images
        ctk.CTkLabel(settings_frame, text="Minimum Images:").grid(row=row, column=0, sticky="w", pady=5)
        ctk.CTkEntry(settings_frame, textvariable=self.min_images_var, width=100).grid(
            row=row, column=1, sticky="w", padx=(10, 0), pady=5
        )
        row += 1
        
        # Queue Check Interval
        ctk.CTkLabel(settings_frame, text="Queue Check Interval (s):").grid(row=row, column=0, sticky="w", pady=5)
        ctk.CTkEntry(settings_frame, textvariable=self.queue_interval_var, width=100).grid(
            row=row, column=1, sticky="w", padx=(10, 0), pady=5
        )
        row += 1
        
        # Checkpoint File
        ctk.CTkLabel(settings_frame, text="Checkpoint File:").grid(row=row, column=0, sticky="w", pady=5)
        ctk.CTkEntry(settings_frame, textvariable=self.checkpoint_file_var).grid(
            row=row, column=1, sticky="ew", padx=(10, 0), pady=5
        )
        row += 1
        
        # Database File
        ctk.CTkLabel(settings_frame, text="Database File:").grid(row=row, column=0, sticky="w", pady=5)
        ctk.CTkEntry(settings_frame, textvariable=self.database_file_var).grid(
            row=row, column=1, sticky="ew", padx=(10, 0), pady=5
        )
        row += 1
        
        # Exposure Correction Section
        ctk.CTkLabel(settings_frame, text="Exposure Correction", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(20, 10)
        )
        row += 1
        
        # Enable Exposure Correction
        ctk.CTkCheckBox(
            settings_frame, 
            text="Enable Exposure Correction",
            variable=self.enable_exposure_var,
            command=self.toggle_exposure_settings
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        row += 1
        
        # ImageMagick Path
        ctk.CTkLabel(settings_frame, text="ImageMagick Path:").grid(row=row, column=0, sticky="w", pady=5)
        self.imagemagick_entry = ctk.CTkEntry(settings_frame, textvariable=self.imagemagick_path_var)
        self.imagemagick_entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
        row += 1
        
        # Exposure Adjustment
        ctk.CTkLabel(settings_frame, text="Exposure Adjustment:").grid(row=row, column=0, sticky="w", pady=5)
        self.exposure_slider = ctk.CTkSlider(
            settings_frame, 
            from_=-2.0, 
            to=2.0, 
            variable=self.exposure_adjustment_var,
            number_of_steps=40
        )
        self.exposure_slider.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
        row += 1
        
        # Exposure value label
        self.exposure_label = ctk.CTkLabel(settings_frame, text="")
        self.exposure_label.grid(row=row, column=1, sticky="w", padx=(10, 0))
        self.exposure_adjustment_var.trace("w", self.update_exposure_label)
        row += 1
        
        # Keep Originals
        self.keep_originals_checkbox = ctk.CTkCheckBox(
            settings_frame, 
            text="Keep Original Images",
            variable=self.keep_originals_var
        )
        self.keep_originals_checkbox.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        row += 1
        
        # Max Workers
        ctk.CTkLabel(settings_frame, text="Max Worker Threads:").grid(row=row, column=0, sticky="w", pady=5)
        self.max_workers_entry = ctk.CTkEntry(settings_frame, textvariable=self.max_workers_var, width=100)
        self.max_workers_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=5)
        row += 1
        
        # Save Settings Button
        ctk.CTkButton(
            settings_frame, 
            text="Save Settings", 
            command=self.save_settings
        ).grid(row=row, column=0, columnspan=2, pady=20)
        
    def setup_preview_panel(self, parent):
        """Setup the photo preview panel"""
        preview_frame = ctk.CTkFrame(parent)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=10)
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_rowconfigure(3, weight=1)
        
        # Title
        ctk.CTkLabel(
            preview_frame, 
            text="Photo Preview", 
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, pady=10, sticky="ew")
        
        # Directory selection
        dir_select_frame = ctk.CTkFrame(preview_frame)
        dir_select_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        dir_select_frame.grid_columnconfigure(0, weight=1)
        
        self.preview_dir_var = ctk.StringVar()
        self.preview_dir_combo = ctk.CTkComboBox(
            dir_select_frame,
            values=["No directories found"],
            variable=self.preview_dir_var,
            command=self.on_preview_dir_selected
        )
        self.preview_dir_combo.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        refresh_btn = ctk.CTkButton(
            dir_select_frame,
            text="Refresh",
            command=self.refresh_preview_directories,
            width=80
        )
        refresh_btn.grid(row=0, column=1, padx=5, pady=5)
        
        # Photo info display
        info_frame = ctk.CTkFrame(preview_frame)
        info_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        
        self.photo_info_label = ctk.CTkLabel(
            info_frame,
            text="Select a directory to preview photos",
            font=ctk.CTkFont(size=12)
        )
        self.photo_info_label.grid(row=0, column=0, pady=5)
        
        # Photo thumbnails container
        self.thumbnails_frame = ctk.CTkScrollableFrame(preview_frame, label_text="Photos")
        self.thumbnails_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        self.thumbnails_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Initialize photo data
        self.current_photos = []
        self.photo_thumbnails = []
        
    def setup_control_panel(self, parent):
        """Setup the control and logging panel"""
        control_frame = ctk.CTkFrame(parent)
        control_frame.grid(row=0, column=2, sticky="nsew")
        control_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_rowconfigure(1, weight=1)
        
        # Control buttons
        button_frame = ctk.CTkFrame(control_frame)
        button_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.start_button = ctk.CTkButton(
            button_frame, 
            text="Start Processing", 
            command=self.start_processing,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.start_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.stop_button = ctk.CTkButton(
            button_frame, 
            text="Stop Processing", 
            command=self.stop_processing,
            fg_color="red",
            hover_color="darkred",
            state="disabled"
        )
        self.stop_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.validate_button = ctk.CTkButton(
            button_frame, 
            text="Validate Settings", 
            command=self.validate_settings
        )
        self.validate_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        # Status
        self.status_label = ctk.CTkLabel(
            control_frame, 
            text="Ready", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.status_label.grid(row=1, column=0, pady=5)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(control_frame)
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        self.progress_bar.set(0)
        
        # Database Status
        stats_frame = ctk.CTkFrame(control_frame)
        stats_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        ctk.CTkLabel(stats_frame, text="Database Status", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=4, pady=(10, 5)
        )
        
        self.pending_label = ctk.CTkLabel(stats_frame, text="Pending: 0")
        self.pending_label.grid(row=1, column=0, padx=5, pady=2)
        
        self.completed_label = ctk.CTkLabel(stats_frame, text="Completed: 0")
        self.completed_label.grid(row=1, column=1, padx=5, pady=2)
        
        self.failed_label = ctk.CTkLabel(stats_frame, text="Failed: 0")
        self.failed_label.grid(row=1, column=2, padx=5, pady=2)
        
        self.queued_label = ctk.CTkLabel(stats_frame, text="Queued: 0")
        self.queued_label.grid(row=1, column=3, padx=5, pady=2)
        
        # Database control buttons
        db_button_frame = ctk.CTkFrame(stats_frame)
        db_button_frame.grid(row=2, column=0, columnspan=4, pady=5)
        
        ctk.CTkButton(
            db_button_frame, 
            text="Refresh Stats", 
            command=self.refresh_database_stats,
            width=100
        ).grid(row=0, column=0, padx=5, pady=5)
        
        ctk.CTkButton(
            db_button_frame, 
            text="Reset Failed", 
            command=self.reset_failed_directories,
            width=100
        ).grid(row=0, column=1, padx=5, pady=5)
        
        # Log output
        log_frame = ctk.CTkFrame(control_frame)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=10)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(log_frame, text="Log Output", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 5)
        )
        
        self.log_text = ctk.CTkTextbox(log_frame, state="disabled")
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Clear log button
        ctk.CTkButton(
            log_frame, 
            text="Clear Log", 
            command=self.clear_log,
            width=100
        ).grid(row=2, column=0, pady=(0, 10))
        
    def setup_logging(self):
        """Setup logging to capture automator output"""
        # Create custom handler
        self.log_handler = LogHandler(self.log_queue)
        self.log_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        
    def apply_settings(self):
        """Apply loaded settings to UI"""
        self.input_dir_var.set(self.settings["input_dir"])
        self.output_dir_var.set(self.settings["output_dir"])
        self.software_exe_var.set(self.settings["software_exe"])
        self.software_type_var.set(self.settings["software_type"])
        self.min_images_var.set(self.settings["min_images"])
        self.queue_interval_var.set(self.settings["queue_interval"])
        self.enable_exposure_var.set(self.settings["enable_exposure_correction"])
        self.imagemagick_path_var.set(self.settings["imagemagick_path"])
        self.exposure_adjustment_var.set(self.settings["exposure_adjustment"])
        self.keep_originals_var.set(self.settings["keep_originals"])
        self.max_workers_var.set(self.settings["max_workers"])
        self.checkpoint_file_var.set(self.settings["checkpoint_file"])
        self.database_file_var.set(self.settings["database_file"])
        
        # Update exposure settings state
        self.toggle_exposure_settings()
        self.update_exposure_label()
        
        # Refresh database stats on startup
        try:
            self.refresh_database_stats()
        except Exception:
            pass  # Database might not exist yet
        
        # Refresh preview directories on startup
        if self.input_dir_var.get():
            self.refresh_preview_directories()
        
    def browse_input_dir(self):
        """Browse for input directory"""
        directory = filedialog.askdirectory(title="Select Input Directory")
        if directory:
            self.input_dir_var.set(directory)
            # Refresh preview directories when input directory changes
            self.refresh_preview_directories()
            
    def browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir_var.set(directory)
            
    def browse_software_exe(self):
        """Browse for software executable"""
        file_path = filedialog.askopenfilename(
            title="Select RealityCapture or RealityScan Executable",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        if file_path:
            self.software_exe_var.set(file_path)
            
    def toggle_exposure_settings(self):
        """Enable/disable exposure correction settings"""
        enabled = self.enable_exposure_var.get()
        state = "normal" if enabled else "disabled"
        
        self.imagemagick_entry.configure(state=state)
        self.exposure_slider.configure(state=state)
        self.keep_originals_checkbox.configure(state=state)
        self.max_workers_entry.configure(state=state)
        
    def update_exposure_label(self, *args):
        """Update exposure adjustment label"""
        value = self.exposure_adjustment_var.get()
        self.exposure_label.configure(text=f"{value:.1f} stops")
    
    def get_image_files(self, directory):
        """Get image files from directory"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.raw', '.cr2', '.nef', '.arw'}
        image_files = []
        
        try:
            directory_path = Path(directory)
            if directory_path.exists() and directory_path.is_dir():
                for file in directory_path.iterdir():
                    if file.is_file() and file.suffix.lower() in image_extensions:
                        image_files.append(file)
        except Exception as e:
            print(f"Error reading directory {directory}: {e}")
        
        return sorted(image_files)
    
    def refresh_preview_directories(self):
        """Refresh the list of available directories for preview"""
        input_dir = self.input_dir_var.get()
        
        if not input_dir or not Path(input_dir).exists():
            self.preview_dir_combo.configure(values=["No input directory set"])
            return
        
        try:
            directories = []
            input_path = Path(input_dir)
            
            for item in input_path.iterdir():
                if item.is_dir():
                    # Check if directory contains images
                    image_files = self.get_image_files(item)
                    if image_files:
                        directories.append(item.name)
            
            if directories:
                self.preview_dir_combo.configure(values=directories)
                if directories:
                    self.preview_dir_var.set(directories[0])
                    self.on_preview_dir_selected(directories[0])
            else:
                self.preview_dir_combo.configure(values=["No directories with images found"])
                self.clear_photo_preview()
                
        except Exception as e:
            self.preview_dir_combo.configure(values=["Error reading directories"])
            print(f"Error refreshing directories: {e}")
    
    def on_preview_dir_selected(self, selected_dir):
        """Handle directory selection for preview"""
        if not selected_dir or selected_dir in ["No directories found", "No input directory set", "Error reading directories"]:
            self.clear_photo_preview()
            return
        
        input_dir = self.input_dir_var.get()
        if not input_dir:
            return
        
        directory_path = Path(input_dir) / selected_dir
        self.load_photo_preview(directory_path)
    
    def clear_photo_preview(self):
        """Clear the photo preview area"""
        # Clear existing thumbnails
        for widget in self.thumbnails_frame.winfo_children():
            widget.destroy()
        
        self.current_photos = []
        self.photo_thumbnails = []
        self.photo_info_label.configure(text="No photos to display")
    
    def load_photo_preview(self, directory_path):
        """Load and display photo thumbnails"""
        try:
            # Clear existing preview
            self.clear_photo_preview()
            
            # Get image files
            image_files = self.get_image_files(directory_path)
            
            if not image_files:
                self.photo_info_label.configure(text="No images found in selected directory")
                return
            
            # Update info label
            total_size = sum(f.stat().st_size for f in image_files) / (1024 * 1024)  # MB
            self.photo_info_label.configure(
                text=f"Found {len(image_files)} images, Total size: {total_size:.1f} MB"
            )
            
            # Load thumbnails (limit to first 20 for performance)
            max_thumbnails = 20
            display_files = image_files[:max_thumbnails]
            
            if len(image_files) > max_thumbnails:
                self.photo_info_label.configure(
                    text=f"Showing {max_thumbnails} of {len(image_files)} images, Total size: {total_size:.1f} MB"
                )
            
            # Create thumbnails in a grid
            cols = 4
            for i, image_file in enumerate(display_files):
                row = i // cols
                col = i % cols
                
                try:
                    # Load and resize image
                    with Image.open(image_file) as img:
                        # Create thumbnail
                        img.thumbnail((150, 150), Image.Resampling.LANCZOS)
                        
                        # Convert to PhotoImage
                        photo = ImageTk.PhotoImage(img)
                        
                        # Create frame for thumbnail
                        thumb_frame = ctk.CTkFrame(self.thumbnails_frame)
                        thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                        
                        # Create label with image
                        img_label = ctk.CTkLabel(
                            thumb_frame,
                            image=photo,
                            text="",
                        )
                        img_label.grid(row=0, column=0, padx=5, pady=5)
                        
                        # Create filename label
                        name_label = ctk.CTkLabel(
                            thumb_frame,
                            text=image_file.name[:15] + "..." if len(image_file.name) > 15 else image_file.name,
                            font=ctk.CTkFont(size=10)
                        )
                        name_label.grid(row=1, column=0, padx=5, pady=(0, 5))
                        
                        # Keep reference to prevent garbage collection
                        self.photo_thumbnails.append(photo)
                        self.current_photos.append(image_file)
                        
                        # Add click handler to show full size
                        img_label.bind("<Button-1>", lambda e, path=image_file: self.show_full_image(path))
                        
                except Exception as e:
                    print(f"Error loading thumbnail for {image_file.name}: {e}")
                    # Create error placeholder
                    thumb_frame = ctk.CTkFrame(self.thumbnails_frame)
                    thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                    
                    error_label = ctk.CTkLabel(
                        thumb_frame,
                        text="Error\nloading\nimage",
                        font=ctk.CTkFont(size=10)
                    )
                    error_label.grid(row=0, column=0, padx=5, pady=5)
                    
        except Exception as e:
            self.photo_info_label.configure(text=f"Error loading photos: {str(e)}")
            print(f"Error in load_photo_preview: {e}")
    
    def show_full_image(self, image_path):
        """Show full size image in a popup window"""
        try:
            # Create new window
            popup = ctk.CTkToplevel(self.root)
            popup.title(f"Image Viewer - {image_path.name}")
            popup.geometry("800x600")
            
            # Load and display image
            with Image.open(image_path) as img:
                # Calculate size to fit window while maintaining aspect ratio
                display_size = (750, 550)
                img.thumbnail(display_size, Image.Resampling.LANCZOS)
                
                photo = ImageTk.PhotoImage(img)
                
                # Create and pack image label
                img_label = ctk.CTkLabel(popup, image=photo, text="")
                img_label.pack(expand=True, fill="both", padx=10, pady=10)
                
                # Info label
                file_size = image_path.stat().st_size / (1024 * 1024)  # MB
                info_text = f"File: {image_path.name}\nSize: {file_size:.2f} MB\nDimensions: {img.size[0]}x{img.size[1]}"
                
                info_label = ctk.CTkLabel(popup, text=info_text)
                info_label.pack(pady=5)
                
                # Keep reference to prevent garbage collection
                popup.photo = photo
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not display image: {str(e)}")
        
    def validate_settings(self):
        """Validate current settings"""
        errors = []
        
        # Check input directory
        if not self.input_dir_var.get():
            errors.append("Input directory is required")
        elif not os.path.exists(self.input_dir_var.get()):
            errors.append("Input directory does not exist")
            
        # Check output directory
        if not self.output_dir_var.get():
            errors.append("Output directory is required")
            
        # Check software executable
        if not self.software_exe_var.get():
            errors.append("Software executable is required")
        elif not os.path.exists(self.software_exe_var.get()):
            errors.append("Software executable does not exist")
            
        # Check ImageMagick if exposure correction is enabled
        if self.enable_exposure_var.get():
            try:
                import subprocess
                result = subprocess.run(
                    [self.imagemagick_path_var.get(), '-version'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    errors.append("ImageMagick test failed")
            except FileNotFoundError:
                errors.append(f"ImageMagick not found at: {self.imagemagick_path_var.get()}")
            except Exception as e:
                errors.append(f"ImageMagick error: {str(e)}")
        
        if errors:
            error_msg = "Validation errors:\n\n" + "\n".join(f"• {error}" for error in errors)
            messagebox.showerror("Validation Failed", error_msg)
            return False
        else:
            messagebox.showinfo("Validation Successful", "All settings are valid!")
            return True
            
    def start_processing(self):
        """Start the processing in a separate thread"""
        if not self.validate_settings():
            return
            
        if self.is_processing:
            messagebox.showwarning("Already Processing", "Processing is already in progress")
            return
            
        # Update UI state
        self.is_processing = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_label.configure(text="Processing...")
        self.progress_bar.set(0.5)  # Indeterminate progress
        
        # Save current settings
        self.save_settings()
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self.run_processing, daemon=True)
        self.processing_thread.start()
        
    def run_processing(self):
        """Run the processing (called in separate thread)"""
        try:
            # Create automator instance
            self.automator = PhotogrammetryAutomator(
                input_dir=self.input_dir_var.get(),
                output_dir=self.output_dir_var.get(),
                software_exe=self.software_exe_var.get(),
                software_type=self.software_type_var.get(),
                checkpoint_file=self.checkpoint_file_var.get(),
                database_file=self.database_file_var.get(),
                min_images=self.min_images_var.get(),
                queue_check_interval=self.queue_interval_var.get(),
                enable_exposure_correction=self.enable_exposure_var.get(),
                imagemagick_path=self.imagemagick_path_var.get(),
                exposure_adjustment=self.exposure_adjustment_var.get(),
                keep_originals=self.keep_originals_var.get(),
                max_workers=self.max_workers_var.get()
            )
            
            # Add our log handler to capture output
            automator_logger = logging.getLogger('main')
            automator_logger.addHandler(self.log_handler)
            
            # Run the automator
            self.automator.run()
            
            # Processing completed successfully
            self.log_queue.put("INFO: Processing completed successfully!")
            
        except Exception as e:
            self.log_queue.put(f"ERROR: Processing failed: {str(e)}")
        finally:
            # Reset UI state
            self.root.after(0, self.processing_finished)
            
    def stop_processing(self):
        """Stop the processing"""
        if self.is_processing and self.automator:
            # Note: This is a simple stop - for more graceful stopping,
            # you might want to add a stop flag to the PhotogrammetryAutomator class
            self.log_queue.put("INFO: Stop requested by user")
            self.processing_finished()
            
    def processing_finished(self):
        """Reset UI after processing is finished"""
        self.is_processing = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="Ready")
        self.progress_bar.set(0)
        
        # Refresh database stats after processing
        try:
            self.refresh_database_stats()
        except Exception:
            pass
        
    def update_logs(self):
        """Update log display with new messages"""
        try:
            while True:
                log_message = self.log_queue.get_nowait()
                
                # Add timestamp and message to log
                timestamp = datetime.now().strftime("%H:%M:%S")
                formatted_message = f"[{timestamp}] {log_message}\n"
                
                # Update log text widget
                self.log_text.configure(state="normal")
                self.log_text.insert("end", formatted_message)
                self.log_text.see("end")  # Scroll to bottom
                self.log_text.configure(state="disabled")
                
        except queue.Empty:
            pass
        
        # Schedule next update
        self.root.after(100, self.update_logs)
        
    def clear_log(self):
        """Clear the log display"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
    
    def refresh_database_stats(self):
        """Refresh database statistics display"""
        try:
            from database import ProcessingDatabase
            db = ProcessingDatabase(self.database_file_var.get())
            
            stats = db.get_processing_stats()
            status_counts = stats.get('status_counts', {})
            
            self.pending_label.configure(text=f"Pending: {status_counts.get('pending', 0)}")
            self.completed_label.configure(text=f"Completed: {status_counts.get('completed', 0)}")
            self.failed_label.configure(text=f"Failed: {status_counts.get('failed', 0)}")
            self.queued_label.configure(text=f"Queued: {status_counts.get('queued', 0)}")
            
            self.log_queue.put(f"INFO: Database stats refreshed - {len(status_counts)} status types found")
            
        except Exception as e:
            self.log_queue.put(f"ERROR: Failed to refresh database stats: {str(e)}")
    
    def reset_failed_directories(self):
        """Reset failed directories to pending status"""
        try:
            from database import ProcessingDatabase
            db = ProcessingDatabase(self.database_file_var.get())
            
            # Get failed directories
            failed_dirs = db.get_failed_directories()
            
            if not failed_dirs:
                messagebox.showinfo("No Failed Directories", "No failed directories found to reset.")
                return
            
            # Ask for confirmation
            result = messagebox.askyesno(
                "Reset Failed Directories", 
                f"Reset {len(failed_dirs)} failed directories to pending status?\n\n"
                f"Failed directories: {', '.join([d['name'] for d in failed_dirs[:5]])}..."
            )
            
            if result:
                # Reset failed directories to pending
                for dir_info in failed_dirs:
                    db.update_directory_status(dir_info['name'], 'pending')
                
                self.log_queue.put(f"INFO: Reset {len(failed_dirs)} failed directories to pending status")
                self.refresh_database_stats()
                messagebox.showinfo("Reset Complete", f"Successfully reset {len(failed_dirs)} directories.")
            
        except Exception as e:
            error_msg = f"Failed to reset failed directories: {str(e)}"
            self.log_queue.put(f"ERROR: {error_msg}")
            messagebox.showerror("Reset Failed", error_msg)
        
    def run(self):
        """Start the UI main loop"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
        
    def on_closing(self):
        """Handle application closing"""
        if self.is_processing:
            result = messagebox.askyesno(
                "Processing Active", 
                "Processing is currently active. Are you sure you want to exit?"
            )
            if not result:
                return
                
        # Save settings before closing
        self.save_settings()
        
        # Close application
        self.root.destroy()

def main():
    """Main entry point"""
    try:
        import customtkinter
    except ImportError:
        print("CustomTkinter is required but not installed.")
        print("Install it with: pip install customtkinter")
        sys.exit(1)
        
    app = PhotogrammetryUI()
    app.run()

if __name__ == "__main__":
    main() 