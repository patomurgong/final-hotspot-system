from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import MpesaTransaction, HotspotCustomer
from decimal import Decimal # 👈 ADDED: Required for Decimal('0.00') initialization

@receiver(post_save, sender=MpesaTransaction)
def create_or_update_hotspot_customer(sender, instance, created, **kwargs):
    """
    Triggered after an MpesaTransaction is saved.
    Credits the HotspotCustomer only if the transaction is COMPLETED 
    AND the customer_credited flag is False, preventing double-counting.
    """
    
    # 1. Check if the transaction is completed AND the customer has NOT been credited yet
    if instance.status == 'COMPLETED' and not instance.customer_credited:
        
        phone_number = instance.phone_number
        amount_paid = instance.amount
        
        # 2. Get or Create the HotspotCustomer
        customer, is_new = HotspotCustomer.objects.get_or_create(
            phone=phone_number,
            defaults={
                # Set initial expenditure for new customer
                'expenditure': amount_paid, 
                'account_balance': Decimal('0.00'),
            }
        )

        if not is_new:
            # 3. If customer exists, update expenditure
            customer.expenditure += amount_paid
            # Note: We include 'account_balance' in update_fields to avoid loading the entire object just for this single update.
            # However, since we don't modify balance here, it's safer to stick to only what changes or simplify the update.
            # Using F expressions is ideal for concurrent updates but this signal approach works for simple cases:
            customer.save(update_fields=['expenditure'])
            
        # 4. Mark the transaction as credited to prevent future double-counting
        # We use .update() to avoid re-triggering the signal, which would cause infinite recursion.
        MpesaTransaction.objects.filter(pk=instance.pk).update(customer_credited=True)

        # 5. Link voucher phone number (safe to run multiple times)
        if instance.voucher and not instance.voucher.phone_number:
             instance.voucher.phone_number = phone_number
             instance.voucher.save(update_fields=['phone_number'])
