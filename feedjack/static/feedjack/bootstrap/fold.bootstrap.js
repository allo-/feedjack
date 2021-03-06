// Generated by CoffeeScript 1.3.3
(function() {
  var localStorage_prefix, site_key, storage,
    __hasProp = {}.hasOwnProperty;

  site_key = $('script').last().data('site_key');

  localStorage_prefix = "feedjack." + site_key + ".fold";

  storage = null;

  $(document).on('fold_storage_init', function(ev, storage_obj) {
    storage = storage_obj;
    return $('.btn.fold-sync').show();
  });

  $(document).ready(function() {
    var fold_apply, fold_css, fold_entries, folds, folds_commit, folds_lru, folds_sync, folds_ts, folds_update, get_length, get_ts, limit, limit_lru, limit_lru_gc, _ref, _ref1;
    if (typeof localStorage === "undefined" || localStorage === null) {
      return;
    }
    limit_lru_gc = 300;
    limit_lru = 200;
    limit = 100;
    fold_css = 'folded';
    get_length = function(obj) {
      var k, len, v;
      len = 0;
      for (k in this) {
        if (!__hasProp.call(this, k)) continue;
        v = this[k];
        len += 1;
      }
      return len;
    };
    get_ts = function() {
      return Math.round((new Date()).getTime() / 1000);
    };
    _ref = [localStorage["" + localStorage_prefix + ".folds"], localStorage["" + localStorage_prefix + ".folds_lru"], localStorage["" + localStorage_prefix + ".folds_ts"]], folds = _ref[0], folds_lru = _ref[1], folds_ts = _ref[2];
    _ref1 = [folds ? JSON.parse(folds) : {}, folds_lru ? JSON.parse(folds_lru) : [], folds_ts ? JSON.parse(folds_ts) : {}], folds = _ref1[0], folds_lru = _ref1[1], folds_ts = _ref1[2];
    folds_update = function(key, value) {
      if (value == null) {
        value = 0;
      }
      folds[key] = value;
      folds_lru.push([key, value]);
      return folds_ts[key] = get_ts();
    };
    folds_commit = function() {
      var folds_lru_gc, key, len_folds, len_lru, val, _i, _len, _ref2, _ref3;
      len_lru = folds_lru.length;
      if (len_lru > limit_lru_gc) {
        _ref2 = [folds_lru.slice(len_lru - limit_lru, +len_lru + 1 || 9e9), folds_lru.slice(0, len_lru - limit_lru)], folds_lru = _ref2[0], folds_lru_gc = _ref2[1];
        len_folds = get_length(folds) - limit;
        for (_i = 0, _len = folds_lru_gc.length; _i < _len; _i++) {
          _ref3 = folds_lru_gc[_i], key = _ref3[0], val = _ref3[1];
          if (len_folds <= 0) {
            break;
          }
          if (folds[key] === val) {
            folds_update(key);
            len_folds -= 1;
          }
        }
      }
      localStorage["" + localStorage_prefix + ".folds"] = JSON.stringify(folds);
      localStorage["" + localStorage_prefix + ".folds_lru"] = JSON.stringify(folds_lru);
      return localStorage["" + localStorage_prefix + ".folds_ts"] = JSON.stringify(folds_ts);
    };
    folds_sync = function(ev) {
      var btn;
      if (!(storage != null)) {
        alert('Unable to remote storage api.');
        return;
      }
      btn = $(ev.target).parents('.btn').andSelf().filter('.btn');
      btn.button('loading');
      return storage.get(site_key, function(error, data) {
        var k, v, _ref2;
        if (error && error !== 404) {
          return btn.button('reset');
        }
        data = JSON.parse(data || "null") || {
          folds: {},
          folds_ts: {}
        };
        _ref2 = data.folds;
        for (k in _ref2) {
          if (!__hasProp.call(_ref2, k)) continue;
          v = _ref2[k];
          if (!(folds_ts[k] != null) || data.folds_ts[k] > folds_ts[k]) {
            folds_update(k, v);
          }
        }
        folds_commit();
        $('.fold-controls .fold-toggle').each(function() {
          return fold_apply(this);
        });
        return storage.put(site_key, JSON.stringify({
          site_key: site_key,
          folds: folds,
          folds_ts: folds_ts
        }), function(error) {
          return btn.button('reset');
        });
      });
    };
    $('.btn.fold-sync').on('click', folds_sync);
    fold_entries = function(day, fold, unfold) {
      var ts_day, ts_entry_max;
      if (fold == null) {
        fold = null;
      }
      if (unfold == null) {
        unfold = false;
      }
      ts_day = day.data('timestamp');
      ts_entry_max = 0;
      day.find('.channel').each(function() {
        var channel, entries, fold_channel, links_channel, links_channel_unfold;
        channel = $(this);
        fold_channel = true;
        entries = channel.find('.entry');
        if (!entries.length) {
          fold_channel = false;
          ts_entry_max = 1;
        } else {
          entries.each(function() {
            var entry, fold_entry, fold_ts_day, links_entry, links_entry_unfold, ts;
            entry = $(this);
            ts = entry.data('timestamp');
            if (!ts) {
              ts_entry_max = 1;
              return;
            }
            fold_entry = false;
            fold_ts_day = folds[ts_day];
            if (unfold === true || !(fold_ts_day != null)) {
              entry.removeClass(fold_css);
            } else if (fold_ts_day >= ts) {
              if (fold !== false) {
                entry.addClass(fold_css);
                links_entry = entry.find('a');
                links_entry_unfold = function() {
                  entry.removeClass(fold_css);
                  links_entry.unbind('click', links_entry_unfold);
                  return false;
                };
                links_entry.on('click', links_entry_unfold);
              }
              fold_entry = true;
            }
            if (!fold_entry) {
              fold_channel = false;
              if (ts > ts_entry_max) {
                return ts_entry_max = ts;
              }
            }
          });
        }
        if (fold_channel) {
          channel.addClass(fold_css);
          links_channel = channel.find('a');
          links_channel_unfold = function() {
            channel.removeClass(fold_css);
            links_channel.unbind('click', links_channel_unfold);
            return false;
          };
          return links_channel.on('click', links_channel_unfold);
        } else {
          return channel.removeClass(fold_css);
        }
      });
      if (unfold === true) {
        day.removeClass(fold_css);
      } else if (fold !== false && (fold || ts_entry_max === 0)) {
        day.addClass(fold_css);
      }
      return [ts_day, ts_entry_max];
    };
    $('.fold-toggle').click(function(ev, toggle) {
      var day, fold_btn, ts_day, ts_entry_max, _ref2;
      if (toggle == null) {
        toggle = true;
      }
      fold_btn = $(ev.target).parents('.fold-toggle').andSelf();
      day = fold_btn.parents('.day');
      _ref2 = fold_entries(day, false), ts_day = _ref2[0], ts_entry_max = _ref2[1];
      if ((ts_entry_max === 0) ^ toggle) {
        fold_entries(day, true);
        folds_update(ts_day, Math.max(ts_entry_max, folds[ts_day] || 0));
        fold_btn.children('i').attr('class', 'icon-plus');
      } else {
        fold_entries(day, false, true);
        folds_update(ts_day);
        fold_btn.children('i').attr('class', 'icon-minus');
      }
      if (toggle) {
        return folds_commit();
      }
    });
    fold_apply = function(fold_btn) {
      var ts_day, ts_entry_max, _ref2;
      fold_btn = $(fold_btn);
      _ref2 = fold_entries(fold_btn.parents('.day')), ts_day = _ref2[0], ts_entry_max = _ref2[1];
      return fold_btn.children('i').attr('class', ts_entry_max === 0 ? 'icon-plus' : 'icon-minus');
    };
    return $('.fold-controls').each(function() {
      return $(this).show().find('.fold-toggle').each(function() {
        return fold_apply(this);
      });
    });
  });

}).call(this);
