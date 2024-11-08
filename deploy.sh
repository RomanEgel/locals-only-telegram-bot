# First, set up the service account for the Cloud Run service
PROJECT_ID=$(gcloud config get-value project)
SERVICE_NAME="telegram-bot"
SERVICE_ACCOUNT="${SERVICE_NAME}-sa"

# Create service account if it doesn't exist
gcloud iam service-accounts create ${SERVICE_ACCOUNT} \
    --display-name="Telegram Bot Service Account" \
    --project=${PROJECT_ID} || true

# Grant the service account permission to sign URLs
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountTokenCreator"

# Deploy the Cloud Run service with the service account
gcloud beta run deploy telegram-bot \
    --source . \
    --function main \
    --base-image gcr.io/serverless-runtimes/google-22/runtimes/python310 \
    --region europe-west3 \
    --service-account=${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com \
    --allow-unauthenticated