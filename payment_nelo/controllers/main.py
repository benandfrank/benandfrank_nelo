# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import json
import logging
import requests
import werkzeug

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class NeloController(http.Controller):
    _confirm_url = '/payment/nelo/confirm'
    _cancel_url = '/payment/nelo/cancel'

    def _nelo_auth_payment(self, **params):
        acquirer = request.env['payment.acquirer'].sudo().search([('provider', '=', 'nelo')])
        payload = json.dumps({
            'checkoutToken': params['checkoutToken']
        })
        headers = {
            'Authorization': 'Bearer %s' % (acquirer.nelo_merchant_secret),
            'Content-Type': 'application/json',
            'x-device-platform': 'web',
            'x-app-version-code': '1'
        }
        try:
            url = '%s/payments' % (acquirer._get_nelo_urls()['rest_url'])
            authResponse = requests.request("POST", url, headers=headers, data=payload)
            _logger.info('Nelo - url requested %s' % url)
            _logger.info('Nelo - response: %s' % authResponse)
            authResponse.raise_for_status()
            authJsonResponse = authResponse.json()
            url = '%s/payments/%s/capture' % (acquirer._get_nelo_urls()['rest_url'], authJsonResponse['uuid'])
            captureResponse = requests.request("POST", url, headers=headers)
            _logger.info('Nelo - url requested %s' % url)
            _logger.info('Nelo - response: %s' % captureResponse)
            captureResponse.raise_for_status()
        except:
            claims = self._get_claims(params['checkoutToken'])
            if claims.get('reference'):
                request.env['payment.transaction'].sudo().search(
                    [('reference', '=', claims.get('reference'))]
                )._set_transaction_error(_('Request rejected by Nelo.'))
            return False
        
        data = {
            'reference': authJsonResponse['reference']
        }
        return request.env['payment.transaction'].sudo().form_feedback(data, 'nelo')
    
    def _get_claims(self, checkoutToken):
        try:
            claims_base64 = checkoutToken.split(".")[1]
            claims_base64 += "=" * ((4 - len(claims_base64) % 4) % 4) # add padding
            claims_bytes = base64.b64decode(claims_base64, validate=False)
            return json.loads(claims_bytes.decode('ascii'))
        except:
            _logger.info('Nelo - error decoding claims from checkoutToken')
            return json.loads('{}')

    @http.route('/payment/nelo/confirm', type='http', auth="public", methods=['GET'], csrf=False)
    def nelo_return(self, **query_params):
        if query_params and query_params['checkoutToken']:
            self._nelo_auth_payment(**query_params)
        return werkzeug.utils.redirect('/payment/process')

    @http.route('/payment/nelo/cancel', type='http', auth='public', methods=['GET'], csrf=False)
    def nelo_notify(self, **post):
        return werkzeug.utils.redirect('/payment/process')
