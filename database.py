#!/usr/bin/env python3
"""
Database module for tracking 3D model processing status
Manages processed and non-processed directories with SQLite
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import logging

class ProcessingDatabase:
    def __init__(self, db_path: str = "processing_database.db"):
        """
        Initialize the processing database
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                
                # Create directories table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS directories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        full_path TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        image_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_at TIMESTAMP NULL,
                        error_message TEXT NULL,
                        processing_time_seconds INTEGER DEFAULT 0,
                        file_size_mb REAL DEFAULT 0.0,
                        has_exposure_correction BOOLEAN DEFAULT FALSE
                    )
                ''')
                
                # Create processing_log table for detailed history
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS processing_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        directory_id INTEGER,
                        action TEXT NOT NULL,
                        message TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (directory_id) REFERENCES directories (id)
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_directories_status ON directories (status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_directories_name ON directories (name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_processing_log_directory_id ON processing_log (directory_id)')
                
                conn.commit()
                self.logger.info(f"Database initialized: {self.db_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def add_directory(self, name: str, full_path: str, image_count: int = 0, 
                     file_size_mb: float = 0.0) -> int:
        """
        Add a new directory to track or update existing one
        
        Args:
            name: Directory name
            full_path: Full path to directory
            image_count: Number of images in directory
            file_size_mb: Total size in MB
            
        Returns:
            Directory ID
        """
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                
                # Check if directory already exists
                cursor.execute('SELECT id, status FROM directories WHERE name = ?', (name,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing directory
                    dir_id, current_status = existing
                    cursor.execute('''
                        UPDATE directories 
                        SET full_path = ?, image_count = ?, file_size_mb = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (full_path, image_count, file_size_mb, dir_id))
                    
                    self.add_log_entry(dir_id, "directory_updated", 
                                     f"Updated: {image_count} images, {file_size_mb:.1f} MB")
                else:
                    # Insert new directory
                    cursor.execute('''
                        INSERT INTO directories (name, full_path, image_count, file_size_mb)
                        VALUES (?, ?, ?, ?)
                    ''', (name, full_path, image_count, file_size_mb))
                    
                    dir_id = cursor.lastrowid
                    self.add_log_entry(dir_id, "directory_added", 
                                     f"Added: {image_count} images, {file_size_mb:.1f} MB")
                
                conn.commit()
                return dir_id
                
        except Exception as e:
            self.logger.error(f"Failed to add directory {name}: {e}")
            raise
    
    def update_directory_status(self, name: str, status: str, 
                              error_message: str = None, 
                              processing_time: int = 0,
                              has_exposure_correction: bool = False):
        """
        Update directory processing status
        
        Args:
            name: Directory name
            status: New status (pending, processing, completed, failed, queued)
            error_message: Error message if failed
            processing_time: Processing time in seconds
            has_exposure_correction: Whether exposure correction was applied
        """
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                
                processed_at = datetime.now().isoformat() if status == 'completed' else None
                
                cursor.execute('''
                    UPDATE directories 
                    SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP,
                        processed_at = ?, processing_time_seconds = ?, has_exposure_correction = ?
                    WHERE name = ?
                ''', (status, error_message, processed_at, processing_time, has_exposure_correction, name))
                
                # Get directory ID for logging
                cursor.execute('SELECT id FROM directories WHERE name = ?', (name,))
                result = cursor.fetchone()
                if result:
                    dir_id = result[0]
                    log_message = f"Status changed to: {status}"
                    if error_message:
                        log_message += f" - Error: {error_message}"
                    if processing_time > 0:
                        log_message += f" - Time: {processing_time}s"
                    
                    self.add_log_entry(dir_id, "status_changed", log_message)
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to update status for {name}: {e}")
            raise
    
    def add_log_entry(self, directory_id: int, action: str, message: str = None):
        """Add a log entry for a directory"""
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO processing_log (directory_id, action, message)
                    VALUES (?, ?, ?)
                ''', (directory_id, action, message))
                conn.commit()
                
        except Exception as e:
            # Don't log database errors to avoid recursion
            pass
    
    def get_directories_by_status(self, status: str) -> List[Dict]:
        """
        Get directories by status
        
        Args:
            status: Status to filter by (pending, processing, completed, failed, queued)
            
        Returns:
            List of directory dictionaries
        """
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, name, full_path, status, image_count, created_at, 
                           updated_at, processed_at, error_message, processing_time_seconds,
                           file_size_mb, has_exposure_correction
                    FROM directories 
                    WHERE status = ?
                    ORDER BY created_at
                ''', (status,))
                
                columns = ['id', 'name', 'full_path', 'status', 'image_count', 'created_at',
                          'updated_at', 'processed_at', 'error_message', 'processing_time_seconds',
                          'file_size_mb', 'has_exposure_correction']
                
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to get directories by status {status}: {e}")
            return []
    
    def get_pending_directories(self) -> List[Dict]:
        """Get all pending directories ready for processing"""
        return self.get_directories_by_status('pending')
    
    def get_completed_directories(self) -> List[Dict]:
        """Get all completed directories"""
        return self.get_directories_by_status('completed')
    
    def get_failed_directories(self) -> List[Dict]:
        """Get all failed directories"""
        return self.get_directories_by_status('failed')
    
    def get_queued_directories(self) -> List[Dict]:
        """Get all queued directories (insufficient images)"""
        return self.get_directories_by_status('queued')
    
    def get_processing_stats(self) -> Dict:
        """Get overall processing statistics"""
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                
                # Get counts by status
                cursor.execute('''
                    SELECT status, COUNT(*) as count
                    FROM directories
                    GROUP BY status
                ''')
                status_counts = dict(cursor.fetchall())
                
                # Get total processing time
                cursor.execute('''
                    SELECT SUM(processing_time_seconds) as total_time,
                           AVG(processing_time_seconds) as avg_time
                    FROM directories
                    WHERE status = 'completed' AND processing_time_seconds > 0
                ''')
                time_stats = cursor.fetchone()
                total_time, avg_time = time_stats if time_stats else (0, 0)
                
                # Get total images processed
                cursor.execute('''
                    SELECT SUM(image_count) as total_images
                    FROM directories
                    WHERE status = 'completed'
                ''')
                total_images = cursor.fetchone()[0] or 0
                
                # Get total file size
                cursor.execute('''
                    SELECT SUM(file_size_mb) as total_size
                    FROM directories
                ''')
                total_size = cursor.fetchone()[0] or 0
                
                return {
                    'status_counts': status_counts,
                    'total_processing_time': total_time or 0,
                    'average_processing_time': avg_time or 0,
                    'total_images_processed': total_images,
                    'total_file_size_mb': total_size,
                    'directories_with_exposure_correction': len([
                        d for d in self.get_completed_directories() 
                        if d.get('has_exposure_correction')
                    ])
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get processing stats: {e}")
            return {}
    
    def reset_processing_status(self, directory_names: List[str] = None):
        """
        Reset directories from processing status to pending
        Useful for resuming interrupted processing
        
        Args:
            directory_names: Specific directories to reset, or None for all 'processing' status
        """
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                
                if directory_names:
                    placeholders = ','.join(['?' for _ in directory_names])
                    cursor.execute(f'''
                        UPDATE directories 
                        SET status = 'pending', updated_at = CURRENT_TIMESTAMP
                        WHERE name IN ({placeholders}) AND status = 'processing'
                    ''', directory_names)
                else:
                    cursor.execute('''
                        UPDATE directories 
                        SET status = 'pending', updated_at = CURRENT_TIMESTAMP
                        WHERE status = 'processing'
                    ''')
                
                rows_affected = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Reset {rows_affected} directories from 'processing' to 'pending'")
                return rows_affected
                
        except Exception as e:
            self.logger.error(f"Failed to reset processing status: {e}")
            return 0
    
    def get_directory_history(self, name: str) -> List[Dict]:
        """Get processing history for a specific directory"""
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                
                # Get directory ID
                cursor.execute('SELECT id FROM directories WHERE name = ?', (name,))
                result = cursor.fetchone()
                if not result:
                    return []
                
                dir_id = result[0]
                
                # Get log entries
                cursor.execute('''
                    SELECT action, message, timestamp
                    FROM processing_log
                    WHERE directory_id = ?
                    ORDER BY timestamp DESC
                ''', (dir_id,))
                
                columns = ['action', 'message', 'timestamp']
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to get directory history for {name}: {e}")
            return []
    
    def cleanup_old_entries(self, days_old: int = 30):
        """Remove entries older than specified days for completed/failed directories"""
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                
                # Remove old completed/failed directories
                cursor.execute('''
                    DELETE FROM directories
                    WHERE status IN ('completed', 'failed') 
                    AND updated_at < datetime('now', '-{} days')
                '''.format(days_old))
                
                rows_affected = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Cleaned up {rows_affected} old directory entries")
                return rows_affected
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old entries: {e}")
            return 0
    
    def export_to_json(self, output_file: str):
        """Export database to JSON for backup"""
        try:
            import json
            
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                
                # Get all directories
                cursor.execute('''
                    SELECT * FROM directories ORDER BY created_at
                ''')
                directories = cursor.fetchall()
                
                # Get column names
                cursor.execute('PRAGMA table_info(directories)')
                dir_columns = [column[1] for column in cursor.fetchall()]
                
                # Get all logs
                cursor.execute('''
                    SELECT * FROM processing_log ORDER BY timestamp
                ''')
                logs = cursor.fetchall()
                
                cursor.execute('PRAGMA table_info(processing_log)')
                log_columns = [column[1] for column in cursor.fetchall()]
                
                export_data = {
                    'directories': [dict(zip(dir_columns, row)) for row in directories],
                    'processing_log': [dict(zip(log_columns, row)) for row in logs],
                    'export_timestamp': datetime.now().isoformat()
                }
                
                with open(output_file, 'w') as f:
                    json.dump(export_data, f, indent=2)
                
                self.logger.info(f"Database exported to {output_file}")
                
        except Exception as e:
            self.logger.error(f"Failed to export database: {e}")
            raise 