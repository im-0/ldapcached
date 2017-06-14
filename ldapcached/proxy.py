from __future__ import absolute_import

import logging

import twisted.internet

import ldaptor.protocols.pureber
import ldaptor.protocols.pureldap
import ldaptor.protocols.ldap.ldaperrors
import ldaptor.protocols.ldap.proxybase


# Logger.
_log = logging.getLogger(__name__)


class LDAPProxy(ldaptor.protocols.ldap.proxybase.ProxyBase):
    def __init__(self, cache):
        ldaptor.protocols.ldap.proxybase.ProxyBase.__init__(self)

        self._cache = cache

        self._search_result_acc = list()
        self._deferred_bind_request = None

    def _send_deferred_bind(self):
        if self._deferred_bind_request is None:
            return

        deferred_bind = self.client.send(self._deferred_bind_request)
        self._deferred_bind_request = None

        def _check_bind_result(result):
            if not isinstance(
                    result, ldaptor.protocols.pureldap.LDAPBindResponse):
                raise RuntimeError('Invalid response after bind request')
            if result.resultCode == 0:
                _log.debug('Successfull bind: %r', result)
            else:
                raise RuntimeError('Bind error: %r' % (result, ))

        def _bind_error(failure):
            raise RuntimeError('Bind failure: %r' % (failure, ))

        deferred_bind.addCallback(_check_bind_result)
        deferred_bind.addErrback(_bind_error)

    def handleBeforeForwardRequest(self, request, controls, reply):
        _log.debug('Request (before forward): %r', request)
        _log.debug('Controls (before forward): %r', controls)

        if isinstance(request, ldaptor.protocols.pureldap.LDAPBindRequest):
            if self._deferred_bind_request is not None:
                raise RuntimeError('Already bind')

            if request.dn or request.auth:
                # Do not defer bind requests with authentication.
                return twisted.internet.defer.succeed((request, controls))

            self._deferred_bind_request = request

            reply(ldaptor.protocols.pureldap.LDAPBindResponse(0))
            return None
        elif isinstance(request, ldaptor.protocols.pureldap.LDAPUnbindRequest):
            if self._deferred_bind_request is None:
                # There was no deferred bind.
                _log.info('Cache MISS: bind/unbind')
                return twisted.internet.defer.succeed((request, controls))

            self._deferred_bind_request = None

            _log.info('Cache HIT: bind/unbind avoided')

            return None
        elif isinstance(request, ldaptor.protocols.pureldap.LDAPSearchRequest):
            cached = self._cache.get_search(request, controls)
            if cached is not None:
                result_entries, result_done = cached
                for result_entry in result_entries:
                    reply(result_entry)
                reply(result_done)
                return None

        self._send_deferred_bind()
        return twisted.internet.defer.succeed((request, controls))

    def handleProxiedResponse(self, response, request, controls):
        _log.debug('Request (proxied): %r', request)
        _log.debug('Controls (proxied): %r', controls)
        _log.debug('Response (proxied): %r', response)

        if isinstance(request, ldaptor.protocols.pureldap.LDAPSearchRequest):
            if isinstance(response,
                          ldaptor.protocols.pureldap.LDAPSearchResultEntry):
                self._search_result_acc.append(response)
            elif isinstance(response,
                            ldaptor.protocols.pureldap.LDAPSearchResultDone):
                self._cache.put_search(
                    request, controls, self._search_result_acc, response)
                self._search_result_acc = list()
            else:
                raise RuntimeError(
                    'Unexpected response to LDAP search request: %r' % (
                        response, ))

        return twisted.internet.defer.succeed(response)


def _ldap_bind_request_repr(self):
    l = list()
    l.append('version={0}'.format(self.version))
    l.append('dn={0}'.format(repr(self.dn)))
    l.append('auth=****')
    if self.tag != self.__class__.tag:
        l.append('tag={0}'.format(self.tag))
    l.append('sasl={0}'.format(repr(self.sasl)))
    return self.__class__.__name__ + '(' + ', '.join(l) + ')'


# TODO: Get rid of monkey patching.
ldaptor.protocols.pureldap.LDAPBindRequest.__repr__ = _ldap_bind_request_repr
