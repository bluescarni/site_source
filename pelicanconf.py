#!/usr/bin/env python
# -*- coding: utf-8 -*- #
from __future__ import unicode_literals

AUTHOR = u'Francesco Biscani'
SITENAME = u'Zig Zag Wanderer'
SITEURL = ''

PATH = 'content'

TIMEZONE = 'Europe/Berlin'

DEFAULT_LANG = u'en'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

THEME = './pure-theme'

TAGLINE = 'Stuff of various degrees of importance'

#PROFILE_IMG_URL = 'http://www.gravatar.com/avatar/4dd67eab56c9687453c13002faf3df36'
SOCIAL = (
    ('github', 'https://github.com/bluescarni/'),
)

# Blogroll
#LINKS = (('Pelican', 'http://getpelican.com/'),
#         ('Python.org', 'http://python.org/'),
#         ('Jinja2', 'http://jinja.pocoo.org/'),
#         ('You can modify those links in your config file', '#'),)

# Social widget
#SOCIAL = (('You can add links in your config file', '#'),
#          ('Another social link', '#'),)

DEFAULT_PAGINATION = 10

DEFAULT_DATE = 'fs'

DISPLAY_PAGES_ON_MENU = True

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True

COVER_IMG_URL = 'https://raw.githubusercontent.com/bluescarni/site_source/master/side_pic.jpg'

MENUITEMS = [('About','pages/about-me.html'),
             ('Research','pages/research.html'),
             ('Software','pages/software.html')]

PLUGINS = ["render_math"]
