"""Payment declarations and clinical referral extensions to the existing workflow."""
from datetime import date, datetime
from sqlalchemy import update
from . import db
from .models import (Role, User, VisitStatus, PaymentStatus, PaymentRequest,
                     Invoice, Referral, ReferralClinical, Notification, ClinicSettings)
from .services import required, number, NotificationService, BillingService


def clinic_settings():
    return db.session.get(ClinicSettings,1) or ClinicSettings(id=1,bank='BCA',account_number='1234567890',account_name='Klinik Medika Husada',bank_demo=True)


class PaymentVerificationService:
    @staticmethod
    def submit(v, actor, method):
        if actor.role!=Role.PATIENT or v.patient.user_id!=actor.id:
            raise PermissionError('Hanya pasien pemilik invoice yang dapat mengajukan pembayaran.')
        if not v.invoice or v.appointment.insurance or v.status!=VisitStatus.WAITING_PAYMENT:
            raise ValueError('Invoice ini tidak menerima pengajuan pembayaran.')
        if method not in ('Transfer','QRIS'):
            raise ValueError('Tunai dan debit dikonfirmasi langsung oleh kasir.')
        inv=v.invoice
        result=db.session.execute(update(Invoice).where(Invoice.id==inv.id,Invoice.status==PaymentStatus.UNPAID)
                                  .values(status=PaymentStatus.WAITING_VERIFICATION))
        if result.rowcount!=1: raise ValueError('Pembayaran sudah diajukan atau diselesaikan.')
        pending=PaymentRequest(invoice=inv,amount=inv.payable,method=method,active_key=inv.id,status=PaymentStatus.WAITING_VERIFICATION)
        db.session.add(pending)
        for admin in User.query.filter_by(role=Role.ADMIN,active=True):
            db.session.add(Notification(user_id=admin.id,message=f'Pembayaran {method} menunggu verifikasi: {inv.number}, {v.patient.user.name}, Rp{inv.payable:,}.'))
        NotificationService.send(v.patient,'Konfirmasi pembayaran diterima. Menunggu verifikasi Admin/Kasir.')
        return pending

    @staticmethod
    def review(pending, actor, approve):
        if actor.role!=Role.ADMIN: raise PermissionError('Hanya Admin/Kasir dapat memverifikasi pembayaran.')
        inv=pending.invoice
        result=db.session.execute(update(PaymentRequest).where(PaymentRequest.id==pending.id,
            PaymentRequest.status==PaymentStatus.WAITING_VERIFICATION,PaymentRequest.active_key==inv.id).values(
            status=PaymentStatus.PAID if approve else PaymentStatus.UNPAID,active_key=None,reviewed_at=datetime.now(),reviewed_by=actor.id))
        if result.rowcount!=1: raise ValueError('Pengajuan pembayaran sudah diproses.')
        if inv.status!=PaymentStatus.WAITING_VERIFICATION or inv.visit.status!=VisitStatus.WAITING_PAYMENT:
            raise ValueError('Status invoice sudah berubah. Muat ulang halaman.')
        if approve:
            if pending.amount!=inv.payable: raise ValueError('Nominal pengajuan berbeda dari invoice.')
            BillingService.pay(inv.visit,actor,{'method':pending.method,'discount':inv.discount},verified_request=True)
            NotificationService.send(inv.visit.patient,'Pembayaran Anda telah berhasil diverifikasi.')
        else:
            inv.status=PaymentStatus.UNPAID
            NotificationService.send(inv.visit.patient,'Pembayaran belum dapat diverifikasi. Silakan periksa kembali transaksi Anda.')


class ReferralService:
    @staticmethod
    def values(v):
        r=v.referral
        c=r.clinical if r else None
        exam=v.examination
        prescribed='\n'.join(f'{i.medicine.name} — {i.quantity} {i.medicine.unit}; {i.dosage}, {i.frequency}, {i.duration}.' for i in v.prescription.items) if v.prescription else 'Tidak ada obat yang diresepkan.'
        # Prescription is not proof of administration: make that distinction explicit.
        medicines=(('Obat telah diserahkan: ' if v.prescription.status.value=='DISPENSED' else 'Resep (belum tercatat diserahkan): ')+prescribed) if v.prescription else prescribed
        return dict(hospital=r.hospital if r else '',specialist=r.specialist if r else '',reason=r.reason if r else '',notes=r.notes if r else '',
            diagnosis=c.diagnosis if c else exam.diagnosis if exam else '',
            examination=c.examination if c else exam.physical if exam else '',
            treatments=c.treatments if c else (exam.treatment or 'Tidak ada tindakan tambahan.') if exam else '',
            medicines=c.medicines if c else medicines,
            condition=c.condition if c else (exam.assessment or exam.physical) if exam else '',
            referral_date=c.referral_date if c else r.created_at.date() if r else date.today(),version=c.version if c else 0)

    @staticmethod
    def save(v, actor, data):
        if actor.role!=Role.DOCTOR or v.doctor.user_id!=actor.id:
            raise PermissionError('Rujukan hanya dapat ditulis oleh dokter penanggung jawab kunjungan.')
        if not v.examination: raise ValueError('Selesaikan pemeriksaan klinis sebelum membuat rujukan.')
        if v.status==VisitStatus.CANCELLED: raise ValueError('Kunjungan dibatalkan.')
        values={key:required(data,key,160 if key in ('hospital','specialist') else 4000)
                for key in ('hospital','specialist','reason','diagnosis','examination','treatments','medicines','condition')}
        try: day=date.fromisoformat(data.get('referral_date',''))
        except (ValueError,TypeError): raise ValueError('Tanggal rujukan tidak valid.')
        if day<v.appointment.date or day>date.today(): raise ValueError('Tanggal rujukan harus antara tanggal kunjungan dan hari ini.')
        r=v.referral
        creating=r is None
        if creating:
            r=Referral(visit=v,number=f'RUJ-{day:%Y%m%d}-{v.id:05}')
            db.session.add(r)
        if r.clinical:
            version=number(data,'version',1,100000000,True)
            result=db.session.execute(update(ReferralClinical).where(ReferralClinical.id==r.clinical.id,
                ReferralClinical.version==version).values(version=version+1))
            if result.rowcount!=1: raise ValueError('Rujukan telah diperbarui pada sesi lain. Muat ulang sebelum mengedit.')
        r.hospital=values.pop('hospital'); r.specialist=values.pop('specialist'); r.reason=values.pop('reason')
        r.notes=str(data.get('notes',''))[:4000]
        clinical=r.clinical or ReferralClinical(referral=r,version=1)
        for key,value in values.items(): setattr(clinical,key,value)
        clinical.referral_date=day; clinical.updated_at=datetime.now()
        db.session.add(clinical)
        NotificationService.send(v.patient,'Surat rujukan tersedia pada rekam medis Anda.' if creating else 'Dokter memperbarui surat rujukan Anda.')
        return r
