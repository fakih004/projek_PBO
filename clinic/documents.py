"""Printable PDF referral using the same clinical snapshot as the HTML letter."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from .revisions import ReferralService


def referral_pdf(v):
    buffer=BytesIO()
    document=SimpleDocTemplate(buffer,pagesize=(210*mm,297*mm),rightMargin=22*mm,leftMargin=22*mm,topMargin=20*mm,bottomMargin=20*mm,
                              title=f'Surat Rujukan {v.referral.number}',author='Klinik Medika Husada')
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Clinic',parent=styles['Title'],fontSize=18,textColor=colors.HexColor('#00685f'),spaceAfter=10))
    styles['BodyText'].leading=15
    def para(value,style='BodyText'):
        return Paragraph(escape(str(value or '—')).replace('\n','<br/>'),styles[style])
    d=ReferralService.values(v)
    story=[para('KLINIK MEDIKA HUSADA','Clinic'),para('SURAT RUJUKAN','Heading2'),
           para(f'No. Rujukan: {v.referral.number}'),para(f'Tanggal: {d["referral_date"].strftime("%d/%m/%Y")}'),Spacer(1,8*mm)]
    table=Table([[para(label),para(value)] for label,value in [('Nama Pasien',v.patient.user.name),('No. RM',v.patient.mr),
        ('Tanggal Lahir',v.patient.birth_date.strftime('%d/%m/%Y')),('Jenis Kelamin',v.patient.gender)]],colWidths=[45*mm,115*mm])
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#eff4ff')),('VALIGN',(0,0),(-1,-1),'TOP'),
                             ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.extend([table,Spacer(1,6*mm)])
    for title,key in [('Diagnosis','diagnosis'),('Alasan Rujukan','reason'),('Telah dilakukan: Pemeriksaan','examination'),
        ('Telah dilakukan: Tindakan','treatments'),('Terapi / Obat','medicines'),('Kondisi Klinis Pasien','condition')]:
        story.extend([para(title,'Heading3'),para(d[key])])
    story.extend([para('Dirujuk ke','Heading3'),para('Rumah Sakit: '+d['hospital']),para('Poli / Spesialis: '+d['specialist']),
                  para('Catatan Klinis','Heading3'),para(d['notes'] or 'Tidak ada catatan tambahan.'),Spacer(1,10*mm),
                  para('Dokter Pengirim'),para(v.doctor.user.name,'Heading3'),para('Klinik Medika Husada')])
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8); canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(22*mm,12*mm,v.referral.number)
        canvas.drawRightString(188*mm,12*mm,f'Halaman {doc.page}')
    document.build(story,onFirstPage=footer,onLaterPages=footer)
    buffer.seek(0)
    return buffer
