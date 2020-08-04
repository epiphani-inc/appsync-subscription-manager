# appsync-subscription-manager
epiphani AWS AppSync Subscription Manager

## Installation
```
$ pip install epiphani-appsync-subscription-manager
```

#### A package for managing GraphQL subscriptions for AWS AppSync

Currently supported AppSync authentication is AWS Cognito only.  Future enhancements will add support for
API Key, AWS IAM & OpenID.

For AWS Cognito, this package currently supports 2 modes of authentication:
- Provide an Access Token as argument:
  - **access_token** - An authenticated, unexpired, Access Token
- Provide the following arguments, the user will be authenticated and the resulting access_token used for making subscriptions:
  - **username** - Username of user in AWS Cognito Pool
  - **passwd** - Password of username
  - **aws_cognito_pool_id** - AWS Cognito Pool ID
  - **aws_cognito_pool_client_id** - AWS Cognito Pool Client ID (one with no secret key)

### Other Arguments
- **aws_region** The AWS Region of the AppSync API to use
- **appsync_api_id** The API ID of the AppSync API to make subscriptions to
