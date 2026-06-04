locals {
  cognito_hosted_ui_url = "https://${aws_cognito_user_pool_domain.web.domain}.auth.${var.aws_region}.amazoncognito.com"
  web_url               = "https://${aws_cloudfront_distribution.web.domain_name}"
  web_source_dir        = "${path.module}/../../web"
}

resource "aws_cognito_user_pool_domain" "web" {
  domain       = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}"
  user_pool_id = aws_cognito_user_pool.api.id
}

resource "aws_s3_bucket" "web" {
  bucket = "${local.name_prefix}-web-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "web" {
  bucket = aws_s3_bucket.web.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "web" {
  bucket = aws_s3_bucket.web.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "web" {
  bucket = aws_s3_bucket.web.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "web" {
  bucket = aws_s3_bucket.web.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "${local.name_prefix}-web"
  description                       = "Signed CloudFront access to the private OpsPilot web bucket."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

resource "aws_cloudfront_response_headers_policy" "web_security" {
  name = "${local.name_prefix}-web-security"

  security_headers_config {
    content_security_policy {
      content_security_policy = "default-src 'self'; connect-src 'self' https:; img-src 'self' data:; script-src 'self'; style-src 'self'; base-uri 'self'; form-action 'self' https:; frame-ancestors 'none'"
      override                = true
    }

    content_type_options {
      override = true
    }

    frame_options {
      frame_option = "DENY"
      override     = true
    }

    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }

    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      override                   = true
      preload                    = true
    }
  }
}

resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  default_root_object = "index.html"
  comment             = "Private OpsPilot web interface"
  price_class         = "PriceClass_100"

  origin {
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_id                = "opspilot-private-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  default_cache_behavior {
    target_origin_id           = "opspilot-private-s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_optimized.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.web_security.id
  }

  ordered_cache_behavior {
    path_pattern               = "config.js"
    target_origin_id           = "opspilot-private-s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_disabled.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.web_security.id
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
    minimum_protocol_version       = "TLSv1.2_2021"
  }
}

data "aws_iam_policy_document" "web_bucket" {
  statement {
    sid     = "AllowCloudFrontReadOnly"
    effect  = "Allow"
    actions = ["s3:GetObject"]
    resources = [
      "${aws_s3_bucket.web.arn}/*",
    ]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.web.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id
  policy = data.aws_iam_policy_document.web_bucket.json
}

resource "aws_s3_object" "web_index" {
  bucket        = aws_s3_bucket.web.id
  key           = "index.html"
  source        = "${local.web_source_dir}/static/index.html"
  etag          = filemd5("${local.web_source_dir}/static/index.html")
  content_type  = "text/html; charset=utf-8"
  cache_control = "no-store"
}

resource "aws_s3_object" "web_styles" {
  bucket        = aws_s3_bucket.web.id
  key           = "styles.css"
  source        = "${local.web_source_dir}/static/styles.css"
  etag          = filemd5("${local.web_source_dir}/static/styles.css")
  content_type  = "text/css; charset=utf-8"
  cache_control = "public, max-age=300"
}

resource "aws_s3_object" "web_app" {
  bucket        = aws_s3_bucket.web.id
  key           = "app.js"
  source        = "${local.web_source_dir}/src/main.ts"
  etag          = filemd5("${local.web_source_dir}/src/main.ts")
  content_type  = "application/javascript; charset=utf-8"
  cache_control = "public, max-age=300"
}

resource "aws_s3_object" "web_config" {
  bucket        = aws_s3_bucket.web.id
  key           = "config.js"
  content_type  = "application/javascript; charset=utf-8"
  cache_control = "no-store"
  content = "window.OPSPILOT_CONFIG = ${jsonencode({
    apiUrl        = trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")
    clientId      = aws_cognito_user_pool_client.web.id
    cognitoDomain = local.cognito_hosted_ui_url
    redirectUri   = "${local.web_url}/callback"
    logoutUri     = local.web_url
    scopes = [
      "openid",
      "email",
      "profile",
      "${local.cognito_resource_identifier}/read",
      "${local.cognito_resource_identifier}/apply",
    ]
  })};"
}
