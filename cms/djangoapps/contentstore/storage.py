"""
Storage backend for course import and export.
"""
from __future__ import absolute_import

from django.conf import settings
from django.core.files.storage import get_storage_class
from storages.backends.s3boto import S3BotoStorage
from storages.backends.azure_storage import AzureStorage
from storages.utils import setting


class ImportExportAzureStorage(AzureStorage):
    def __init__(self):
        azure_container = setting("COURSE_IMPORT_EXPORT_CONTAINER", settings.AZURE_STORAGE_CONTAINER_NAME)
        super(ImportExportAzureStorage, self).__init(container=azure_container)


class ImportExportS3Storage(S3BotoStorage):  # pylint: disable=abstract-method
    """
    S3 backend for course import and export OLX files.
    """

    def __init__(self):
        bucket = setting('COURSE_IMPORT_EXPORT_BUCKET', settings.AWS_STORAGE_BUCKET_NAME)
        super(ImportExportS3Storage, self).__init__(bucket=bucket, custom_domain=None, querystring_auth=True)

# pylint: disable=invalid-name
course_import_export_storage = get_storage_class(settings.COURSE_IMPORT_EXPORT_STORAGE)()
