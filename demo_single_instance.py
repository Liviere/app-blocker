"""
Demonstration script showing the single instance mechanism in action
This script simulates trying to launch the application multiple times
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from single_instance import ensure_single_instance


def demo_gui_instance():
    """Demonstrate GUI single instance behavior"""
    print("\n=== GUI Instance Demo ===")
    print("Attempting to launch GUI instance 1...")
    
    instance1 = ensure_single_instance("AppBlocker_GUI")
    if instance1:
        print("✓ GUI instance 1 launched successfully!")
        
        print("\nAttempting to launch GUI instance 2...")
        instance2 = ensure_single_instance("AppBlocker_GUI")
        if instance2:
            print("✗ ERROR: GUI instance 2 should have been blocked!")
            instance2.release()
        else:
            print("✓ GUI instance 2 was correctly blocked!")
            print("  (User would see a warning dialog)")
        
        print("\nReleasing GUI instance 1...")
        instance1.release()
        print("✓ GUI instance 1 released")
        
        print("\nAttempting to launch GUI instance 3 after release...")
        instance3 = ensure_single_instance("AppBlocker_GUI")
        if instance3:
            print("✓ GUI instance 3 launched successfully after previous release!")
            instance3.release()
        else:
            print("✗ ERROR: Should be able to launch after release!")
    else:
        print("✗ ERROR: GUI instance 1 should have launched!")


def demo_monitor_instance():
    """Demonstrate Monitor single instance behavior"""
    print("\n=== Monitor Instance Demo ===")
    print("Attempting to launch Monitor instance 1...")
    
    instance1 = ensure_single_instance("AppBlocker_Monitor")
    if instance1:
        print("✓ Monitor instance 1 launched successfully!")
        
        print("\nAttempting to launch Monitor instance 2...")
        instance2 = ensure_single_instance("AppBlocker_Monitor")
        if instance2:
            print("✗ ERROR: Monitor instance 2 should have been blocked!")
            instance2.release()
        else:
            print("✓ Monitor instance 2 was correctly blocked!")
            print("  (User would see: 'App Blocker monitoring is already running')")
        
        print("\nReleasing Monitor instance 1...")
        instance1.release()
        print("✓ Monitor instance 1 released")
    else:
        print("✗ ERROR: Monitor instance 1 should have launched!")


def demo_concurrent_gui_and_monitor():
    """Demonstrate that GUI and Monitor can run concurrently"""
    print("\n=== Concurrent GUI and Monitor Demo ===")
    print("Launching both GUI and Monitor instances simultaneously...")
    
    gui_instance = ensure_single_instance("AppBlocker_GUI")
    monitor_instance = ensure_single_instance("AppBlocker_Monitor")
    
    if gui_instance and monitor_instance:
        print("✓ Both GUI and Monitor instances running concurrently!")
        print("  This is expected behavior - they use different locks")
        
        gui_instance.release()
        monitor_instance.release()
        print("✓ Both instances released")
    else:
        print("✗ ERROR: Both should be able to run concurrently!")


if __name__ == "__main__":
    print("=" * 70)
    print("Single Instance Mechanism Demonstration")
    print("=" * 70)
    
    demo_gui_instance()
    demo_monitor_instance()
    demo_concurrent_gui_and_monitor()
    
    print("\n" + "=" * 70)
    print("Demonstration Complete!")
    print("=" * 70)
    print("\nKey Points:")
    print("- Only one GUI instance can run at a time")
    print("- Only one Monitor instance can run at a time")
    print("- GUI and Monitor can run concurrently (different locks)")
    print("- User-friendly error messages when blocked")
    print("=" * 70)
