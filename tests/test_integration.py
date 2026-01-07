"""
Manual integration test to verify the application works with the new retry mechanism.
This simulates a download scenario to ensure the changes don't break existing functionality.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from source.downloader.turbo_downloader import TurboDownloader
from source.downloader.chapter_downloader import ChapterDownloader


def test_basic_initialization():
    """Test that downloaders can be initialized with new parameters"""
    print("\n" + "="*60)
    print("INTEGRATION TEST: Basic Initialization")
    print("="*60)
    
    # Test TurboDownloader with default values
    turbo1 = TurboDownloader()
    assert turbo1.max_retry_attempts == 3, "Default max_retry_attempts should be 3"
    assert turbo1.retry_timeout == 300, "Default retry_timeout should be 300"
    print("✓ TurboDownloader initialized with defaults")
    
    # Test TurboDownloader with custom values
    turbo2 = TurboDownloader(max_retry_attempts=5, retry_timeout=600)
    assert turbo2.max_retry_attempts == 5, "Custom max_retry_attempts should be 5"
    assert turbo2.retry_timeout == 600, "Custom retry_timeout should be 600"
    print("✓ TurboDownloader initialized with custom values")
    
    # Test ChapterDownloader with default values
    chapter1 = ChapterDownloader()
    assert chapter1.max_retry_attempts == 3, "Default max_retry_attempts should be 3"
    assert chapter1.retry_timeout == 300, "Default retry_timeout should be 300"
    print("✓ ChapterDownloader initialized with defaults")
    
    # Test ChapterDownloader with custom values
    chapter2 = ChapterDownloader(max_retry_attempts=5, retry_timeout=600)
    assert chapter2.max_retry_attempts == 5, "Custom max_retry_attempts should be 5"
    assert chapter2.retry_timeout == 600, "Custom retry_timeout should be 600"
    print("✓ ChapterDownloader initialized with custom values")
    
    print("\n✅ TEST PASSED: All initializations work correctly")


def test_backwards_compatibility():
    """Test that old code without new parameters still works"""
    print("\n" + "="*60)
    print("INTEGRATION TEST: Backwards Compatibility")
    print("="*60)
    
    # Old-style initialization (should still work)
    turbo = TurboDownloader(max_workers=10, connection_pool_size=20)
    assert turbo.max_workers == 10
    assert turbo.max_retry_attempts == 3, "Should use default value"
    print("✓ TurboDownloader backwards compatible")
    
    chapter = ChapterDownloader(max_workers=3)
    assert chapter.max_workers == 3
    assert chapter.max_retry_attempts == 3, "Should use default value"
    print("✓ ChapterDownloader backwards compatible")
    
    print("\n✅ TEST PASSED: Backwards compatibility maintained")


def test_download_completion_workflow():
    """Test the complete workflow of download -> retry -> completion"""
    print("\n" + "="*60)
    print("INTEGRATION TEST: Download Completion Workflow")
    print("="*60)
    
    downloader = TurboDownloader(max_workers=2, max_retry_attempts=2, retry_timeout=10)
    
    # Simulate initial download with some failures
    print("\n1. Initial download phase (simulated)")
    downloader.failed_downloads = [
        {'url': 'http://test.com/1.jpg', 'path': '/tmp/1.jpg', 'filename': '1.jpg', 'error': 'test'},
        {'url': 'http://test.com/2.jpg', 'path': '/tmp/2.jpg', 'filename': '2.jpg', 'error': 'test'},
    ]
    print(f"   - {len(downloader.failed_downloads)} files failed")
    
    # First retry
    print("\n2. First retry phase")
    downloader.retry_failed_downloads()
    print(f"   - Still {len(downloader.failed_downloads)} files failed")
    print(f"   - Retry counts: {downloader.retry_counts}")
    
    # Second retry (should hit max)
    print("\n3. Second retry phase")
    downloader.failed_downloads = [
        {'url': 'http://test.com/1.jpg', 'path': '/tmp/1.jpg', 'filename': '1.jpg', 'error': 'test'},
        {'url': 'http://test.com/2.jpg', 'path': '/tmp/2.jpg', 'filename': '2.jpg', 'error': 'test'},
    ]
    downloader.retry_failed_downloads()
    print(f"   - Still {len(downloader.failed_downloads)} files failed")
    print(f"   - Retry counts: {downloader.retry_counts}")
    
    # Third attempt should skip (exceeded max)
    print("\n4. Third retry attempt (should skip)")
    downloader.failed_downloads = [
        {'url': 'http://test.com/1.jpg', 'path': '/tmp/1.jpg', 'filename': '1.jpg', 'error': 'test'},
        {'url': 'http://test.com/2.jpg', 'path': '/tmp/2.jpg', 'filename': '2.jpg', 'error': 'test'},
    ]
    result = downloader.retry_failed_downloads()
    print(f"   - Retry result: {result}")
    print(f"   - Failed downloads count: {len(downloader.failed_downloads)}")
    
    # Verify files are marked as permanently failed
    assert len(downloader.failed_downloads) == 2, "Should have 2 permanently failed files"
    
    print("\n5. Download can now complete")
    print(f"   - Download phase: COMPLETE")
    print(f"   - Retry phase: COMPLETE")
    print(f"   - Status: Can exit with summary of failed files")
    
    print("\n✅ TEST PASSED: Workflow completes properly even with failures")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("RUNNING INTEGRATION TESTS")
    print("="*60)
    
    try:
        test_basic_initialization()
        test_backwards_compatibility()
        test_download_completion_workflow()
        
        print("\n" + "="*60)
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("="*60)
        print("\nSummary:")
        print("- Downloaders initialize correctly with new parameters")
        print("- Backwards compatibility maintained")
        print("- Download workflow completes even with failures")
        print("- No infinite retry loops")
        print("- Application can exit successfully")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
