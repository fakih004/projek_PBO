"""Jam simulasi sementara untuk menguji alur klinik di luar jam operasional."""
from datetime import date, datetime, time
from flask import current_app, has_app_context


def now():
    if has_app_context() and current_app.config.get('TEST_CLOCK', False):
        return datetime.combine(date.today(), time.min)
    return datetime.now()


def today():
    return now().date()
