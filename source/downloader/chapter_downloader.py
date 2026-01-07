import os
import requests
import time
import re
import threading
import zipfile
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io


class ChapterDownloader:
    def __init__(self, max_workers=3, max_retry_attempts=3, retry_timeout=300):
        """
        Chapter downloader with retry limits
        max_workers: Number of concurrent downloads (default: 3)
        max_retry_attempts: Maximum number of retry attempts per file (default: 3)
        retry_timeout: Maximum time in seconds for entire retry phase (default: 300 = 5 minutes)
        """
        self.max_workers = max_workers
        self.max_retry_attempts = max_retry_attempts
        self.retry_timeout = retry_timeout
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        self.is_paused = False
        self.is_stopped = False

        # Error tracking
        self.failed_downloads = []
        self.retry_counts = {}  # Track retry count per file

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

    def check_pause(self):
        while self.is_paused and not self.is_stopped:
            time.sleep(0.1)

    def sanitize_filename(self, filename):
        return re.sub(r'[<>:"/\\|?*]', '', filename)

    def download_image(self, url, output_path, retry=3, progress_callback=None):
        """Download with error logging"""
        for attempt in range(retry):
            if self.is_stopped:
                return False

            self.check_pause()

            try:
                response = self.session.get(url, timeout=30, stream=True)
                response.raise_for_status()

                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.is_stopped:
                            return False

                        self.check_pause()

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            if progress_callback and total_size > 0:
                                progress_callback(downloaded, total_size)

                return True
            except Exception as e:
                error_msg = f"Attempt {attempt + 1}/{retry} failed: {str(e)}"
                print(f"✗ {os.path.basename(output_path)}: {error_msg}")

                if attempt < retry - 1:
                    print(f"  ⏳ Retrying in 2 seconds...")
                    time.sleep(2)
                else:
                    # Log failed download
                    self.failed_downloads.append({
                        'url': url,
                        'path': output_path,
                        'filename': os.path.basename(output_path),
                        'error': str(e)
                    })
                    print(f"  ❌ FAILED after {retry} attempts")
                    return False
        return False

    def download_cover_to_chapter(self, cover_url, chapter_path, progress_callback=None):
        """Download cover as 00.{ext}"""
        try:
            if not cover_url:
                return False

            ext = cover_url.split('.')[-1].split('?')[0].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                ext = 'jpg'

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

            response = self.session.get(cover_url, timeout=30)
            response.raise_for_status()

            with open(cover_path, 'wb') as f:
                f.write(response.content)

            print(f"✓ Cover saved:  {cover_filename}")

            if progress_callback:
                progress_callback(0, 1, f"{cover_filename} (cover)", "completed")

            return True
        except Exception as e:
            print(f"✗ Cover error: {e}")
            self.failed_downloads.append({
                'url': cover_url,
                'path': cover_path,
                'filename': cover_filename,
                'error': str(e),
                'type': 'cover'
            })
            return False

    def download_chapter(self, chapter_info, page_urls, output_path, progress_callback=None,
                         cover_url=None, is_first_chapter=False):
        """Download chapter with error tracking"""
        try:
            os.makedirs(output_path, exist_ok=True)

            # Download cover FIRST if first chapter
            if is_first_chapter and cover_url:
                self.download_cover_to_chapter(cover_url, output_path, progress_callback)

            total_pages = len(page_urls)
            successful_downloads = 0
            failed_pages = []

            for i, page_url in enumerate(page_urls, 1):
                if self.is_stopped:
                    return False

                self.check_pause()

                ext = page_url.split('.')[-1].split('?')[0].lower()
                if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                    ext = 'jpg'

                if total_pages < 100:
                    page_filename = f"{i:02d}.{ext}"
                else:
                    page_filename = f"{i:03d}.{ext}"

                page_path = os.path.join(output_path, page_filename)

                if os.path.exists(page_path):
                    if progress_callback:
                        progress_callback(i, total_pages, page_filename, "skipped")
                    successful_downloads += 1
                    continue

                if progress_callback:
                    progress_callback(i, total_pages, page_filename, "downloading")

                def image_progress(downloaded, total):
                    if progress_callback:
                        progress_callback(i, total_pages, page_filename, "downloading", downloaded, total)

                success = self.download_image(page_url, page_path, progress_callback=image_progress)

                if success:
                    if progress_callback:
                        progress_callback(i, total_pages, page_filename, "completed")
                    successful_downloads += 1
                else:
                    if self.is_stopped:
                        return False
                    if progress_callback:
                        progress_callback(i, total_pages, page_filename, "failed")
                    failed_pages.append({
                        'page_num': i,
                        'filename': page_filename,
                        'url': page_url,
                        'path': page_path
                    })

                time.sleep(0.2)

            # Report results
            print(f"\n📊 Chapter Summary:")
            print(f"   ✓ Success: {successful_downloads}/{total_pages}")
            if failed_pages:
                print(f"   ✗ Failed: {len(failed_pages)}/{total_pages}")
                print(f"   📄 Missing pages: {', '.join([str(p['page_num']) for p in failed_pages])}")

            return not self.is_stopped
        except Exception as e:
            print(f"✗ Chapter error: {e}")
            return False

    def retry_failed_downloads(self, progress_callback=None):
        """Retry all failed downloads with max attempts and timeout"""
        if not self.failed_downloads:
            return True

        retry_start_time = time.time()

        print(f"\n{'=' * 60}")
        print(f"🔄 Retrying {len(self.failed_downloads)} failed downloads (max {self.max_retry_attempts} attempts)...")
        print(f"{'=' * 60}\n")

        # Filter files that haven't exceeded max retry attempts
        retry_list = []
        permanently_failed = []
        
        for item in self.failed_downloads:
            file_key = item['path']
            current_retry_count = self.retry_counts.get(file_key, 0)
            
            if current_retry_count < self.max_retry_attempts:
                # Still within retry limit
                self.retry_counts[file_key] = current_retry_count + 1
                retry_list.append(item)
            else:
                # Exceeded max retries
                permanently_failed.append(item)
        
        if permanently_failed:
            print(f"⚠️  {len(permanently_failed)} files exceeded max retry attempts and will be skipped")
        
        if not retry_list:
            print(f"✅ No more retries needed (all files either succeeded or exceeded max attempts)")
            self.failed_downloads = permanently_failed
            return True

        # Clear failed list before retry
        self.failed_downloads = []

        for idx, item in enumerate(retry_list, 1):
            # Check timeout
            elapsed_time = time.time() - retry_start_time
            if elapsed_time > self.retry_timeout:
                print(f"\n⏱️  Retry timeout ({self.retry_timeout}s) reached, stopping retries")
                # Re-add remaining files to failed list (including current item being processed)
                # idx is 1-based, so current item is at index idx-1
                self.failed_downloads.extend(retry_list[idx-1:])
                break
            
            if self.is_stopped:
                break

            file_key = item['path']
            retry_attempt = self.retry_counts.get(file_key, 1)

            print(f"\n🔄 Retry [{idx}/{len(retry_list)}] Attempt {retry_attempt}/{self.max_retry_attempts}: {item['filename']}")

            if progress_callback:
                progress_callback(idx, len(retry_list), item['filename'], f"retry_attempt_{retry_attempt}")

            success = self.download_image(item['url'], item['path'], retry=3)

            if success:
                print(f"   ✓ SUCCESS on retry attempt {retry_attempt}!")
            else:
                print(f"   ✗ Still failed after retry attempt {retry_attempt}")

        # Add permanently failed files back to the list
        self.failed_downloads.extend(permanently_failed)

        # Check if still have failures
        if self.failed_downloads:
            print(f"\n⚠️  {len(self.failed_downloads)} downloads still failed after retry phase")
            print(f"📄 Failed files:")
            for item in self.failed_downloads[:5]:  # Show first 5
                print(f"   - {item['filename']}")
            if len(self.failed_downloads) > 5:
                print(f"   ... and {len(self.failed_downloads) - 5} more")
            return False
        else:
            print(f"\n✅ All failed downloads recovered!")
            return True

    def verify_chapter(self, chapter_path, expected_pages):
        """Verify all pages exist"""
        missing_pages = []

        for i in range(expected_pages):
            page_num = i + 1
            found = False

            # Check all possible extensions
            for ext in ['jpg', 'jpeg', 'png', 'webp']:
                if expected_pages < 100:
                    filename = f"{page_num:02d}.{ext}"
                else:
                    filename = f"{page_num:03d}.{ext}"

                filepath = os.path.join(chapter_path, filename)
                if os.path.exists(filepath):
                    found = True
                    break

            if not found:
                missing_pages.append(page_num)

        return missing_pages

    def create_cbz(self, chapter_path, output_cbz_path):
        try:
            print(f"📦 Creating CBZ: {os.path.basename(output_cbz_path)}")

            with zipfile.ZipFile(output_cbz_path, 'w', zipfile.ZIP_DEFLATED) as cbz:
                image_files = sorted([f for f in os.listdir(chapter_path)
                                      if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])

                for img_file in image_files:
                    img_path = os.path.join(chapter_path, img_file)
                    cbz.write(img_path, img_file)

            print(f"✓ CBZ created:  {os.path.basename(output_cbz_path)}")
            return True
        except Exception as e:
            print(f"✗ CBZ error: {e}")
            return False

    def create_pdf(self, chapter_path, output_pdf_path):
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

                temp_jpg = img_path.rsplit('. ', 1)[0] + '_temp.jpg'
                img.save(temp_jpg, 'JPEG', quality=95)

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
            print(f"✗ PDF error:  {e}")
            return False

    def merge_cbz_files(self, cbz_files, output_path, manga_title):
        try:
            merged_cbz_path = os.path.join(output_path, f"{self.sanitize_filename(manga_title)}_Complete.cbz")

            print(f"\n📦 Merging {len(cbz_files)} CBZ files...")

            with zipfile.ZipFile(merged_cbz_path, 'w', zipfile.ZIP_DEFLATED) as merged_cbz:
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
        """Download with auto-retry failed downloads"""

        print(f"\n{'=' * 60}")
        print(f"📚 Download:  {manga_title}")
        print(f"   Chapters: {len(chapters_data)}")
        print(f"   CBZ per:  {create_cbz_per_chapter} | PDF per: {create_pdf_per_chapter}")
        print(f"   CBZ all:  {create_cbz_all} | PDF all: {create_pdf_all}")
        print(f"{'=' * 60}\n")

        manga_title = self.sanitize_filename(manga_title)
        manga_path = os.path.join(output_dir, manga_title)

        total_chapters = len(chapters_data)
        cbz_files = []
        pdf_files = []

        need_cbz_per = create_cbz_per_chapter or create_cbz_all
        need_pdf_per = create_pdf_per_chapter or create_pdf_all

        # Download all chapters
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
            success = self.download_chapter(chapter_info, page_urls, chapter_path, page_progress,
                                            cover_url=cover_url, is_first_chapter=is_first)

            if self.is_stopped:
                return False

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

        # RETRY FAILED DOWNLOADS
        if self.failed_downloads and not self.is_stopped:
            print(f"\n{'=' * 60}")
            print(f"🔄 RETRY PHASE - {len(self.failed_downloads)} failed downloads detected")
            print(f"{'=' * 60}")

            if progress_callback:
                progress_callback(total_chapters, total_chapters, "Retrying failed downloads", "retrying")

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
        print(f"\n{'=' * 60}")
        print(f"✅ Download Complete!")
        if self.failed_downloads:
            print(f"⚠️ {len(self.failed_downloads)} pages still failed after all retries")
            print(f"📄 Failed files:")
            for item in self.failed_downloads:
                print(f"   - {item['filename']}")
        else:
            print(f"🎉 All pages downloaded successfully!")
        print(f"{'=' * 60}\n")

        return not self.is_stopped