#!/bin/bash
set -euo pipefail
#Check arguments in seconds here
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 BOOK_URL BUCKET EXPIRES_IN_SECONDS" >&2
    exit 1
fi

URL="$1"
BUCKET="$2"
EXPIRES="$3"
FILE="$(basename "$URL")"
#Download book into books
mkdir -p books
curl -fsSL -o "books/$FILE" "$URL"
echo "Downloaded $URL to books/$FILE"
#Create bucket unless it exists
if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket already exists: $BUCKET"
else
    aws s3 mb "s3://$BUCKET" --region us-east-1
fi
#Upload book
aws s3 cp "books/$FILE" "s3://$BUCKET/$FILE" \
    --content-type "text/plain; charset=utf-8"
#Print URL
aws s3 presign "s3://$BUCKET/$FILE" --expires-in "$EXPIRES"
