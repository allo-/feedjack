# -*- coding: utf-8 -*-


from django.utils import feedgenerator
from django.shortcuts import render, get_object_or_404
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponse, Http404, HttpResponsePermanentRedirect
from django.utils.cache import patch_vary_headers
from django.template import Context, loader
from django.views.generic import RedirectView
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.utils.encoding import smart_unicode
from django.views.decorators.http import condition
from decorators import login_required_get_parameters

from feedjack import models, fjlib, fjcache

import itertools as it, operator as op, functools as ft
from datetime import datetime
from collections import defaultdict
from urlparse import urlparse
from collections import OrderedDict



def ctx_get(ctx, k):
    v = ctx[k]
    if callable(v): v = ctx[k]()
    return v

def cache_etag(request, *argz, **kwz):
    '''Produce etag value for a cached page.
        Intended for usage in conditional views (@condition decorator).'''
    response, site, cachekey = kwz.get('_view_data') or initview(request)
    if not response: return None
    return fjcache.str2md5(
        '{0}--{1}--{2}'.format( site.id if site else 'x', cachekey,
            response[1].strftime('%Y-%m-%d %H:%M:%S%z') ) )

def cache_last_modified(request, *argz, **kwz):
    '''Last modification date for a cached page.
        Intended for usage in conditional views (@condition decorator).'''
    response, site, cachekey = kwz.get('_view_data') or initview(request)
    if not response: return None
    return response[1]

def initview(request, response_cache=True):
    '''Retrieves the basic data needed by all feeds (host, feeds, etc)
        Returns a tuple of:
            1. A valid cached response or None
            2. The current site object
            3. The cache key
            4. The subscribers for the site (objects)
            5. The feeds for the site (ids)'''

    http_host, path_info = ( smart_unicode(part.strip('/')) for part in
        [ request.META['HTTP_HOST'],
            request.META.get('REQUEST_URI', request.META.get('PATH_INFO', '/')) ] )
    query_string = request.META['QUERY_STRING']

    url = '{0}/{1}'.format(http_host, path_info)
    cachekey = u'{0}?{1}'.format(*it.imap(smart_unicode, (path_info, query_string)))
    hostdict = fjcache.hostcache_get() or dict()

    site_id = hostdict.get(url, None)
    if site_id is not None:
        if response_cache:
            response = fjcache.cache_get(site_id, cachekey)
            if response:
                return response, None, cachekey
        site = models.Site.objects.get(pk=site_id)
    else: # match site from all of them
        sites = models.Site.objects.all()

        django_site = get_current_site(request)
        if sites.count() == 0: # no sites available, create a default one
            site = models.Site(django_site=django_site)
            site.save()
        else:
            site = get_object_or_404(models.Site, django_site=django_site)
            if urlparse(site.url).netloc != http_host: # redirect to proper site hostname
                response = HttpResponsePermanentRedirect(
                    'http://{0}/{1}{2}'.format( site_url.netloc, path_info,
                        '?{0}'.format(query_string) if query_string.strip() else '') )
                return (response, timezone.now()), None, cachekey

        hostdict[url] = site_id = site.id
        fjcache.hostcache_set(hostdict)

    if response_cache:
        response = fjcache.cache_get(site_id, cachekey)
        if response:
            return response, None, cachekey

    return None, site, cachekey


class RedirectForSite(RedirectView):
    '''Simple permanent redirect, taking site prefix
        into account, otherwise similar to RedirectView.'''

    def get(self, request, *args, **kwz):
        response, site, cachekey = initview(request)
        if response: return response[0]
        return HttpResponsePermanentRedirect(site.url + self.url)


def blogroll(request, btype):
    'View that handles the generation of blogrolls.'
    response, site, cachekey = initview(request)
    if response: return response[0]

    template = loader.get_template('feedjack/{0}.xml'.format(btype))
    ctx = fjlib.get_extra_context(request)
    ctx = Context(ctx)
    response = HttpResponse(
        template.render(ctx), content_type='text/xml; charset=utf-8' )

    patch_vary_headers(response, ['Host'])
    fjcache.cache_set(site, cachekey, (response, ctx_get(ctx, 'last_modified')))
    return response

def foaf(request):
    'View that handles the generation of the FOAF blogroll.'
    return blogroll(request, 'foaf')

def opml(request):
    'View that handles the generation of the OPML blogroll.'
    return blogroll(request, 'opml')


def viewdata_decorator(view):
    'View that handles all page requests.'
    def inner(request, **kwargs):
        view_data = initview(request)
        wrap = lambda func: ft.partial(func, _view_data=view_data)
        return condition(etag_func=wrap(cache_etag), last_modified_func=wrap(cache_last_modified))(view)(request=request, view_data=view_data, **kwargs)
    return inner


