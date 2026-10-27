terraform {
  # Supply bucket, key, and region with -backend-config. The key must be
  # different for development, staging, and production.
  backend "s3" {
    encrypt = true
  }
}
