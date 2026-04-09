#!/usr/bin/env python3
"""
Command-line interface for Photo Organizer
Usage: python cli.py <command> [options]
"""
import argparse
import sys
import os
from pathlib import Path
from typing import Optional
import logging

from core import PhotoOrganizer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CLI:
    """Command-line interface for PhotoOrganizer"""

    def __init__(self):
        self.organizer = PhotoOrganizer()

    def list_drives(self):
        """List connected SD cards and removable drives"""
        drives = self.organizer.list_sd_cards()
        
        if not drives:
            print("No removable drives detected.")
            return
        
        print("\n📦 Connected Removable Drives:")
        print("-" * 50)
        for i, drive in enumerate(drives, 1):
            print(f"  {i}. {drive}")
        print()

    def list_photos(self, directory: str):
        """List photos in a directory"""
        photos = self.organizer.find_photo_files(directory)
        
        if not photos:
            print(f"No photos found in {directory}")
            return
        
        print(f"\n📷 Found {len(photos)} photos:")
        print("-" * 50)
        for photo in photos[:10]:  # Show first 10
            print(f"  • {Path(photo).name}")
        
        if len(photos) > 10:
            print(f"  ... and {len(photos) - 10} more")
        print()

    def organize(self, sd_card_path: str, camera_name: str,
                 backup_nas: bool = False,
                 nas_address: Optional[str] = None,
                 nas_share: str = "backups",
                 nas_username: Optional[str] = None,
                 nas_password: Optional[str] = None):
        """
        Main organization workflow
        
        Args:
            sd_card_path: Path to SD card
            camera_name: Name of the camera
            backup_nas: Whether to backup to NAS
            nas_address: NAS IP address
            nas_share: NAS share name
            nas_username: NAS username
            nas_password: NAS password
        """
        
        # Validate input
        if not Path(sd_card_path).exists():
            logger.error(f"SD card path does not exist: {sd_card_path}")
            return False
        
        if not camera_name.strip():
            logger.error("Camera name is required")
            return False
        
        try:
            print(f"\n🎬 Starting organization workflow for {camera_name}")
            print("=" * 60)
            
            # Step 1: Create camera folder
            print(f"\n1️⃣  Creating camera folder...")
            camera_folder = self.organizer.create_camera_folder(camera_name)
            print(f"   ✓ Created: {camera_folder}")
            
            # Step 2: Copy photos
            print(f"\n2️⃣  Copying photos from SD card...")
            print(f"   Source: {sd_card_path}")
            print(f"   Destination: {camera_folder}")
            
            def progress_callback(current, total):
                percent = (current / total * 100) if total > 0 else 0
                bar_length = 40
                filled = int(bar_length * current / total) if total > 0 else 0
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"\r   Progress: [{bar}] {current}/{total} ({percent:.1f}%)", end='', flush=True)
            
            copied, copy_errors = self.organizer.copy_photos(
                sd_card_path,
                camera_folder,
                progress_callback=progress_callback
            )
            print()  # Newline after progress bar
            print(f"   ✓ Copied {copied} photos")
            
            if copy_errors:
                print(f"   ⚠️  {len(copy_errors)} errors occurred during copy:")
                for error in copy_errors[:5]:  # Show first 5 errors
                    print(f"      • {error}")
                if len(copy_errors) > 5:
                    print(f"      • ... and {len(copy_errors) - 5} more")
            
            # Step 3: Backup to NAS if requested
            if backup_nas:
                if not nas_address:
                    logger.error("NAS address is required for backup")
                    return False
                
                print(f"\n3️⃣  Backing up to NAS...")
                print(f"   NAS Address: {nas_address}")
                print(f"   Share: {nas_share}")
                
                backed_up, backup_errors = self.organizer.backup_to_nas(
                    camera_folder,
                    nas_address,
                    nas_share,
                    nas_username,
                    nas_password,
                    progress_callback=progress_callback
                )
                print()  # Newline after progress bar
                print(f"   ✓ Backed up {backed_up} photos")
                
                if backup_errors:
                    print(f"   ⚠️  {len(backup_errors)} errors occurred during backup:")
                    for error in backup_errors[:5]:
                        print(f"      • {error}")
                    if len(backup_errors) > 5:
                        print(f"      • ... and {len(backup_errors) - 5} more")
            
            # Show statistics
            print(f"\n📊 Organization Complete!")
            print("=" * 60)
            stats = self.organizer.get_stats()
            print(f"   Camera Folders: {stats['total_folders']}")
            print(f"   Total Photos: {stats['total_photos']:,}")
            print(f"   Total Size: {stats['total_size_gb']:.2f} GB")
            print(f"   Pictures Location: {self.organizer.pictures_base}")
            print()
            
            return True
        
        except Exception as e:
            logger.error(f"Organization failed: {e}")
            return False

    def show_stats(self):
        """Display library statistics"""
        stats = self.organizer.get_stats()
        
        print(f"\n📊 Photo Library Statistics")
        print("=" * 60)
        print(f"Camera Folders:  {stats['total_folders']}")
        print(f"Total Photos:    {stats['total_photos']:,}")
        print(f"Total Size:      {stats['total_size_gb']:.2f} GB")
        print(f"Location:        {self.organizer.pictures_base}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Photo Organizer - Manage photos from SD cards',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List connected drives
  python cli.py drives
  
  # List photos on an SD card
  python cli.py list /Volumes/SD_CARD
  
  # Copy and organize photos
  python cli.py organize /Volumes/SD_CARD "Canon EOS R5"
  
  # Copy and backup to NAS
  python cli.py organize /Volumes/SD_CARD "Sony A7IV" \\
    --backup-nas --nas-address 192.168.1.100
  
  # Show statistics
  python cli.py stats
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # drives command
    subparsers.add_parser('drives', help='List connected removable drives')
    
    # list command
    list_parser = subparsers.add_parser('list', help='List photos in a directory')
    list_parser.add_argument('directory', help='Directory to scan for photos')
    
    # organize command
    org_parser = subparsers.add_parser('organize', help='Organize photos from SD card')
    org_parser.add_argument('sd_card', help='Path to SD card')
    org_parser.add_argument('camera_name', help='Name of the camera (e.g., Canon EOS R5)')
    org_parser.add_argument('--backup-nas', action='store_true',
                           help='Backup to Synology NAS')
    org_parser.add_argument('--nas-address', type=str,
                           help='NAS IP address (e.g., 192.168.1.100)')
    org_parser.add_argument('--nas-share', type=str, default='backups',
                           help='NAS share name (default: backups)')
    org_parser.add_argument('--nas-username', type=str,
                           help='NAS username')
    org_parser.add_argument('--nas-password', type=str,
                           help='NAS password')
    
    # stats command
    subparsers.add_parser('stats', help='Show photo library statistics')
    
    # version
    parser.add_argument('--version', action='version', version='Photo Organizer 1.0.0')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    cli = CLI()
    
    try:
        if args.command == 'drives':
            cli.list_drives()
        
        elif args.command == 'list':
            cli.list_photos(args.directory)
        
        elif args.command == 'organize':
            if args.backup_nas and not args.nas_address:
                print("Error: --nas-address is required when using --backup-nas")
                return 1
            
            success = cli.organize(
                args.sd_card,
                args.camera_name,
                backup_nas=args.backup_nas,
                nas_address=args.nas_address,
                nas_share=args.nas_share,
                nas_username=args.nas_username,
                nas_password=args.nas_password
            )
            return 0 if success else 1
        
        elif args.command == 'stats':
            cli.show_stats()
        
        return 0
    
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        return 1
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
