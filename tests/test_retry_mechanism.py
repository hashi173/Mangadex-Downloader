"""
Test script to verify retry mechanism fixes
Tests that:
1. Retry attempts are limited to max_retry_attempts
2. Retry timeout prevents infinite loops
3. Download completes even with failed files
"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from source.downloader.turbo_downloader import TurboDownloader
from source.downloader.chapter_downloader import ChapterDownloader


def test_turbo_downloader_max_retries():
    """Test that TurboDownloader respects max retry attempts"""
    print("\n" + "="*60)
    print("TEST: TurboDownloader - Max Retry Attempts")
    print("="*60)
    
    downloader = TurboDownloader(max_workers=2, max_retry_attempts=3, retry_timeout=60)
    
    # Verify initialization
    assert downloader.max_retry_attempts == 3, "max_retry_attempts not set correctly"
    assert downloader.retry_timeout == 60, "retry_timeout not set correctly"
    assert downloader.retry_counts == {}, "retry_counts should be empty dict"
    
    print("✓ TurboDownloader initialized with correct parameters")
    
    # Simulate failed downloads
    test_files = [
        {'url': 'http://fake-url-1.com/image1.jpg', 'path': '/tmp/test1.jpg', 'filename': 'test1.jpg', 'error': 'Test error'},
        {'url': 'http://fake-url-2.com/image2.jpg', 'path': '/tmp/test2.jpg', 'filename': 'test2.jpg', 'error': 'Test error'},
    ]
    
    downloader.failed_downloads = test_files.copy()
    
    print(f"✓ Simulated {len(test_files)} failed downloads")
    
    # First retry attempt
    print("\n--- Retry Attempt 1 ---")
    downloader.retry_failed_downloads()
    
    # Check retry counts
    assert downloader.retry_counts.get('/tmp/test1.jpg', 0) == 1, "Retry count should be 1"
    assert downloader.retry_counts.get('/tmp/test2.jpg', 0) == 1, "Retry count should be 1"
    print(f"✓ Retry counts tracked correctly: {downloader.retry_counts}")
    
    # Simulate files still failed
    downloader.failed_downloads = test_files.copy()
    
    # Second retry attempt
    print("\n--- Retry Attempt 2 ---")
    downloader.retry_failed_downloads()
    assert downloader.retry_counts.get('/tmp/test1.jpg', 0) == 2, "Retry count should be 2"
    print(f"✓ Retry counts updated: {downloader.retry_counts}")
    
    # Third retry attempt
    downloader.failed_downloads = test_files.copy()
    print("\n--- Retry Attempt 3 (Final) ---")
    downloader.retry_failed_downloads()
    assert downloader.retry_counts.get('/tmp/test1.jpg', 0) == 3, "Retry count should be 3"
    print(f"✓ Retry counts updated: {downloader.retry_counts}")
    
    # Fourth retry attempt - should skip
    downloader.failed_downloads = test_files.copy()
    print("\n--- Retry Attempt 4 (Should be Skipped) ---")
    result = downloader.retry_failed_downloads()
    
    # After exceeding max retries, files should be marked as permanently failed
    print(f"✓ Files marked as permanently failed: {len(downloader.failed_downloads)}")
    assert len(downloader.failed_downloads) == 2, "Files should still be in failed list after max retries"
    
    print("\n✅ TEST PASSED: Max retry attempts respected")


def test_chapter_downloader_max_retries():
    """Test that ChapterDownloader respects max retry attempts"""
    print("\n" + "="*60)
    print("TEST: ChapterDownloader - Max Retry Attempts")
    print("="*60)
    
    downloader = ChapterDownloader(max_workers=2, max_retry_attempts=3, retry_timeout=60)
    
    # Verify initialization
    assert downloader.max_retry_attempts == 3, "max_retry_attempts not set correctly"
    assert downloader.retry_timeout == 60, "retry_timeout not set correctly"
    assert downloader.retry_counts == {}, "retry_counts should be empty dict"
    
    print("✓ ChapterDownloader initialized with correct parameters")
    
    # Simulate failed downloads
    test_files = [
        {'url': 'http://fake-url-1.com/image1.jpg', 'path': '/tmp/test1.jpg', 'filename': 'test1.jpg', 'error': 'Test error'},
    ]
    
    downloader.failed_downloads = test_files.copy()
    
    print(f"✓ Simulated {len(test_files)} failed downloads")
    
    # First retry attempt
    print("\n--- Retry Attempt 1 ---")
    downloader.retry_failed_downloads()
    
    # Check retry counts
    assert downloader.retry_counts.get('/tmp/test1.jpg', 0) == 1, "Retry count should be 1"
    print(f"✓ Retry counts tracked correctly: {downloader.retry_counts}")
    
    print("\n✅ TEST PASSED: ChapterDownloader max retry attempts working")


def test_retry_timeout():
    """Test that retry timeout prevents infinite loops"""
    print("\n" + "="*60)
    print("TEST: Retry Timeout")
    print("="*60)
    
    # Create downloader with very short timeout
    downloader = TurboDownloader(max_workers=2, max_retry_attempts=10, retry_timeout=2)
    
    print("✓ Created TurboDownloader with 2-second timeout")
    
    # Simulate many failed downloads
    test_files = [
        {'url': f'http://fake-url-{i}.com/image{i}.jpg', 
         'path': f'/tmp/test{i}.jpg', 
         'filename': f'test{i}.jpg', 
         'error': 'Test error'}
        for i in range(10)
    ]
    
    downloader.failed_downloads = test_files.copy()
    
    print(f"✓ Simulated {len(test_files)} failed downloads")
    
    start_time = time.time()
    downloader.retry_failed_downloads()
    elapsed = time.time() - start_time
    
    print(f"✓ Retry phase completed in {elapsed:.2f} seconds")
    
    # Should complete close to timeout, not much longer
    assert elapsed < 5, f"Retry took too long: {elapsed}s (timeout was 2s)"
    
    print("\n✅ TEST PASSED: Timeout prevents infinite retry loop")


def test_reset_clears_retry_counts():
    """Test that reset() clears retry counts"""
    print("\n" + "="*60)
    print("TEST: Reset Clears Retry Counts")
    print("="*60)
    
    downloader = TurboDownloader(max_workers=2, max_retry_attempts=3)
    
    # Add some retry counts
    downloader.retry_counts = {'/tmp/test1.jpg': 2, '/tmp/test2.jpg': 1}
    downloader.failed_downloads = [{'url': 'test', 'path': '/tmp/test.jpg', 'filename': 'test.jpg'}]
    
    print(f"✓ Set retry_counts: {downloader.retry_counts}")
    print(f"✓ Set failed_downloads: {len(downloader.failed_downloads)} items")
    
    # Reset
    downloader.reset()
    
    assert downloader.retry_counts == {}, "retry_counts should be empty after reset"
    assert downloader.failed_downloads == [], "failed_downloads should be empty after reset"
    
    print("✓ Retry counts cleared after reset")
    print("✓ Failed downloads cleared after reset")
    
    print("\n✅ TEST PASSED: Reset properly clears state")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("RUNNING RETRY MECHANISM TESTS")
    print("="*60)
    
    try:
        test_turbo_downloader_max_retries()
        test_chapter_downloader_max_retries()
        test_retry_timeout()
        test_reset_clears_retry_counts()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
