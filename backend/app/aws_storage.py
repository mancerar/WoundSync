import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger("woundsync-backend")

AWS_REGION = os.getenv("AWS_REGION")
DYNAMODB_IMAGE_TABLE = os.getenv("DYNAMODB_IMAGE_TABLE", "").strip()
DYNAMODB_UPLOAD_TTL_DAYS = int(os.getenv("DYNAMODB_UPLOAD_TTL_DAYS", "30"))


def _build_dynamodb_table():
    if not DYNAMODB_IMAGE_TABLE:
        logger.warning("DYNAMODB_IMAGE_TABLE not set. Upload metadata will not be persisted.")
        return None

    resource = boto3.resource(
        "dynamodb",
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    return resource.Table(DYNAMODB_IMAGE_TABLE)


dynamodb_table = _build_dynamodb_table()


def save_upload_metadata(
    *,
    wound_id: str,
    user_id: str,
    s3_bucket: str,
    s3_key: str,
    content_type: str,
    expires_in_seconds: int,
) -> Optional[Dict[str, Any]]:
    if dynamodb_table is None:
        return None

    now = datetime.now(timezone.utc)
    item: Dict[str, Any] = {
        "pk": f"WOUND#{wound_id}",
        "sk": f"UPLOAD#{now.isoformat()}#{uuid.uuid4().hex}",
        "entity_type": "image_upload",
        "woundId": wound_id,
        "userId": user_id,
        "wound_id": wound_id,
        "user_id": user_id,
        "s3_bucket": s3_bucket,
        "s3_key": s3_key,
        "content_type": content_type,
        "status": "url_generated",
        "created_at": now.isoformat(),
        "presigned_expires_in_seconds": expires_in_seconds,
    }

    if DYNAMODB_UPLOAD_TTL_DAYS > 0:
        item["ttl"] = int(now.timestamp()) + (DYNAMODB_UPLOAD_TTL_DAYS * 24 * 60 * 60)

    try:
        dynamodb_table.put_item(Item=item)
        return item
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Failed to save upload metadata to DynamoDB: %s", exc)
        return None
