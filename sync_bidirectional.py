#!/usr/bin/env python3
"""Dvosmjerni sync izmedju Termux i sdcard"""
import os, shutil, time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

TERMUX_DIR = os.path.expanduser("~/BooklyTTS")
SDCARD_DIR = "/sdcard/termux/BooklyTTS"
EXCLUDE = {'.venv', '.git', '__pycache__'}

class SyncHandler(FileSystemEventHandler):
    def __init__(self, src, dst, name):
        self.src = src
        self.dst = dst
        self.name = name
        self.syncing = False
    
    def sync_file(self, src_path):
        if self.syncing: return
        rel_path = os.path.relpath(src_path, self.src)
        parts = set(rel_path.split(os.sep))
        if EXCLUDE & parts: return
        
        dst_path = os.path.join(self.dst, rel_path)
        try:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)
                print(f"  [{self.name}] {rel_path}")
        except Exception as e:
            if 'Permission denied' not in str(e):
                print(f"  ❌ {rel_path}: {e}")
    
    def on_modified(self, event):
        if not event.is_directory:
            self.syncing = True
            self.sync_file(event.src_path)
            self.syncing = False
    
    def on_created(self, event):
        if not event.is_directory:
            self.syncing = True
            self.sync_file(event.src_path)
            self.syncing = False

def full_sync(src, dst, label):
    count = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
        for file in files:
            src_path = os.path.join(root, file)
            rel_path = os.path.relpath(src_path, src)
            dst_path = os.path.join(dst, rel_path)
            if not os.path.exists(dst_path) or os.path.getmtime(src_path) > os.path.getmtime(dst_path):
                try:
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                    count += 1
                except: pass
    if count: print(f"  [{label}] {count} fajlova")

if __name__ == '__main__':
    print("🔄 BooklyTTS dvosmjerni sync")
    print(f"   📱 {TERMUX_DIR}")
    print(f"   💾 {SDCARD_DIR}")
    full_sync(TERMUX_DIR, SDCARD_DIR, "📱→💾")
    full_sync(SDCARD_DIR, TERMUX_DIR, "💾→📱")
    print("✅ Folderi identicni. Watchdog aktivan...")
    
    observer = Observer()
    observer.schedule(SyncHandler(TERMUX_DIR, SDCARD_DIR, "📱→💾"), TERMUX_DIR, recursive=True)
    observer.schedule(SyncHandler(SDCARD_DIR, TERMUX_DIR, "💾→📱"), SDCARD_DIR, recursive=True)
    observer.start()
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n👋 Zaustavljeno")
    observer.join()
