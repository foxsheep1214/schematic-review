#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查器共用的数值读取：有限数与 {min, max} 区间。"""
import math

def number(value):
    """有限数值或 None；布尔不算数值。"""
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) else None


def span(value):
    """保证区间 (min, max)；缺任一端或次序颠倒都返回 None。"""
    if not isinstance(value, dict):
        return None
    low, high = number(value.get('min')), number(value.get('max'))
    if low is None or high is None or low > high:
        return None
    return (low, high)
