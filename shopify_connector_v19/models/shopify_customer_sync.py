# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class ShopifyCustomerSync(models.AbstractModel):
    _name = 'shopify.customer.sync'
    _description = 'Shopify Customer Sync Engine'

    def get_or_create_partner(self, config, shopify_customer, shopify_order=None):
        """
        Find or create a res.partner from Shopify customer data.
        Uses email as primary identifier.

        Falls back to config.default_guest_partner_id if no email.
        Returns a res.partner record.
        """
        email = None
        if shopify_customer:
            email = shopify_customer.get('email', '').strip().lower() or None

        if not email:
            # No email — use guest partner configured for this store
            if config.default_guest_partner_id:
                return config.default_guest_partner_id
            else:
                raise Exception(_(
                    'Order has no customer email and no default guest partner '
                    'is configured for store: %s'
                ) % config.name)

        # Check existing customer mapping
        customer_mapping = self.env['shopify.customer.mapping'].search([
            ('config_id', '=', config.id),
            ('email', '=', email),
        ], limit=1)

        if customer_mapping and customer_mapping.partner_id:
            partner = customer_mapping.partner_id
            # Update if data changed
            self._update_partner_from_shopify(partner, shopify_customer, shopify_order)
            return partner

        # Search existing contact by email
        partner = self.env['res.partner'].search([
            ('email', '=', email),
            ('company_id', 'in', [False, config.company_id.id]),
        ], limit=1)

        if not partner:
            partner = self._create_partner_from_shopify(config, shopify_customer, shopify_order)
        else:
            self._update_partner_from_shopify(partner, shopify_customer, shopify_order)

        # Save customer mapping
        shopify_customer_id = shopify_customer.get('id', '') if shopify_customer else ''
        if shopify_customer_id:
            existing_mapping = self.env['shopify.customer.mapping'].search([
                ('config_id', '=', config.id),
                ('shopify_customer_id', '=', str(shopify_customer_id)),
            ], limit=1)
            if not existing_mapping:
                self.env['shopify.customer.mapping'].create({
                    'config_id': config.id,
                    'shopify_customer_id': str(shopify_customer_id),
                    'partner_id': partner.id,
                    'email': email,
                })

        return partner

    def _create_partner_from_shopify(self, config, shopify_customer, shopify_order=None):
        """Create a new res.partner from Shopify customer data."""
        first_name = shopify_customer.get('firstName', '') or ''
        last_name = shopify_customer.get('lastName', '') or ''
        name = f"{first_name} {last_name}".strip() or shopify_customer.get('email', 'Unknown')
        email = shopify_customer.get('email', '').strip().lower()
        phone = shopify_customer.get('phone', '') or ''

        vals = {
            'name': name,
            'email': email,
            'phone': phone,
            'customer_rank': 1,
            'company_id': config.company_id.id,
        }

        # Use shipping address from order if available
        shipping_address = None
        if shopify_order:
            shipping_address = shopify_order.get('shippingAddress')
        if not shipping_address and shopify_customer.get('defaultAddress'):
            shipping_address = shopify_customer.get('defaultAddress')

        if shipping_address:
            country = self._get_country(shipping_address.get('countryCode', ''))
            state = self._get_state(
                shipping_address.get('provinceCode', ''),
                country
            )
            vals.update({
                'street': shipping_address.get('address1', '') or '',
                'street2': shipping_address.get('address2', '') or '',
                'city': shipping_address.get('city', '') or '',
                'zip': shipping_address.get('zip', '') or '',
                'country_id': country.id if country else False,
                'state_id': state.id if state else False,
            })

        return self.env['res.partner'].create(vals)

    def _update_partner_from_shopify(self, partner, shopify_customer, shopify_order=None):
        """Update partner data if anything has changed."""
        if not shopify_customer:
            return

        first_name = shopify_customer.get('firstName', '') or ''
        last_name = shopify_customer.get('lastName', '') or ''
        name = f"{first_name} {last_name}".strip()
        phone = shopify_customer.get('phone', '') or ''

        vals = {}
        if name and partner.name != name:
            vals['name'] = name
        if phone and partner.phone != phone:
            vals['phone'] = phone

        if vals:
            partner.write(vals)

    def _get_country(self, country_code):
        """Get res.country from ISO code."""
        if not country_code:
            return None
        return self.env['res.country'].search([('code', '=', country_code.upper())], limit=1)

    def _get_state(self, province_code, country):
        """Get res.country.state from province code."""
        if not province_code or not country:
            return None
        return self.env['res.country.state'].search([
            ('code', '=', province_code),
            ('country_id', '=', country.id),
        ], limit=1)

    def get_shipping_address(self, config, shopify_address, parent_partner):
        """
        Create or retrieve a shipping address partner (child of main partner).
        """
        if not shopify_address:
            return parent_partner

        country = self._get_country(shopify_address.get('countryCode', ''))
        state = self._get_state(shopify_address.get('provinceCode', ''), country)

        # Search for existing matching address
        domain = [
            ('parent_id', '=', parent_partner.id),
            ('type', '=', 'delivery'),
            ('street', '=', shopify_address.get('address1', '') or ''),
            ('city', '=', shopify_address.get('city', '') or ''),
        ]
        existing = self.env['res.partner'].search(domain, limit=1)
        if existing:
            return existing

        name_parts = [
            shopify_address.get('firstName', '') or '',
            shopify_address.get('lastName', '') or ''
        ]
        name = ' '.join(filter(None, name_parts)) or parent_partner.name

        return self.env['res.partner'].create({
            'name': name,
            'type': 'delivery',
            'parent_id': parent_partner.id,
            'street': shopify_address.get('address1', '') or '',
            'street2': shopify_address.get('address2', '') or '',
            'city': shopify_address.get('city', '') or '',
            'zip': shopify_address.get('zip', '') or '',
            'country_id': country.id if country else False,
            'state_id': state.id if state else False,
            'phone': shopify_address.get('phone', '') or '',
        })
