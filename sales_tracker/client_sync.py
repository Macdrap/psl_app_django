"""Keep client-level facts consistent across a client's sales enquiries.

- Referral source belongs to the client: every enquiry from the same client
  carries the same `referral` value.
- A client marked `new` becomes `current` once it has more than one enquiry.

Called from the views that create an enquiry or can move one to another
client (Sales Tracker add/edit, Monthly Award edit). Migration
`sales_tracker/0017` applied the same rules to existing data.
"""


def client_referral(client, exclude_pk=None):
    """The referral source already recorded for `client`, or None.

    All of a client's enquiries share one value; if they somehow differ, the
    earliest enquiry's value (how the client first found us) wins.
    """
    if client is None:
        return None
    qs = client.sales_enquiries.exclude(referral__isnull=True).exclude(referral='')
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.order_by('date', 'created_at', 'pk').values_list('referral', flat=True).first()


def set_client_referral(client, referral):
    """Give every enquiry of `client` the same referral source (None clears it)."""
    if client is None:
        return
    client.sales_enquiries.update(referral=referral or None)


def promote_new_client(client):
    """A `new` client with more than one enquiry becomes `current`."""
    if client is None or client.client_status != 'new':
        return
    if client.sales_enquiries.count() > 1:
        client.client_status = 'current'
        client.save(update_fields=['client_status'])


def sync_moved_enquiry(enquiry, old_client_id, old_referral):
    """After `enquiry` was saved, keep its client's enquiries consistent.

    If the enquiry moved to another client and its referral wasn't changed,
    it takes the new client's existing referral (when that client has one).
    Otherwise the enquiry's referral is applied to all of its client's
    enquiries. Then the client is promoted from `new` if applicable.
    """
    client = enquiry.client
    if client is None:
        return
    referral = enquiry.referral or None
    if enquiry.client_id != old_client_id and referral == (old_referral or None):
        referral = client_referral(client, exclude_pk=enquiry.pk) or referral
    set_client_referral(client, referral)
    enquiry.referral = referral
    promote_new_client(client)
