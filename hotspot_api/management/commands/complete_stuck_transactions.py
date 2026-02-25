from django.core.management.base import BaseCommand
from hotspot_api.models import MpesaTransaction
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Manually complete stuck pending transactions and create vouchers'

    def add_arguments(self, parser):
        parser.add_argument('--phone', type=str, help='Phone number to complete transactions for')
        parser.add_argument('--all', action='store_true', help='Complete all pending transactions older than 5 minutes')
        parser.add_argument('--transaction-id', type=str, help='Specific checkout_request_id to complete')

    def handle(self, *args, **options):
        from hotspot_api.views import create_voucher_for_transaction
        
        self.stdout.write(self.style.WARNING('\n⚠️  MANUAL TRANSACTION COMPLETION TOOL\n'))
        self.stdout.write('=' * 80)
        
        if options['transaction_id']:
            transactions = MpesaTransaction.objects.filter(checkout_request_id=options['transaction_id'], status='PENDING')
        elif options['phone']:
            phone = options['phone']
            if phone.startswith('0'):
                phone = '254' + phone[1:]
            transactions = MpesaTransaction.objects.filter(phone_number=phone, status='PENDING')
        elif options['all']:
            cutoff_time = timezone.now() - timedelta(minutes=5)
            transactions = MpesaTransaction.objects.filter(status='PENDING', created_at__lt=cutoff_time)
        else:
            self.stdout.write(self.style.ERROR('\n❌ Please specify --phone, --transaction-id, or --all'))
            return
        
        if not transactions.exists():
            self.stdout.write(self.style.WARNING('\n⚠️  No pending transactions found'))
            return
        
        self.stdout.write(f'\n📋 Found {transactions.count()} pending transaction(s):\n')
        
        for txn in transactions:
            self.stdout.write('-' * 80)
            self.stdout.write(f"Phone: {txn.phone_number}")
            self.stdout.write(f"Amount: KSh {txn.amount}")
            self.stdout.write(f"Created: {txn.created_at}")
            self.stdout.write(f"Checkout Request ID: {txn.checkout_request_id}")
        
        self.stdout.write('\n' + '=' * 80)
        confirm = input('\n⚠️  Do you want to mark these as COMPLETED and create vouchers? (yes/no): ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('\n❌ Operation cancelled'))
            return
        
        completed_count = 0
        failed_count = 0
        
        for txn in transactions:
            try:
                import random
                import string
                fake_receipt = 'MANUAL' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                
                txn.status = 'COMPLETED'
                txn.mpesa_receipt_number = fake_receipt
                txn.transaction_id = fake_receipt
                txn.save()
                
                self.stdout.write(f'\n✅ Marked as completed: {txn.checkout_request_id}')
                
                voucher = create_voucher_for_transaction(txn)
                if voucher:
                    txn.voucher = voucher
                    txn.save()
                    self.stdout.write(f'   ✅ Voucher created: {voucher.code}')
                    self.stdout.write(f'   📱 SMS should be sent to: {txn.phone_number}')
                    completed_count += 1
                else:
                    self.stdout.write(f'   ⚠️  Voucher creation failed')
                    failed_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'\n❌ Error processing {txn.checkout_request_id}: {e}'))
                failed_count += 1
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS(f'\n✅ COMPLETED: {completed_count} transaction(s)'))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f'❌ FAILED: {failed_count} transaction(s)'))
        self.stdout.write('\n')