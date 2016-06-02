# -*- coding: utf-8 -*-

from django.conf.urls import patterns, url
from feedjack import views


import itertools as it, operator as op, functools as ft
from types import StringTypes, NoneType

specs = dict(feed=('feed', r'\d+'), tag=r'[^/]+')

urljoin = lambda pieces: '/'.join(it.imap(op.methodcaller('strip', '/'), pieces))


urlpatterns = list()

# New-style syndication links
urlpatterns.extend([
	(r'^syndication/atom/?$', views.atomfeed),
	(r'^syndication/rss/?$', views.rssfeed),
	(r'^syndication/opml/?$', views.opml),
	(r'^syndication/foaf/?$', views.foaf) ])

# Index page
urlpatterns.append((r'^$', views.mainview))

# Ajax Stuff
urlpatterns.append((r'^mark-post/(?P<post_id>[0-9]*)/(?P<mark>[A-Z])/$', views.mark_post))

#urlpatterns = patterns('', *urlpatterns)
# new django way. TODO: cleanup the creation of the urls
urlpatterns = [url(*x) for x in urlpatterns]
