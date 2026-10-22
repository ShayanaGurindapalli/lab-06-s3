#!/usr/bin/env python3
"""Download books and stage them in a public S3 bucket."""

import json
import logging
import os
import sys
import time

import boto3
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def create_bucket(bucket):
    """Return True if the bucket exists afterwards, False otherwise."""
    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket: {bucket}")
        return True
    except ClientError as e:
        pass


def upload_index(bucket, index_path):
    """Upload index.html with the text/html content type."""
    try:
        with open(index_path, "rb") as f:
            s3.put_object(
                Bucket=bucket,
                Key="index.html",
                Body=f,
                ContentType="text/html",
            )
        log.info(f"Uploaded {index_path} to s3://{bucket}/index.html")
        return True
    except FileNotFoundError:
        log.error(f"Local file not found: {index_path}")
        return False
    except ClientError as e:
        log.error(f"Error uploading object: {e}")
        return False

def parse_args():
    """Return (list_file, index_path, bucket) from the command line."""
    if len(sys.argv) < 4:
        log.error("Usage: stage_books.py LIST_FILE INDEX_PATH BUCKET")
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]


def download_books(list_file, dest_dir):
    """Download each book in list_file to dest_dir; return local paths."""
    os.makedirs(dest_dir, exist_ok=True)

    with open(list_file) as f:
        urls = [line.strip() for line in f if line.strip()]

    paths = []
    for url in urls:
        path = os.path.join(dest_dir, url.split("/")[-1])

        if os.path.exists(path):
            log.info(f"Already downloaded: {path}")
            paths.append(path)
            continue

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, "wb") as out:
                out.write(response.content)
            log.info(f"Downloaded {url} to {path}")
            paths.append(path)
        except requests.RequestException as e:
            log.error(f"Error downloading {url}: {e}")

        time.sleep(1)  # be polite to Project Gutenberg

    return paths

def make_public(bucket):
    """Turn off Block Public Access and allow public reads of objects."""
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Bucket is now public: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error making bucket public: {e}")
        return False


def upload_files(bucket, file_paths):
    """Upload each file to the top level of the bucket; return the count."""
    count = 0
    for path in file_paths:
        key = os.path.basename(path)  # pg1342.txt, not books/pg1342.txt
        try:
            with open(path, "rb") as f:
                s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=f,
                    ContentType="text/plain; charset=utf-8",
                )
            log.info(f"Uploaded {path} to s3://{bucket}/{key}")
            count += 1
        except FileNotFoundError:
            log.error(f"Local file not found: {path}")
        except ClientError as e:
            log.error(f"Error uploading {path}: {e}")
    return count


def main():
    """Download books, create a public bucket, and upload everything."""
    list_file, index_path, bucket = parse_args()

    paths = download_books(list_file, "books")
    if not paths:
        log.error("No books were downloaded.")
        sys.exit(1)

    if not create_bucket(bucket):
        log.error("Could not create the bucket.")
        sys.exit(1)

    if not make_public(bucket):
        log.error("Could not make the bucket public.")
        sys.exit(1)

    uploaded = upload_files(bucket, paths)
    index_ok = upload_index(bucket, index_path)

    if uploaded == len(paths) and index_ok:
        log.info(f"Success: uploaded {uploaded} books and the index page.")
    else:
        log.error(f"Finished with problems: {uploaded}/{len(paths)} books uploaded.")
    log.info(f"Index page: https://{bucket}.s3.amazonaws.com/index.html")


if __name__ == "__main__":
    main()
