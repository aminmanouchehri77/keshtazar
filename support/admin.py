from django.contrib import admin

from .models import SupportConversation, SupportMessage


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    can_delete = False
    fields = ('sender', 'body', 'created_at', 'delivery_status', 'delivery_attempts', 'delivery_error')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SupportConversation)
class SupportConversationAdmin(admin.ModelAdmin):
    list_display = ('public_code_display', 'user', 'status', 'created_at', 'updated_at', 'message_count')
    list_filter = ('status', 'created_at')
    list_editable = ('status',)
    list_select_related = ('user',)
    inlines = (SupportMessageInline,)
    readonly_fields = ('id', 'session_token_hash', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'

    @admin.display(description='کد گفتگو', ordering='id')
    def public_code_display(self, obj):
        return obj.public_code

    @admin.display(description='تعداد پیام‌ها')
    def message_count(self, obj):
        return obj.messages.count()


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'delivery_status', 'created_at')
    list_filter = ('sender', 'delivery_status', 'created_at')
    search_fields = ('body',)
    readonly_fields = (
        'conversation', 'sender', 'body', 'created_at', 'delivery_status',
        'delivery_attempts', 'delivery_error', 'rubika_message_id', 'rubika_inbound_message_id',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
