#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计划项生成的共享小工具（原 plan_review 内部函数，供检查器复用）。"""
import hashlib
import re


def slug(value):
    value = re.sub(r'[^A-Za-z0-9]+', '-', str(value or '').upper()).strip('-')
    return value[:64] or 'GLOBAL'


def frame_slug(value):
    """slug for a function id: a name too long for 64 characters keeps its first 55 and an 8-digit hash of the whole
    name, so two long names that share a prefix never share an id; a name that fits is its slug."""
    full = re.sub(r'[^A-Za-z0-9]+', '-', str(value or '').upper()).strip('-')
    if len(full) <= 64:
        return slug(value)
    return full[:55].rstrip('-') + '-' + hashlib.sha1(str(value).encode('utf-8')).hexdigest()[:8].upper()


def empty_handoff():
    return {'required': False, 'state': None}
