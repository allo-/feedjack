# -*- coding: utf-8 -*-
from __future__ import unicode_literals


from django.conf import settings
from django.db import connection
from django.db.models import Q, Max
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator, InvalidPage
from django.http import Http404
from django.utils.encoding import smart_unicode, force_unicode
from django.utils.html import escape
from django.utils import timezone
from django.contrib.sites.shortcuts import get_current_site

from feedjack import models

import itertools as it, operator as op, functools as ft
from collections import OrderedDict
from datetime import datetime, timedelta
import warnings


try:
	from lxml.html import fromstring as lxml_fromstring, tostring as lxml_tostring
	from lxml.html.clean import Cleaner as lxml_Cleaner
	from lxml.etree import XMLSyntaxError as lxml_SyntaxError,\
		ParserError as lxml_ParserError

except ImportError:
	warnings.warn( 'Failed to import "lxml" module, some'
		' html-sanitization and processing functionality, as well'
		' as some template tags will be unavailable.' )

	# at least strip c0 control codes, which are quite common in broken html
	_xml_c0ctl_chars = bytearray(
		set(it.imap(chr, xrange(32)))\
			.difference(b'\x09\x0a\x0d').union(b'\x7f'))
	_xml_c0ctl_trans = dict(it.izip(
		_xml_c0ctl_chars, '_'*len(_xml_c0ctl_chars) ))

	def html_cleaner(string):
		'Produces template-safe valid xml-escaped string.'
		return force_unicode(string).translate(_xml_c0ctl_trans)

	def lxml_fail(string):
		import lxml
		raise NotImplementedError('Looks like some of lxml imports has failed')
	lxml_tostring = lxml_soup = lxml_fail

else:
	def lxml_soup(string):
		'Safe processing of any tag soup (which is a norm on the internets).'
		try: doc = lxml_fromstring(force_unicode(string))
		except (lxml_SyntaxError, lxml_ParserError): # last resort for "tag soup"
			from lxml.html.soupparser import fromstring as soup
			doc = soup(force_unicode(string))
		return doc

	def html_cleaner(string):
		'str -> str, like lxml.html.clean.clean_html, but removing styles as well.'
		if string == "":
			return string
		doc = lxml_soup(string)
		lxml_Cleaner(style=True)(doc)
		return lxml_tostring(doc)


def get_extra_context(request):
	'Returns extra data useful to the templates.'
	# XXX: clean this up from obsolete stuff
	feedjack_site = models.Site.objects.get(django_site=get_current_site(request))
	ctx = {}
	ctx['site'] = feedjack_site
	feeds = feedjack_site.active_feeds.order_by('name')
	ctx['feeds'] = feeds

	ctx['last_checked'] = models.Feed.objects.aggregate(last_checked=Max('last_checked'))['last_checked']
	ctx['last_modified'] = models.Feed.objects.aggregate(last_modified=Max('last_modified'))['last_modified']

	# media_url is set here for historical reasons,
	#  use static_url or STATIC_URL (from django context) in any new templates.
	ctx['media_url'] = ctx['static_url'] =\
		'{}feedjack/{}'.format(settings.STATIC_URL, feedjack_site.template)
	ctx['groups'] = models.Group.objects.filter(subscriber__site=feedjack_site).distinct()
	ctx['ungrouped'] = models.Subscriber.objects.filter(group=None, site=feedjack_site)

	return ctx


def get_posts_tags(subscribers, object_list, feed, tag_name):
	'''Adds a qtags property in every post object in a page.
		Use "qtags" instead of "tags" in templates to avoid unnecesary DB hits.'''

	tagd = dict()
	user_obj = None
	tag_obj = None
	tags = models.Tag.objects.extra(
		select=dict(post_id='{0}.{1}'.format(
			*it.imap( connection.ops.quote_name,
				('feedjack_post_tags', 'post_id') ) )),
		tables=['feedjack_post_tags'],
		where=[
		'{0}.{1}={2}.{3}'.format(*it.imap( connection.ops.quote_name,
			('feedjack_tag', 'id', 'feedjack_post_tags', 'tag_id') )),
		'{0}.{1} IN ({2})'.format(
			connection.ops.quote_name('feedjack_post_tags'),
			connection.ops.quote_name('post_id'),
			', '.join([str(post.id) for post in object_list]) ) ] )

	for tag in tags:
		if tag.post_id not in tagd: tagd[tag.post_id] = list()
		tagd[tag.post_id].append(tag)
		if tag_name and tag.name == tag_name: tag_obj = tag

	subd = dict()
	for sub in subscribers: subd[sub.feed.id] = sub
	for post in object_list:
		if post.id in tagd: post.qtags = tagd[post.id]
		else: post.qtags = list()
		post.subscriber = subd[post.feed.id]
		if feed == post.feed: user_obj = post.subscriber

	return user_obj, tag_obj

def get_page(request, site, page=1):
	'Returns a paginator object and a requested page from it.'

	criterias = {}
	if 'since' in request.GET:
		since = request.GET.get('since')
		criterias['since'] = since
	if 'until' in request.GET:
		until = request.GET.get('until')
		criterias['until'] = until
	group = request.GET.get("group", None)
	subscriber = request.GET.get("subscriber", None)

	asc = False
	if request.GET.get('asc', None) == "1":
		asc = True
		criterias['asc'] = True
	else:
		criterias['asc'] = False

	try:
		sorting = models.SITE_ORDERING_REVERSE[site.order_posts_by]
		if not asc:
		   sorting = "-" + sorting

		posts = models.Post.objects.filtered(site, **criterias)\
			.order_by(sorting, 'feed', '-date_created')\
			.select_related('feed')
		if subscriber:
			try:
				posts = posts.filter(feed__subscriber=subscriber)
			except ValueError:
				raise Http404("Malformed subscriber parameter")
		elif group:
			# get all subscribers for the current site, which are in the group
			try:
				group_subscribers = models.Subscriber.objects.filter(site=site, group=group)
				posts = posts.filter(feed__subscriber__in=group_subscribers)
			except ValueError:
				raise Http404("Malformed group parameter")
	except ValidationError:
		raise Http404('Validation Error (probably malformed since/until date)')

	# filter by PostMark, like ?marked=U,I,L or ?marked=R
	mark_filter = request.GET.get("marked", "")
	if mark_filter and request.user.is_authenticated():
		mark_filter = mark_filter.split(",")
		if "U" in mark_filter: # for unread, list posts without PostMark object, too
			posts = posts.filter(Q(postmark__user=request.user, postmark__mark__in=mark_filter)|~Q(postmark__user=request.user))
		else:
			posts = posts.filter(postmark__user=request.user, postmark__mark__in=mark_filter)

	paginator = Paginator(posts, site.posts_per_page)
	try:
		paginator_page = paginator.page(page)
	except InvalidPage:
		raise Http404()

	if request.user.is_authenticated():
		for post in paginator_page.object_list:
			mark = None
			if request.user.is_authenticated():
				mark = models.PostMark.objects.filter(user=request.user, post=post)
			if mark:
				post.mark = mark[0].mark
			else:
				post.mark = "U" #unread

	return paginator_page
