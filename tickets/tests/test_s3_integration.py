import boto3
from unittest.mock import patch
from django.test import TestCase, override_settings
from moto import mock_s3
from django.core.files.uploadedfile import SimpleUploadedFile
from storages.backends.s3boto3 import S3Boto3Storage
from tickets.models import Ticket, TicketAttachment, User
from django.utils import timezone
from datetime import datetime
import pytz

@mock_s3
@override_settings(
    AWS_ACCESS_KEY_ID='fake_access_key',
    AWS_SECRET_ACCESS_KEY='fake_secret_key',
    AWS_STORAGE_BUCKET_NAME='test-bucket',
    AWS_DEFAULT_ACL=None,
    AWS_S3_REGION_NAME='us-east-1',
)
class S3IntegrationTestCase(TestCase):

    def setUp(self):
        # 创建一个 fake s3 client，并生成 'test-bucket'
        self.s3_client = boto3.client('s3', region_name='us-east-1')
        self.s3_client.create_bucket(Bucket='test-bucket')

        # 创建学生用户
        self.student = User.objects.create_user(
            username="@john",
            email="john.doe@example.org",
            password="Password123",
            role="students"
        )

        # 让 ticket.created_at 固定为 2025-03-09
        fixed_time = datetime(2025, 3, 9, 10, 0, 0, tzinfo=pytz.UTC)
        with patch("django.utils.timezone.now", return_value=fixed_time):
            self.ticket = Ticket.objects.create(
                title="Test Ticket",
                creator=self.student,
            )

    def test_s3_upload_attachment_hello_txt(self):
        """
        测试：保存附件hello.txt，
        验证自动生成 attachments/john.doe@example.org/2025-03-09/hello.txt
        并确实上传到 mock S3
        """
        test_file = SimpleUploadedFile(
            "hello.txt", b"Hello S3 test!", content_type="text/plain"
        )

        attachment = TicketAttachment(ticket=self.ticket)
        # 这里会调用 TicketAttachment 的upload_to函数 => user_directory_path
        # 期望: "attachments/john.doe@example.org/2025-03-09/hello.txt"
        attachment.file.save("hello.txt", test_file, save=True)

        # 断言 file.name
        self.assertEqual(
            attachment.file.name,
            "attachments/john.doe@example.org/2025-03-09/hello.txt"
        )

        # 再检查 mock s3 是否真的有这个 key
        response = self.s3_client.list_objects_v2(Bucket="test-bucket")
        keys = [obj['Key'] for obj in response.get('Contents', [])]
        self.assertIn(
            "attachments/john.doe@example.org/2025-03-09/hello.txt",
            keys,
            "hello.txt not found in mock S3"
        )

    def test_s3_upload_attachment_test2_txt(self):

        test_file = SimpleUploadedFile(
            "test2.txt", b"Subfolder test", content_type="text/plain"
        )

        attachment = TicketAttachment(ticket=self.ticket)
        attachment.file.save("test2.txt", test_file, save=True)

        self.assertEqual(
            attachment.file.name,
            "attachments/john.doe@example.org/2025-03-09/test2.txt"
        )

        response = self.s3_client.list_objects_v2(Bucket="test-bucket")
        keys = [obj['Key'] for obj in response.get('Contents', [])]
        self.assertIn(
            "attachments/john.doe@example.org/2025-03-09/test2.txt",
            keys,
            "test2.txt not found in mock S3"
        )