@viewdata_decorator
def buildfeed(request, feedclass, view_data):
    # TODO: quite a mess, can't it be handled with a default feed-views?
    response, site, cachekey = view_data
    if response: return response[0]

    feed_title = site.title
    if request.GET.get('feed_id'):
        try:
            feed_id = request.GET.get('feed_id')
            feed_title = u'{0} - {1}'.format(
                models.Feed.objects.get(id=feed_id).title, feed_title )
        except ObjectDoesNotExist:
            raise Http404("no such feed") # no such feed
        except ValueError: # id not numeric
            raise Http404("non-numeric feed_id")
    object_list = fjlib.get_page(request, site, page=page).object_list

    feed = feedclass( title=feed_title, link=site.url,
        description=site.description, feed_url=u'{0}/{1}'.format(site.url, '/feed/rss/') )
    last_modified = datetime(1970, 1, 1, 0, 0, 0, 0, timezone.utc)
    for post in object_list:
        # Enclosures are not created here, as these have somewhat unpredictable format,
        #  and don't always fit Django's url+length+type style - href+title links, for instance.
        feed.add_item(
            title = u'{0}: {1}'.format(post.feed.name, post.title),
            link = post.link,
            description = fjlib.html_cleaner(post.content),
            author_email = post.author_email,
            author_name = post.author,
            pubdate = post.date_created,
            updateddate = post.date_modified,
            unique_id = post.link,
            categories = [tag.name for tag in post.tags.all()] )
        if post.date_updated > last_modified: last_modified = post.date_updated

    response = HttpResponse(content_type=feed.mime_type)

    # Per-host caching
    patch_vary_headers(response, ['Host'])

    feed.write(response, 'utf-8')
    if site.use_internal_cache:
        fjcache.cache_set(
            site, cachekey, (response, last_modified) )
    return response


def rssfeed(request):
    'Generates the RSS2 feed.'
    return buildfeed(request=request, feedclass=feedgenerator.Rss201rev2Feed)

def atomfeed(request):
    'Generates the Atom 1.0 feed.'
    return buildfeed(request=request, feedclass=feedgenerator.Atom1Feed)

@login_required_get_parameters(['marked'])
@viewdata_decorator
def mainview(request, view_data):
    response, site, cachekey = view_data
    if not response:
        site = models.Site.objects.get(django_site=get_current_site(request))
        'Returns the context dictionary for a page view.'
        try:
            page = int(request.GET.get('page', 1))
        except ValueError:
            page = 1
        feed, tag = request.GET.get('feed'), request.GET.get('tag')

        if feed:
            try:
                feed = models.Feed.objects.get(pk=feed)
            except ObjectDoesNotExist:
                raise Http404
        page = fjlib.get_page(request, site, page=page)
        subscribers = site.active_subscribers

        # TODO: remove all remaining tag cloud stuff
        tag_obj, tag_cloud = None, tuple()
        try:
            user_obj = None
            if feed:
                user_obj = models.Subscriber.objects.get(site=site, feed=feed)
        except ObjectDoesNotExist:
            raise Http404

        site_proc_tags = site.processing_tags.strip()
        if site_proc_tags != 'none':
            site_proc_tags = filter( None, map(op.methodcaller('strip'), site.processing_tags.split(',')) )
            # XXX: database hit that can be cached
            for site_feed, posts in it.groupby(page.object_list, key=op.attrgetter('feed')):
                proc = site_feed.processor_for_tags(site_proc_tags)
                if proc:
                    proc.apply_overlay_to_posts(posts)
        # TODO: cleanup
        ctx = {
            'last_modified': max(it.imap(
                    op.attrgetter('date_updated'), page.object_list ))\
                if len(page.object_list) else datetime(1970, 1, 1, 0, 0, 0, 0, timezone.utc),
            'object_list': page.object_list,
            'subscribers':  subscribers.select_related('feed'),
            'tag': tag_obj,
            'feed': feed,
            'url_suffixi': ''.join((
                '/feed/{0}'.format(feed.id) if feed else '',
                '/tag/{0}'.format(escape(tag)) if tag else '' )),
            'p': page, # "page" is taken by legacy number
            'p_10neighbors': OrderedDict(
                # OrderedDict of "num: exists" values
                # Use as "{% for p_num, p_exists in p_10neighbors.items|slice:"7:-7" %}"
                (p, p >= 1 and p <= page.paginator.num_pages)
                for p in ((page.number + n) for n in xrange(-10, 11)) ),

            ## DEPRECATED:
            # Totally misnamed and inconsistent b/w user/user_obj,
            #  use "feed" and "subscribers" instead.
            'user_id': feed and feed.id,
            'user': user_obj,

            # Legacy flat pagination context, use "p" instead.
            'is_paginated': page.paginator.num_pages > 1,
            'results_per_page': site.posts_per_page,
            'has_next': page.has_next(),
            'has_previous': page.has_previous(),
            'page': page.number,
            'next': page.number + 1,
            'previous': page.number - 1,
            'pages': page.paginator.num_pages,
            'hits': page.paginator.count,
            'url_parameters': request.GET
        }
        ctx2 = fjlib.get_extra_context(request)
        for key in ctx2:
            ctx[key] = ctx2[key]
        response = render(request, u'feedjack/{0}/post_list.html'.format(site.template), ctx)
        # per host caching, in case the cache middleware is enabled
        patch_vary_headers(response, ['Host'])
        if site.use_internal_cache:
            fjcache.cache_set( site, cachekey,
                (response, ctx_get(ctx, 'last_modified')) )
    else:
        response = response[0]
    return response

def mark_post(request, post_id, mark):
    if not request.user.is_authenticated():
        return Http404("No user logged in")
    post = get_object_or_404(models.Post, id=post_id)
    post_mark, created = models.PostMark.objects.get_or_create(user=request.user, post=post, defaults={"mark": "U"})
    post_mark.mark = mark
    post_mark.save()
    return HttpResponse("OK")
