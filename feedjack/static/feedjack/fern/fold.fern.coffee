$(document).ready ->
	/* IE6? Fuck off */
	return unless localStorage?

	/* size of lru journal to trigger gc */
	limit_lru_gc = 300
	/* size of lru journal after cleanup */
	limit_lru = 200
	/* minimum number of folds to keep */
	limit = 100

	Object::get_length = ->
		len = 0
		len += 1 for own k,v of this
		len

	get_ts = -> Math.round((new Date()).getTime() / 1000)

	[url_site, url_media, url_store] = [
		$('html').data('url_site'),
		$('html').data('url_media'),
		$('html').data('url_store') ]
	storage_key = "feedjack.fold.#{url_site}"
	[folds, folds_lru, folds_ts] = [
		localStorage["#{storage_key}.folds"],
		localStorage["#{storage_key}.folds_lru"],
		localStorage["#{storage_key}.folds_ts"] ]
	[folds, folds_lru, folds_ts] = [
		if folds then JSON.parse(folds) else {},
		if folds_lru then JSON.parse(folds_lru) else [],
		if folds_ts then JSON.parse(folds_ts) else {} ]

	folds_update = (key, value=0) ->
		folds[key] = value
		folds_lru.push([key, value])
		folds_ts[key] = get_ts()

	folds_commit = ->
		/* gc */
		len_lru = folds_lru.length
		if len_lru > limit_lru_gc
			[folds_lru, folds_lru_gc] = [
				folds_lru[(len_lru - limit_lru)..len_lru],
				folds_lru[0...(len_lru - limit_lru)] ]
			len_folds = folds.get_length() - limit
			for [key,val] in folds_lru_gc
				break if len_folds <= 0
				if folds[key] == val
					folds_update(key)
					len_folds -= 1
		/* actual storage */
		localStorage["#{storage_key}.folds"] = JSON.stringify(folds)
		localStorage["#{storage_key}.folds_lru"] = JSON.stringify(folds_lru)
		localStorage["#{storage_key}.folds_ts"] = JSON.stringify(folds_ts)

	folds_sync = (ev) ->
		return unless $.cookie('feedjack.tracking')

		/* rotation effect for image while data ping-pong goes on */
		img = $(ev.target)
		timer = setInterval(( ->
			tilt = img.data('tilt') or 0
			img.css(
				'transform': "rotate(#{tilt}deg)"
				'-moz-transform': "rotate(#{tilt}deg)"
				'-o-transform': "rotate(#{tilt}deg)"
				'-webkit-transform': "rotate(#{tilt}deg)" )
			img.data('tilt', tilt) ), 40)

		$.get url_store,
			(raw, status) ->
				data = raw or {folds: {}, folds_ts: {}}
				if status != 'success' or not data
					alert("Failed to fetch data (#{status}): #{raw}")
				for own k,v of data.folds
					folds_update(k, v) if not folds_ts[k]? or data.folds_ts[k] > folds_ts[k]
				folds_commit()
				$('h1.feed').each (idx, el) -> fold_entries(el)
				$.post url_store, JSON.stringify({folds, folds_ts}),
					(raw, status) ->
						if status != 'success' or not JSON.parse(raw)
							alert("Failed to send data (#{status}): #{raw}")
						clearInterval(timer)


	/* (un)fold everything under the specified day-header */
	fold_entries = (h1, fold=null, unfold=false) ->
		h1 = $(h1)
		ts_day = h1.data('timestamp')
		ts_entry_max = 0

		/* (un)fold entries */
		h1.nextUntil('h1').children('.entry').each (idx, el) ->
			entry = $(el)
			ts = entry.data('timestamp')
			if unfold is true
				entry.children('.content').css('display', '')
			else if fold isnt false and folds[ts_day] >= ts
				entry.children('.content').css('display', 'none')
			ts_entry_max = ts if (not folds[ts_day]? or folds[ts_day] < ts) and ts > ts_entry_max

		/* (un)fold whole day */
		if unfold is true
			h1.nextUntil('h1').css('display', '')
		else if fold isnt false and (fold or ts_entry_max == 0)
			h1.nextUntil('h1').css('display', 'none')

		[ts_day, ts_entry_max]

	/* Buttons, initial fold */
	img_sync = if $.cookie('feedjack.tracking')
	then """<img title="fold sync" class="button_fold_sync" src="#{url_media}/fold_sync.png" />"""
	else ''
	$('h1.feed')
		.append(
			"""<img title="fold page" class="button_fold_all" src="#{url_media}/fold_all.png" />
			<img title="fold day" class="button_fold" src="#{url_media}/fold.png" />""" + img_sync )
		.each (idx, el) -> fold_entries(el)

	/* Fold sync button */
	$('.button_fold_sync').click(folds_sync)

	/* Fold day button */
	$('.button_fold').click (ev) ->
		h1 = $(ev.target).parent('h1')
		[ts_day, ts_entry_max] = fold_entries(h1, false)
		if ts_entry_max > 0
			fold_entries(h1, true)
			folds_update(ts_day, Math.max(ts_entry_max, folds[ts_day] or 0))
		else
			fold_entries(h1, false, true)
			folds_update(ts_day)
		folds_commit()

	/* Fold all button */
	$('.button_fold_all').click (ev) ->
		ts_page_max = 0
		h1s = $('h1.feed')
		h1s.each (idx, el) ->
			ts_page_max = Math.max(ts_page_max, fold_entries(el, false)[1])
		if ts_page_max > 0
			h1s.each (idx, el) ->
				[ts_day, ts_entry_max] = fold_entries(el, true)
				folds_update(ts_day, Math.max(ts_entry_max, folds[ts_day] or 0))
		else
			h1s.each (idx, el) ->
				[ts_day, ts_entry_max] = fold_entries(el, false, true)
				folds_update(ts_day)
		folds_commit()
