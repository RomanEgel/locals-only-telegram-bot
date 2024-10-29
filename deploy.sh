gcloud beta run deploy telegram-bot \
    --source . \
    --function main \
    --base-image gcr.io/serverless-runtimes/google-22/runtimes/python310 \
    --region europe-west3 \
    --allow-unauthenticated