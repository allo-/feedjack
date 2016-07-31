# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.utils import timezone, encoding

import itertools as it, operator as op, functools as ft
from datetime import datetime, timedelta
import os, sys, math, logging


def command_logger_setup(logger, opts,
                         stream=sys.stdout, verbose_level=logging.DEBUG):
    if not isinstance(opts, dict):
        opts = vars(opts)

    if opts.get('django_logging'):
        return

    verbosity = int(getattr(opts, 'verbosity', 1)) # option from django-admin

    if opts.get('debug') or verbosity >= 3:
        verbosity = logging.DEBUG
    elif opts.get('verbose') or verbosity >= 2:
        verbosity = verbose_level
    elif opts.get('quiet') or verbosity < 1:
        verbosity = logging.WARNING
    else:
        verbosity = logging.INFO

    logging.basicConfig(stream=stream, level=verbosity)

    # Adjust logger for Django-standard "--verbosity" option, add console-output handler
    # This can unexpectedly clash with logging config in settings.py
    logger.setLevel(verbosity)
    log_handler = logging.StreamHandler(stream)
    log_handler.setFormatter(logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s'))
    logger.addHandler(log_handler)


# Somewhat like django.contrib.humanize.templatetags.humanize.naturaltime
# Except shorter, more precise, and can be parsed back easily

def naturaltime_diff(ts, ts0=None, ext=None):
    _units={
        's': 1.0,
        'm': 60.0,
        'h': 3600.0,
        'd': 86400.0,
        'w': 7*86400.0,
        'mo': 30.5*86400.0,
        'y': 365.25*86400.0
    }
    if isinstance(ts, timedelta):
        delta = abs(ts)
    else:
        delta = abs(ts - (ts0 or timezone.now()))

    res = list()
    delta_s = delta.total_seconds()
    for unit, unit_s in sorted(_units.viewitems(), key=op.itemgetter(1), reverse=True):
        val = math.floor(delta_s / unit_s)
        if not val:
            continue
        res.append('{:.0f}{}'.format(val, unit))
        if len(res) >= 2:
            break
        delta_s -= val * unit_s

    if not res:
        return 'now'
    else:
        if ext:
            res.append(ext)
        return ' '.join(res)
