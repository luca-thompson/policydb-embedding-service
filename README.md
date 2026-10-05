# policydb-embedding-service

Extraction of the embedding pipeline out into its own service, this service runs and at set intervals checks if the policy content has changed, if it has then it rebuilds the database, otherwise just waits until next interval
