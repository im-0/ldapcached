from __future__ import absolute_import

import abc
import copy
import logging
import re

import six

import dogpile.cache


# Logger.
_log = logging.getLogger(__name__)


class _BaseSearchMatch(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def match_request(self, request):
        pass


class _SearchFilterMatch(_BaseSearchMatch):
    def __init__(self, conf):
        splitted_conf = conf.split(':', 1)
        if len(splitted_conf) != 2:
            raise RuntimeError(
                'Search filter match should be in form "$type:$string": '
                '"%s"' % (conf, ))
        match_type, match_str = splitted_conf
        if match_type != 're':
            raise RuntimeError(
                'Only "re" type filter match is currently supported: "%s" != '
                '"re" in "%s"' % (match_type, conf))

        self._re = re.compile(match_str)

    def match_request(self, request):
        return self._re.match(request.filter.asText()) is not None


class _AllSearchFieldsMatch(_BaseSearchMatch):
    _SUPPORTED_FIELD_TYPES = {
        'filter': _SearchFilterMatch,
    }

    def __init__(self, conf):
        self._match_list = []
        for field_type, field_match_conf in six.iteritems(conf):
            field_type_cls = self._SUPPORTED_FIELD_TYPES.get(field_type)
            if field_type_cls is None:
                raise RuntimeError(
                    'Unsupported field type: "%s"' % (field_type, ))

            self._match_list.append(field_type_cls(field_match_conf))

    def match_request(self, request):
        return all(
            map(
                lambda match: match.match_request(request),
                self._match_list))


class _AnySearchRequestMatch(_BaseSearchMatch):
    def __init__(self, conf):
        if not conf:
            raise RuntimeError(
                'No templates configured for caching search requests')

        self._match_list = [
            _AllSearchFieldsMatch(request_match_conf)
            for request_match_conf in conf]

    def match_request(self, request):
        return any(
            map(
                lambda match: match.match_request(request),
                self._match_list))


class _CacheRegion(object):
    def __init__(self, name, common_conf, conf):
        # TODO: Use as prefix.
        del name

        conf = copy.deepcopy(conf)

        templates = conf.pop('templates', [])
        self._match = _AnySearchRequestMatch(templates)

        self._cache_region = dogpile.cache.make_region()
        self._cache_region.configure(
            **dict(common_conf, **conf))

    def match_request(self, request):
        return self._match.match_request(request)

    def set(self, *args, **kwargs):
        return self._cache_region.set(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self._cache_region.get(*args, **kwargs)


def _get_cache_key(request, controls):
    request = None if request is None else str(request)
    controls = None if controls is None else str(controls)
    return request, controls


class LDAPSearchCache(object):
    def __init__(self, conf):
        common_conf = conf.get('common', {})

        self._regions = {}
        for region_name, region_conf in six.iteritems(conf.get('regions', {})):
            self._regions[region_name] = _CacheRegion(
                region_name, common_conf, region_conf)

    def _find_region(self, request):
        for region in six.itervalues(self._regions):
            if region.match_request(request):
                return region
        return None

    def put_search(self, request, controls, result_entries, result_done):
        if result_done.resultCode != 0:
            # Do not cache negative results.
            return
        if len(result_entries) == 0:
            # Do not cache empty search results.
            return

        cache_region = self._find_region(request)
        if cache_region is None:
            # Cache usage is not configured for such results.
            return

        cache_key = _get_cache_key(request, controls)
        cache_region.set(cache_key, (result_entries, result_done))

    def get_search(self, request, controls):
        _log.debug('Search filter string: "%s"', request.filter.asText())

        cache_region = self._find_region(request)
        if cache_region is None:
            # Cache usage is not configured for such results.
            _log.info('Cache DISABLED: %r, %r', request, controls)
            return

        cache_key = _get_cache_key(request, controls)
        result = cache_region.get(cache_key)
        if result == dogpile.cache.region.NO_VALUE:
            _log.info('Cache MISS: %r, %r', request, controls)
            return None
        else:
            _log.info('Cache HIT: %r, %r', request, controls)
            return result
