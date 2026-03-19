# hotspot_api/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal

from .models import MpesaTransaction, HotspotCustomer


@receiver(post_save, sender=MpesaTransaction)
def create_or_update_hotspot_customer(sender, instance, created, **kwargs):
    """
    Triggered after an MpesaTransaction is saved.

    When a transaction reaches COMPLETED status for the first time:
      1. Creates or updates the HotspotCustomer record (expenditure tracking)
      2. Marks the transaction as customer_credited to prevent double-counting

    Note: Points awarding happens inside mpesa_callback (views.py) so it has
    access to the full transaction object and can pass it to PointsTransaction.
    We keep this signal lean — customer record only.
    """
    if instance.status == 'COMPLETED' and not instance.customer_credited:
        phone_number = instance.phone_number
        amount_paid  = instance.amount

        customer, is_new = HotspotCustomer.objects.get_or_create(
            phone=phone_number,
            defaults={
                'expenditure':     amount_paid,
                'account_balance': Decimal('0.00'),
            }
        )

        if not is_new:
            customer.expenditure += amount_paid
            customer.save(update_fields=['expenditure'])

        # Prevent future double-counting without retriggering the signal
        MpesaTransaction.objects.filter(pk=instance.pk).update(customer_credited=True)

        # Link voucher phone if missing
        if instance.voucher and not instance.voucher.phone_number:
            instance.voucher.phone_number = phone_number
            instance.voucher.save(update_fields=['phone_number'])