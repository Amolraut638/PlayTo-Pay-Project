from django.contrib import admin

from .models import BankAccount, IdempotencyKey, LedgerEntry, Merchant, Payout


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "created_at")


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("merchant", "label", "account_last4", "ifsc", "is_active")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("merchant", "direction", "reason", "amount_paise", "payout", "created_at")
    list_filter = ("direction", "reason")


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("merchant", "amount_paise", "status", "attempts", "created_at", "updated_at")
    list_filter = ("status",)


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("merchant", "key", "response_status", "expires_at", "payout")
