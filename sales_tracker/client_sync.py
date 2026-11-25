"""Client-level helpers used when enquiries are created or moved.

- Referral source is stored per enquiry and can differ between a client's
  enquiries. A new enquiry for an existing client defaults to the referral of
  that client's previous enquiry (`client_referral`); it can be changed on the
  add or edit form without affecting the client's other enquiries.
- A client marked `new` becomes `current` once it has more than one enquiry.

Called from Sales Tracker add/edit and Monthly Award edit. Migration
`sales_tracker/0017` (applied 2026-11) once copied each client's referral to
all its enquiries; since then nothing syncs referrals between enquiries.
"""


def client_referral(client, exclude_pk=None):
    """The referral source of `client`'s most recent enquiry that has one, or None."""
    if client is None:
        return None
    qs = client.sales_enquiries.exclude(referral__isnull=True).exclude(referral='')
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.order_by('-date', '-created_at', '-pk').values_list('referral', flat=True).first()


def promote_new_client(client):
    """A `new` client with more than one enquiry becomes `current`."""
    if client is None or client.client_status != 'new':
        return
    if client.sales_enquiries.count() > 1:
        client.client_status = 'current'
        client.save(update_fields=['client_status'])
