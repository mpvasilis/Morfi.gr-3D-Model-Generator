#!/usr/bin/env python3
"""
Simple test script for the 3D Model Generator UI
"""

import sys
import os

def test_imports():
    """Test that all required modules can be imported"""
    try:
        import customtkinter as ctk
        print("✓ CustomTkinter imported successfully")
        
        from PIL import Image, ImageTk
        print("✓ Pillow imported successfully")
        
        from database import ProcessingDatabase
        print("✓ Database module imported successfully")
        
        from main import PhotogrammetryAutomator
        print("✓ Main automation module imported successfully")
        
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_database():
    """Test database functionality"""
    try:
        from database import ProcessingDatabase
        
        # Create test database
        db = ProcessingDatabase("test_db.db")
        
        # Add test directory
        db.add_directory("test_dir", "/test/path", 250)
        
        # Update status
        db.update_directory_status("test_dir", "completed")
        
        # Get stats
        stats = db.get_processing_stats()
        print(f"✓ Database test successful: {stats}")
        
        # Explicitly close any database connections
        del db
        
        # Cleanup with retry mechanism
        import time
        import gc
        gc.collect()  # Force garbage collection
        
        for attempt in range(3):
            try:
                if os.path.exists("test_db.db"):
                    os.remove("test_db.db")
                break
            except (PermissionError, OSError) as e:
                if attempt < 2:
                    time.sleep(0.5)  # Wait a bit and retry
                    continue
                else:
                    print(f"⚠ Warning: Could not delete test database file: {e}")
        
        return True
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        # Cleanup with error handling
        try:
            del db
        except:
            pass
        
        import time
        import gc
        gc.collect()
        
        for attempt in range(3):
            try:
                if os.path.exists("test_db.db"):
                    os.remove("test_db.db")
                break
            except:
                if attempt < 2:
                    time.sleep(0.5)
                    continue
        return False

def main():
    """Run tests"""
    print("Testing 3D Model Generator UI Components...")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests failed. Please install required packages:")
        print("pip install -r requirements.txt")
        sys.exit(1)
    
    # Test database
    if not test_database():
        print("\n❌ Database tests failed.")
        sys.exit(1)
    
    print("\n✅ All tests passed! UI should work correctly.")
    print("\nTo run the UI:")
    print("python ui.py")

if __name__ == "__main__":
    main() 