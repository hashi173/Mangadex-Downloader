import os
import requests
import time
import re
import threading
import zipfile
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io
from queue import Queue
import urllib3

# Disable SSL warnings for speed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TurboDownloader:
    def __init__(self, max_workers=10, connection_pool_size=20, max_retry_attempts=3, retry_timeout=300):
        """
        Ultra-fast downloader
        max_workers: Number of concurrent downloads (default 10, can go up to 20)
        connection_pool_size: HTTP connection pool size
        max_retry_attempts: Maximum number of retry attempts per file (default: 3)
        retry_timeout: Maximum time in seconds for entire retry phase (default: 300 = 5 minutes)
        """
        self.max_workers = max_workers
        self.max_retry_attempts = max_retry_attempts
        self.retry_timeout = retry_timeout

        # Create optimized session with connection pooling
        self.session = requests.Session()

        # Optimize adapter for speed
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=connection_pool_size,
            pool_maxsize=connection_pool_size,
            max_retries=3,
            pool_block=False
        )

        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })

        # Control
        self.is_paused = False
        self.is_stopped = False

        # Progress tracking
        self.total_downloaded = 0
        self.start_time = None
        self.download_speeds = []

        # Error tracking
        self.failed_downloads = []
        self.retry_counts = {}  # Track retry count per file

        # Thread-safe locks
        self.progress_lock = threading.Lock()

        # Download queue for batching
        self.download_queue = Queue()

        print(f"🚀 TurboDownloader initialized:  {max_workers} threads")

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        self.is_stopped = True
        self.is_paused = False

    def reset(self):
        self.is_paused = False
        self.is_stopped = False
        self.failed_downloads = []
        self.retry_counts = {}
        self.total_downloaded = 0
        self.start_time = None
        self.download_speeds = []

    def check_pause(self):
        while self.is_paused and not self.is_stopped:
            time.sleep(0.1)

    def sanitize_filename(self, filename):
        return re.sub(r'[<>:"/\\|?*]', '', filename)

    def download_image_fast(self, url, output_path, retry=2):
        """
        Ultra-fast image download with minimal overhead
        Reduced retries for speed (2 instead of 3)
        """
        for attempt in range(retry):
            if self.is_stopped:
                return False

            self.check_pause()

            try:
                start_time = time.time()

                # Fast download with streaming disabled for small files
                response = self.session.get(
                    url,
                    timeout=15,  # Reduced from 30
                    stream=False,  # Faster for small files
                    verify=False  # Skip SSL verification for speed (use with caution)
                )
                response.raise_for_status()

                # Create directory if needed
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Write file directly
                with open(output_path, 'wb') as f:
                    f.write(response.content)

                # Track speed
                download_time = time.time() - start_time
                file_size = len(response.content)
                speed = file_size / download_time if download_time > 0 else 0

                with self.progress_lock:
                    self.total_downloaded += file_size
                    self.download_speeds.append(speed)
                    # Keep only last 50 speeds for average
                    if len(self.download_speeds) > 50:
                        self.download_speeds.pop(0)

                return True

            except Exception as e:
                if attempt < retry - 1:
                    time.sleep(0.5)  # Reduced wait time
                else:
                    self.failed_downloads.append({
                        'url': url,
                        'path': output_path,
                        'filename': os.path.basename(output_path),
                        'error': str(e)
                    })
                    return False

        return False

    def download_batch_fast(self, download_tasks, progress_callback=None):
        """
        Download multiple files in parallel with ThreadPoolExecutor
        download_tasks: List of (url, filepath, page_num, total_pages)
        """
        successful = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for task in download_tasks:
                url, filepath, page_num, total_pages = task

                # Skip if exists
                if os.path.exists(filepath):
                    successful += 1
                    if progress_callback:
                        progress_callback(page_num, total_pages, os.path.basename(filepath), "skipped")
                    continue

                if progress_callback:
                    progress_callback(page_num, total_pages, os.path.basename(filepath), "downloading")

                future = executor.submit(self.download_image_fast, url, filepath)
                future_to_task[future] = task

            # Process completed downloads
            for future in as_completed(future_to_task):
                if self.is_stopped:
                    executor.shutdown(wait=False, cancel_futures=True)
                    return successful, failed

                task = future_to_task[future]
                url, filepath, page_num, total_pages = task

                try:
                    result = future.result()
                    if result:
                        successful += 1
                        if progress_callback:
                            progress_callback(page_num, total_pages, os.path.basename(filepath), "completed")
                    else:
                        failed += 1
                        if progress_callback:
                            progress_callback(page_num, total_pages, os.path.basename(filepath), "failed")
                except Exception as e:
                    failed += 1
                    if progress_callback:
                        progress_callback(page_num, total_pages, os.path.basename(filepath), "failed")

        return successful, failed

    def download_cover_fast(self, cover_url, chapter_path, progress_callback=None):
        """Fast cover download with correct extension"""
        try:
            if not cover_url:
                return False

            # FIXED: Get actual extension from URL
            # Extract extension from cover_url
            url_path = cover_url.split('? ')[0]  # Remove query params
            ext = url_path.split('.')[-1].lower()

            # Validate extension
            if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                # If extension invalid, try to detect from URL
                if '. png' in cover_url.lower():
                    ext = 'png'
                elif '.jpg' in cover_url.lower() or '.jpeg' in cover_url.lower():
                    ext = 'jpg'
                elif '. webp' in cover_url.lower():
                    ext = 'webp'
                else:
                    ext = 'jpg'  # Default fallback

            # FIXED: Cover always 00.{actual_ext}
            cover_filename = f"00.{ext}"
            cover_path = os.path.join(chapter_path, cover_filename)

            if os.path.exists(cover_path):
                if progress_callback:
                    progress_callback(0, 1, cover_filename, "skipped")
                return True

            print(f"📥 Downloading cover as {cover_filename}...")

            if progress_callback:
                progress_callback(0, 1, f"{cover_filename} (cover)", "downloading")

            os.makedirs(chapter_path, exist_ok=True)

            success = self.download_image_fast(cover_url, cover_path)

            if success:
                print(f"✓ Cover saved:  {cover_filename}")
                if progress_callback:
                    progress_callback(0, 1, f"{cover_filename} (cover)", "completed")
                return True
            else:
                return False

        except Exception as e:
            print(f"✗ Cover error: {e}")
            return False

    def download_chapter_turbo(self, chapter_info, page_urls, output_path, progress_callback=None,
                               cover_url=None, is_first_chapter=False):
        """
        Turbo-charged chapter download
        Downloads all pages in parallel
        """
        try:
            os.makedirs(output_path, exist_ok=True)

            # Download cover first if needed
            if is_first_chapter and cover_url:
                self.download_cover_fast(cover_url, output_path, progress_callback)

            total_pages = len(page_urls)

            print(f"⚡ Turbo download:  {total_pages} pages with {self.max_workers} threads")

            # Prepare all download tasks
            download_tasks = []
            for i, page_url in enumerate(page_urls, 1):
                # FIXED: Get actual extension from URL
                url_path = page_url.split('?')[0]  # Remove query params
                ext = url_path.split('.')[-1].lower()

                # Validate extension
                if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                    ext = 'jpg'  # Default

                # FIXED: Always use 2 digits minimum (01, 02, ...)
                # Use 3 digits if more than 99 pages (001, 002, ...)
                if total_pages < 100:
                    page_filename = f"{i:02d}.{ext}"  # 01, 02, .. ., 99
                elif total_pages < 1000:
                    page_filename = f"{i:03d}.{ext}"  # 001, 002, ..., 999
                else:
                    page_filename = f"{i:04d}.{ext}"  # 0001, 0002, ..., 9999

                page_path = os.path.join(output_path, page_filename)
                download_tasks.append((page_url, page_path, i, total_pages))

            # Batch download with parallel execution
            successful, failed = self.download_batch_fast(download_tasks, progress_callback)

            # Summary
            print(f"📊 Chapter Summary:  ✓ {successful}/{total_pages}")
            if failed > 0:
                print(f"   ✗ Failed: {failed}/{total_pages}")

            return not self.is_stopped

        except Exception as e:
            print(f"✗ Chapter error: {e}")
            return False

    def get_average_speed(self):
        """Get average download speed in MB/s"""
        if not self.download_speeds:
            return 0

        avg_speed = sum(self.download_speeds) / len(self.download_speeds)
        return avg_speed / (1024 * 1024)  # Convert to MB/s

    def retry_failed_downloads(self, progress_callback=None):
        """Retry failed downloads with max attempts and timeout"""
        if not self.failed_downloads:
            return True

        retry_start_time = time.time()
        
        print(f"\n🔄 Retrying {len(self.failed_downloads)} failed downloads (max {self.max_retry_attempts} attempts)...")

        # Filter files that haven't exceeded max retry attempts
        retry_tasks = []
        permanently_failed = []
        
        for item in self.failed_downloads:
            file_key = item['path']
            current_retry_count = self.retry_counts.get(file_key, 0)
            
            if current_retry_count < self.max_retry_attempts:
                # Still within retry limit
                self.retry_counts[file_key] = current_retry_count + 1
                retry_tasks.append(item)
            else:
                # Exceeded max retries
                permanently_failed.append(item)
        
        if permanently_failed:
            print(f"⚠️  {len(permanently_failed)} files exceeded max retry attempts and will be skipped")
        
        if not retry_tasks:
            print(f"✅ No more retries needed (all files either succeeded or exceeded max attempts)")
            self.failed_downloads = permanently_failed
            return True
        
        # Prepare retry tasks for download
        download_tasks = [
            (item['url'], item['path'], idx, len(retry_tasks))
            for idx, item in enumerate(retry_tasks, 1)
        ]
        
        # Clear failed list before retry
        self.failed_downloads = []
        
        print(f"🔄 Attempting retry for {len(retry_tasks)} files...")
        
        # Retry with progress and timeout check
        for idx, (url, path, task_idx, total) in enumerate(download_tasks):
            # Check timeout
            elapsed_time = time.time() - retry_start_time
            if elapsed_time > self.retry_timeout:
                print(f"\n⏱️  Retry timeout ({self.retry_timeout}s) reached, stopping retries")
                # Re-add remaining files to failed list
                for remaining_idx in range(idx, len(download_tasks)):
                    remaining_item = retry_tasks[remaining_idx]
                    self.failed_downloads.append(remaining_item)
                break
            
            if self.is_stopped:
                break
            
            file_key = path
            retry_attempt = self.retry_counts.get(file_key, 1)
            
            if progress_callback:
                progress_callback(task_idx, total, os.path.basename(path), 
                                f"retry_attempt_{retry_attempt}")
            
            print(f"🔄 [{task_idx}/{total}] Retry attempt {retry_attempt}/{self.max_retry_attempts}: {os.path.basename(path)}")
            
            # Attempt download
            success = self.download_image_fast(url, path)
            
            if success:
                print(f"   ✓ SUCCESS on retry attempt {retry_attempt}")
            else:
                print(f"   ✗ Failed on retry attempt {retry_attempt}")

        # Add permanently failed files back to the list
        self.failed_downloads.extend(permanently_failed)

        if self.failed_downloads:
            print(f"\n⚠️  {len(self.failed_downloads)} files still failed after retries")
            print(f"📄 Failed files:")
            for item in self.failed_downloads[:5]:  # Show first 5
                print(f"   - {item['filename']}")
            if len(self.failed_downloads) > 5:
                print(f"   ... and {len(self.failed_downloads) - 5} more")
            return False
        else:
            print(f"✅ All retries successful!")
            return True

    def create_cbz(self, chapter_path, output_cbz_path):
        """Create CBZ archive"""
        try:
            print(f"📦 Creating CBZ:  {os.path.basename(output_cbz_path)}")

            with zipfile.ZipFile(output_cbz_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as cbz:
                image_files = sorted([f for f in os.listdir(chapter_path)
                                      if f.lower().endswith(('.jpg', '. jpeg', '.png', '.webp'))])

                for img_file in image_files:
                    img_path = os.path.join(chapter_path, img_file)
                    cbz.write(img_path, img_file)

            print(f"✓ CBZ created: {os.path.basename(output_cbz_path)}")
            return True
        except Exception as e:
            print(f"✗ CBZ error: {e}")
            return False

    def create_pdf(self, chapter_path, output_pdf_path):
        """Create PDF"""
        try:
            print(f"📄 Creating PDF: {os.path.basename(output_pdf_path)}")

            image_files = sorted([f for f in os.listdir(chapter_path)
                                  if f.lower().endswith(('.jpg', '.jpeg', '.png', '. webp'))])

            if not image_files:
                return False

            c = canvas.Canvas(output_pdf_path, pagesize=A4)

            for img_file in image_files:
                img_path = os.path.join(chapter_path, img_file)

                img = Image.open(img_path)

                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        background.paste(img, mask=img.split()[-1])
                        img = background
                    else:
                        img = img.convert('RGB')
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                temp_jpg = img_path.rsplit('.', 1)[0] + '_temp.jpg'
                img.save(temp_jpg, 'JPEG', quality=90)  # Slightly lower quality for speed

                img_width, img_height = img.size
                a4_width, a4_height = A4

                ratio = min(a4_width / img_width, a4_height / img_height)
                new_width = img_width * ratio
                new_height = img_height * ratio

                x = (a4_width - new_width) / 2
                y = (a4_height - new_height) / 2

                c.drawImage(temp_jpg, x, y, width=new_width, height=new_height,
                            preserveAspectRatio=True)
                c.showPage()

                try:
                    os.remove(temp_jpg)
                except:
                    pass

            c.save()
            print(f"✓ PDF created: {os.path.basename(output_pdf_path)}")
            return True
        except Exception as e:
            print(f"✗ PDF error: {e}")
            return False

    def merge_cbz_files(self, cbz_files, output_path, manga_title):
        """Merge CBZ files"""
        try:
            merged_cbz_path = os.path.join(output_path, f"{self.sanitize_filename(manga_title)}_Complete.cbz")

            print(f"\n📦 Merging {len(cbz_files)} CBZ files...")

            with zipfile.ZipFile(merged_cbz_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as merged_cbz:
                for cbz_file in cbz_files:
                    with zipfile.ZipFile(cbz_file, 'r') as source_cbz:
                        for file_info in source_cbz.filelist:
                            chapter_name = os.path.basename(os.path.dirname(cbz_file))
                            new_name = f"{chapter_name}/{file_info.filename}"

                            file_data = source_cbz.read(file_info.filename)
                            merged_cbz.writestr(new_name, file_data)

            print(f"✓ Merged CBZ:  {os.path.basename(merged_cbz_path)}")
            return merged_cbz_path
        except Exception as e:
            print(f"✗ Merge CBZ error: {e}")
            return None

    def merge_pdf_files(self, pdf_files, output_path, manga_title):
        """Merge PDF files"""
        try:
            from PyPDF2 import PdfMerger

            merged_pdf_path = os.path.join(output_path, f"{self.sanitize_filename(manga_title)}_Complete.pdf")

            print(f"\n📄 Merging {len(pdf_files)} PDF files...")

            merger = PdfMerger()

            for pdf_file in pdf_files:
                merger.append(pdf_file)

            merger.write(merged_pdf_path)
            merger.close()

            print(f"✓ Merged PDF: {os.path.basename(merged_pdf_path)}")
            return merged_pdf_path
        except ImportError:
            print("⚠ Installing PyPDF2...")
            import subprocess
            subprocess.check_call(['pip', 'install', 'PyPDF2'])
            return self.merge_pdf_files(pdf_files, output_path, manga_title)
        except Exception as e:
            print(f"✗ Merge PDF error: {e}")
            return None

    def download_manga(self, manga_title, chapters_data, output_dir, progress_callback=None,
                       create_cbz_per_chapter=False, create_pdf_per_chapter=False,
                       create_cbz_all=False, create_pdf_all=False, cover_url=None):
        """
        Ultra-fast manga download with parallel execution
        """
        self.start_time = time.time()

        print(f"\n{'=' * 60}")
        print(f"🚀 TURBO Download:  {manga_title}")
        print(f"   Chapters: {len(chapters_data)}")
        print(f"   Threads: {self.max_workers} (TURBO MODE)")
        print(f"   CBZ per:  {create_cbz_per_chapter} | PDF per: {create_pdf_per_chapter}")
        print(f"   CBZ all: {create_cbz_all} | PDF all: {create_pdf_all}")
        print(f"{'=' * 60}\n")

        manga_title = self.sanitize_filename(manga_title)
        manga_path = os.path.join(output_dir, manga_title)

        total_chapters = len(chapters_data)
        cbz_files = []
        pdf_files = []

        need_cbz_per = create_cbz_per_chapter or create_cbz_all
        need_pdf_per = create_pdf_per_chapter or create_pdf_all

        # Download chapters
        for chapter_idx, chapter_data in enumerate(chapters_data, 1):
            if self.is_stopped:
                return False

            self.check_pause()

            chapter_info = chapter_data['chapter_info']
            page_urls = chapter_data['page_urls']

            chapter_num = chapter_info.get('attributes', {}).get('chapter', 'Unknown')
            chapter_title = chapter_info.get('attributes', {}).get('title', '')

            if chapter_title:
                folder_name = f"Chapter {chapter_num} - {self.sanitize_filename(chapter_title)}"
            else:
                folder_name = f"Chapter {chapter_num}"

            chapter_path = os.path.join(manga_path, folder_name)

            print(f"\n📖 {chapter_idx}/{total_chapters}: {folder_name}")

            if progress_callback:
                progress_callback(chapter_idx, total_chapters, folder_name, "chapter_start")

            def page_progress(page_num, total_pages, page_name, status, downloaded=0, total=0):
                if progress_callback:
                    progress_callback(chapter_idx, total_chapters, folder_name, "page_progress",
                                      page_num, total_pages, page_name, status, downloaded, total)

            is_first = (chapter_idx == 1)
            success = self.download_chapter_turbo(chapter_info, page_urls, chapter_path, page_progress,
                                                  cover_url=cover_url, is_first_chapter=is_first)

            if self.is_stopped:
                return False

            # Show speed
            avg_speed = self.get_average_speed()
            print(f"   ⚡ Speed: {avg_speed:.2f} MB/s")

            # Create CBZ
            if success and need_cbz_per:
                if progress_callback:
                    progress_callback(chapter_idx, total_chapters, folder_name, "creating_cbz")

                cbz_path = f"{chapter_path}.cbz"
                if self.create_cbz(chapter_path, cbz_path):
                    cbz_files.append(cbz_path)

            # Create PDF
            if success and need_pdf_per:
                if progress_callback:
                    progress_callback(chapter_idx, total_chapters, folder_name, "creating_pdf")

                pdf_path = f"{chapter_path}.pdf"
                if self.create_pdf(chapter_path, pdf_path):
                    pdf_files.append(pdf_path)

            if progress_callback:
                progress_callback(chapter_idx, total_chapters, folder_name,
                                  "chapter_complete" if success else "chapter_failed")

        # Retry failed
        if self.failed_downloads and not self.is_stopped:
            print(f"\n🔄 RETRY PHASE - {len(self.failed_downloads)} failed")

            if progress_callback:
                progress_callback(total_chapters, total_chapters, "Retrying", "retrying")

            self.retry_failed_downloads(progress_callback)

        # Merge CBZ
        if create_cbz_all and cbz_files:
            if progress_callback:
                progress_callback(total_chapters, total_chapters, "Merging CBZ", "merging_cbz")

            self.merge_cbz_files(cbz_files, output_dir, manga_title)

        # Merge PDF
        if create_pdf_all and pdf_files:
            if progress_callback:
                progress_callback(total_chapters, total_chapters, "Merging PDF", "merging_pdf")

            self.merge_pdf_files(pdf_files, output_dir, manga_title)

        # Final summary
        total_time = time.time() - self.start_time
        total_mb = self.total_downloaded / (1024 * 1024)
        avg_speed = self.get_average_speed()

        print(f"\n{'=' * 60}")
        print(f"✅ TURBO Download Complete!")
        print(f"   📊 Total:  {total_mb:.2f} MB")
        print(f"   ⚡ Avg Speed: {avg_speed:. 2f} MB/s")
        print(f"   ⏱️ Time: {int(total_time)}s")
        if self.failed_downloads:
            print(f"   ⚠️ Failed: {len(self.failed_downloads)} files")
        else:
            print(f"   🎉 All files downloaded!")
        print(f"{'=' * 60}\n")

        return not self.is_stopped