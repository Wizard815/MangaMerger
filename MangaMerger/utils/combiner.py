import os, io, zipfile, tempfile, shutil, re
from PyPDF2 import PdfMerger, PdfReader
from PyPDF2.errors import PdfReadError
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

VALID_IMG = (".jpg", ".jpeg", ".png", ".gif", ".webp")

# ------------------------------
# Helpers
# ------------------------------
def _make_index_text(chapter_list):
    lines = ["Chapters Included:"] + [f"- {c}" for c in chapter_list]
    return "\n".join(lines)

def _create_index_pdf(chapter_list):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 730, "Chapters Included:")
    c.setFont("Helvetica", 12)
    y = 700
    for ch in chapter_list:
        if y < 72:
            c.showPage()
            y = 730
        c.drawString(100, y, f"- {ch}")
        y -= 18
    c.save()
    buf.seek(0)
    return buf

def _numeric_key(s):
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    return float(nums[0]) if nums else 0.0

def _sorted_files(files):
    try:
        return sorted(files, key=_numeric_key)
    except Exception:
        return sorted(files)

# ------------------------------
# CBZ → individual PDFs
# ------------------------------
def _cbz_to_pdfs(cbz_path, tmp_dir, chap_index):
    """Extract images from a CBZ and convert them to PDF pages for that chapter."""
    made = []
    try:
        with zipfile.ZipFile(cbz_path, "r") as z:
            imgs = [m for m in z.namelist() if m.lower().endswith(VALID_IMG)]
            imgs = _sorted_files(imgs)
            for j, name in enumerate(imgs, 1):
                data = z.read(name)
                im = Image.open(io.BytesIO(data)).convert("RGB")
                page = os.path.join(tmp_dir, f"{chap_index:03d}_{j:03d}.pdf")
                im.save(page, "PDF")
                made.append(page)
    except Exception as e:
        print(f"⚠️  Failed to convert {cbz_path}: {e}")
    return made

# ------------------------------
# Combine PDF
# ------------------------------
def combine_pdf(folder_path, selected_files, export_folder, volume_name):
    import time
    manga = os.path.basename(folder_path)
    full_name = f"{manga}_{volume_name}"
    out_dir = os.path.join(export_folder, manga)
    os.makedirs(out_dir, exist_ok=True)
    output = os.path.join(out_dir, f"{full_name}.pdf")

    base_tmp = tempfile.mkdtemp()
    merger = PdfMerger()
    total_pages = 0
    chapter_pdfs = []  # collect all temp pdfs to delete later

    try:
        merger.append(_create_index_pdf(selected_files))
        ordered = _sorted_files(selected_files)

        for i, f in enumerate(ordered, 1):
            src_path = os.path.join(folder_path, f)
            if not os.path.exists(src_path):
                continue

            # Each chapter gets its own subdir to avoid lock collisions
            chap_tmp = os.path.join(base_tmp, f"chap_{i:03d}")
            os.makedirs(chap_tmp, exist_ok=True)

            if f.lower().endswith(".cbz"):
                pdfs = _cbz_to_pdfs(src_path, chap_tmp, i)
                for p in pdfs:
                    merger.append(p)
                    chapter_pdfs.append(p)
                    total_pages += 1
                print(f"📦 {f}: {len(pdfs)} image pages added")

            elif f.lower().endswith(".pdf"):
                try:
                    reader = PdfReader(src_path)
                    if len(reader.pages) > 0:
                        merger.append(reader)
                        total_pages += len(reader.pages)
                        print(f"📄 {f}: {len(reader.pages)} pages added")
                except PdfReadError:
                    print(f"⚠️ Invalid PDF skipped: {f}")
            else:
                print(f"⚠️ Skipped {f}")

        merger.write(output)
        merger.close()
        print(f"✅ PDF created with {total_pages} pages (+TOC)")

        # Wait briefly to ensure file handles are released
        time.sleep(0.5)

        # Cleanup
        shutil.rmtree(base_tmp, ignore_errors=True)
        return output

    except Exception as e:
        print(f"❌ combine_pdf error: {e}")
        try:
            merger.close()
        except Exception:
            pass
        return None


# ------------------------------
# Combine CBZ (same good version)
# ------------------------------
def combine_cbz(folder_path, selected_files, export_folder, volume_name):
    manga = os.path.basename(folder_path)
    full_name = f"{manga}_{volume_name}"
    out_dir = os.path.join(export_folder, manga)
    os.makedirs(out_dir, exist_ok=True)
    output = os.path.join(out_dir, f"{full_name}.cbz")

    tmp = tempfile.mkdtemp()
    total_images = 0
    try:
        # TOC image
        toc_png = os.path.join(tmp, "000_TOC.png")
        text = _make_index_text(selected_files)
        img = Image.new("RGB", (900, 1300), (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((40, 40), text, fill=(0, 0, 0))
        img.save(toc_png, "PNG")

        ordered = _sorted_files(selected_files)
        for chap_i, f in enumerate(ordered, 1):
            src = os.path.join(folder_path, f)
            if not os.path.exists(src):
                continue
            if f.lower().endswith(".cbz"):
                with zipfile.ZipFile(src, "r") as z:
                    members = [m for m in z.namelist() if m.lower().endswith(VALID_IMG)]
                    members = _sorted_files(members)
                    for j, name in enumerate(members, 1):
                        data = z.read(name)
                        ext = os.path.splitext(name)[1].lower()
                        newname = f"{chap_i:03d}_{j:03d}{ext}"
                        with open(os.path.join(tmp, newname), "wb") as out:
                            out.write(data)
                        total_images += 1
            elif f.lower().endswith(VALID_IMG):
                ext = os.path.splitext(f)[1].lower()
                newname = f"{chap_i:03d}_000{ext}"
                shutil.copy2(src, os.path.join(tmp, newname))
                total_images += 1

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as cbz:
            for root, _, files in os.walk(tmp):
                for n in sorted(files):
                    cbz.write(os.path.join(root, n),
                              os.path.relpath(os.path.join(root, n), tmp))
        print(f"✅ CBZ created with {total_images} images + TOC")
        return output
    except Exception as e:
        print(f"❌ combine_cbz error: {e}")
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
