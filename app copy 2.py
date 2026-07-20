import os
import pandas as pd

from flask import Blueprint, jsonify, send_file, current_app
from azure.identity import DeviceCodeCredential
from msgraph import GraphServiceClient
from msgraph.generated.users.item.user_item_request_builder import UserItemRequestBuilder
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder


class Office365MailExporter:
    def __init__(self, client_id: str, tenant_id: str = "common", scopes=None):
        self.client_id = client_id
        self.tenant_id = tenant_id or "common"
        self.scopes = scopes or ["User.Read", "Mail.Read"]

        self.credential = DeviceCodeCredential(
            client_id=self.client_id,
            tenant_id=self.tenant_id
        )

        self.client = GraphServiceClient(
            credentials=self.credential,
            scopes=self.scopes
        )

    @staticmethod
    def _safe_email(recipient_obj):
        try:
            if recipient_obj and recipient_obj.email_address:
                name = recipient_obj.email_address.name or ""
                address = recipient_obj.email_address.address or ""
                if name and address:
                    return f"{name} <{address}>"
                return address
        except Exception:
            pass
        return ""

    @staticmethod
    def _safe_recipients(recipient_list):
        if not recipient_list:
            return ""
        values = []
        for item in recipient_list:
            value = Office365MailExporter._safe_email(item)
            if value:
                values.append(value)
        return "; ".join(values)

    async def get_current_user(self):
        query_params = UserItemRequestBuilder.UserItemRequestBuilderGetQueryParameters(
            select=["displayName", "mail", "userPrincipalName"]
        )
        request_config = UserItemRequestBuilder.UserItemRequestBuilderGetRequestConfiguration(
            query_parameters=query_params
        )
        return await self.client.me.get(request_configuration=request_config)

    async def get_all_messages(self, page_size: int = 100, max_messages: int | None = None):
        rows = []

        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            select=[
                "id",
                "subject",
                "from",
                "sender",
                "toRecipients",
                "ccRecipients",
                "bccRecipients",
                "receivedDateTime",
                "sentDateTime",
                "isRead",
                "hasAttachments",
                "importance",
                "bodyPreview",
                "conversationId",
                "internetMessageId",
                "parentFolderId",
            ],
            top=page_size,
            orderby=["receivedDateTime DESC"]
        )

        request_config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters=query_params
        )

        page = await self.client.me.messages.get(
            request_configuration=request_config
        )

        while page:
            if page.value:
                for msg in page.value:
                    rows.append({
                        "id": msg.id or "",
                        "subject": msg.subject or "",
                        "from": self._safe_email(getattr(msg, "from_", None)),
                        "sender": self._safe_email(getattr(msg, "sender", None)),
                        "toRecipients": self._safe_recipients(getattr(msg, "to_recipients", [])),
                        "ccRecipients": self._safe_recipients(getattr(msg, "cc_recipients", [])),
                        "bccRecipients": self._safe_recipients(getattr(msg, "bcc_recipients", [])),
                        "receivedDateTime": str(getattr(msg, "received_date_time", "") or ""),
                        "sentDateTime": str(getattr(msg, "sent_date_time", "") or ""),
                        "isRead": bool(getattr(msg, "is_read", False)),
                        "hasAttachments": bool(getattr(msg, "has_attachments", False)),
                        "importance": str(getattr(msg, "importance", "") or ""),
                        "bodyPreview": getattr(msg, "body_preview", "") or "",
                        "conversationId": getattr(msg, "conversation_id", "") or "",
                        "internetMessageId": getattr(msg, "internet_message_id", "") or "",
                        "parentFolderId": getattr(msg, "parent_folder_id", "") or "",
                    })

                    if max_messages is not None and len(rows) >= max_messages:
                        return rows

            if getattr(page, "odata_next_link", None):
                page = await self.client.me.messages.with_url(page.odata_next_link).get()
            else:
                break

        return rows

    async def export_to_excel(
        self,
        output_path: str = r"C:\\temp\\correos_office365.xlsx",
        page_size: int = 100,
        max_messages: int | None = None,
    ):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        rows = await self.get_all_messages(
            page_size=page_size,
            max_messages=max_messages
        )

        df = pd.DataFrame(rows)

        if df.empty:
            df = pd.DataFrame(columns=[
                "id",
                "subject",
                "from",
                "sender",
                "toRecipients",
                "ccRecipients",
                "bccRecipients",
                "receivedDateTime",
                "sentDateTime",
                "isRead",
                "hasAttachments",
                "importance",
                "bodyPreview",
                "conversationId",
                "internetMessageId",
                "parentFolderId",
            ])

        df.to_excel(output_path, index=False)
        return {
            "ok": True,
            "path": output_path,
            "total": len(df),
        }