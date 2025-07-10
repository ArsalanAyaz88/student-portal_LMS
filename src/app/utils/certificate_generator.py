from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import os
import io
import math
import uuid
import logging
from datetime import datetime
from ..utils.file import save_upload_and_get_url
from fastapi import UploadFile
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CertificateGenerator:
    """PDF certificate with header banner, layered border, watermark,
       arc header, starburst seal, logo, body, and footer."""
    def __init__(self, logo_path=None, signature_path=None):
        # Always use the user's provided absolute logo path
        self.logo_path = r"F:\student_project\application\src\app\utils\sabri_logo.png"
        # Signature path (optional)
        self.signature_path = signature_path

    def _generate_number(self):
        ts  = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        uid = uuid.uuid4().hex[:8].upper()
        return f"CERT-{ts}-{uid}"

    async def generate(self,
                 username: str,
                 course_title: str,
                 completion_date: str = None,
                 certificate_number: str = None) -> str:
        """
        Generate a certificate PDF and upload it to B2 storage.
        
        Args:
            username: Name of the certificate recipient
            course_title: Title of the course
            completion_date: Date of completion
            certificate_number: Unique certificate number
            
        Returns:
            str: URL to the uploaded certificate in B2 storage
        """
        try:
            # Defaults
            if not completion_date:
                completion_date = datetime.utcnow().date().isoformat()
            if not certificate_number:
                certificate_number = self._generate_number()

            pdf_buffer = io.BytesIO()
            width, height = landscape(A4)
            c = canvas.Canvas(pdf_buffer, pagesize=(width, height))

            # Define border_margin for downstream code compatibility
            border_margin = 0.32*inch

            # --- Use User's Certificate Template as Background ---
            # Use absolute path for template image (avoid path errors)
            template_img_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'certificate_template.jpg'))
            if os.path.exists(template_img_path):
                c.drawImage(template_img_path, 0, 0, width=width, height=height, mask='auto')
            # --- End Template Background ---

            # --- Layout Constants ---
            cx = width / 2
            border_margin = 0.32 * inch
            content_left = border_margin + 0.5 * inch
            content_right = width - border_margin - 0.5 * inch
            inset = 0.8 * inch    # tweak this value to taste
        
            # 1. Header: Institute Name (bold uppercase serif, centered at top)
            header_text = "SABRI ULTRASOUND TRAINING INSTITUTE"
            header_font = 'Times-Bold'
            header_font_size = 28
            header_y = height - border_margin - 3 * (header_font_size / 72.0) * inch
            c.setFont(header_font, header_font_size)
            c.setFillColor(colors.HexColor('#B8860B'))  # Gold shade
            c.drawCentredString(cx, header_y, header_text.upper())

            # 2. Logo (centered below header, 2 lines spacing)
            logo_w = 1.5 * inch
            logo_h = 1.5 * inch
            logo_y = header_y - 0.35 * inch - logo_h  # 2 lines = 0.7 inch
            if self.logo_path and os.path.exists(self.logo_path):
                c.drawImage(self.logo_path, cx - logo_w/2, logo_y, width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto')

            # 3. Certificate Title (large bold serif, centered two lines below logo)
            title_text = "Certificate of Commendation"
            title_font = 'Times-Bold'
            title_font_size = 24
            title_y = logo_y - 0.35* inch
            c.setFont(title_font, title_font_size)
            c.setFillColor(colors.HexColor('#222222'))
            c.drawCentredString(cx, title_y, title_text)

            # 4. Award Text (regular serif, centered, 2 lines below title)
            award_text = "This certificate is awarded to"
            award_font = 'Times-Roman'
            award_font_size = 20
            award_y = title_y - 0.35 * inch
            c.setFont(award_font, award_font_size)
            c.setFillColor(colors.HexColor('#222222'))
            c.drawCentredString(cx, award_y, award_text)

            # 5. Recipient Name (blue cursive script, centered, 2 lines below award)
            script_font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'GreatVibes-Regular.ttf')
            name_y = award_y - 0.5 * inch

            if os.path.exists(script_font_path):
                try:
                    pdfmetrics.registerFont(TTFont('GreatVibes', script_font_path))
                    c.setFont('GreatVibes', 32)
                except Exception:
                    c.setFont('Times-Italic', 28)
            else:
                c.setFont('Times-Italic', 28)
            c.setFillColor(colors.HexColor('#003399'))  # Elegant blue
            c.drawCentredString(cx, name_y, username)

            # 5b. Course Title (bold serif, centered, just below recipient name)
            course_title_font = 'Times-Bold'
            course_title_font_size = 20
            course_title_y = name_y - 0.4 * inch
            c.setFont(course_title_font, course_title_font_size)
            c.setFillColor(colors.HexColor('#222222'))
            c.drawCentredString(cx, course_title_y,  f"Course Title: {course_title}")

            # 6. Recognition Line (regular serif, 2 lines below name, then 0.25 inch between each line)
            recognition_y = course_title_y - 0.35 * inch
            c.setFont('Times-Roman', 14)
            c.setFillColor(colors.HexColor('#222222'))
            c.drawCentredString(cx, recognition_y, "in recognition of")
            c.drawCentredString(cx, recognition_y - 0.25 * inch, "Attending the online Lectures of")
            c.drawCentredString(cx, recognition_y - 0.50 * inch, "12 weeks of basic Ultrasound Training Programme")

            # 7. Certificate Metadata (bottom left, inside border)
            meta_font = 'Times-Bold'
            meta_font_size = 10
            meta_x = content_left + 0.5 * inch
            import datetime
            # Format the date in a human-readable way
            try:
                issue_dt = datetime.datetime.fromisoformat(completion_date)
                human_date = issue_dt.strftime("%B %d, %Y")  # e.g., "May 10, 2025"
            except Exception:
                human_date = completion_date  # Fallback if parsing fails

            meta_y = border_margin + 0.8 * inch
            c.setFont(meta_font, meta_font_size)
            c.setFillColor(colors.HexColor('#222222'))
            c.drawString(meta_x, meta_y + 0.25*inch, f"Certificate No: {certificate_number}")
            c.drawString(meta_x, meta_y, f"Issued On: {human_date}")

            # 8. Signature Block (bottom right, inside border, right-aligned)
            sign_x = content_right - inset
            base_y = border_margin + 0.9 * inch  # Start above the border

            # Line 1: Dr Sabir Ali Butt (topmost, red)
            c.setFont('Times-Bold', 24)
            c.setFillColor(colors.red)
            c.drawRightString(sign_x, base_y + 0.60 * inch, "Prof. Dr. Sabir Ali Butt")

            # Line 2: CEO (below, black)
            c.setFont('Times-Roman', 12)
            c.setFillColor(colors.HexColor('#222222'))
            c.drawRightString(sign_x, base_y + 0.36 * inch, "CEO")

            # Line 3: Sabiry Surgical Hospital (below, black)
            c.setFont('Times-Roman', 10)
            c.setFillColor(colors.HexColor('#222222'))
            c.drawRightString(sign_x, base_y + 0.18 * inch, "Sabiry Surgical Hospital")

            # Line 4: Faisalabad (bottom, black)
            c.setFont('Times-Roman', 10)
            c.setFillColor(colors.HexColor('#222222'))
            c.drawRightString(sign_x, base_y, "Faisalabad")

            c.showPage()
            c.save()

            # Upload to B2 storage
            try:
                # Move buffer's cursor to the beginning
                pdf_buffer.seek(0)
                
                # Use save_upload_and_get_url with certificates folder
                url = await save_upload_and_get_url(
                    file=UploadFile(
                        filename=f"certificate_{certificate_number}.pdf",
                        file=pdf_buffer
                    ),
                    folder="certificates"
                )
                
                return url
            except Exception as e:
                logger.error(f"Failed to upload certificate: {str(e)}")
                logger.error(f"Detailed error: {traceback.format_exc()}")
                raise Exception(f"Failed to upload certificate: {str(e)}")

        except Exception as e:
            logger.error(f"Certificate generation failed: {str(e)}")
            logger.error(f"Detailed error: {traceback.format_exc()}")
            raise Exception(f"Failed to generate certificate: {str(e)}")
