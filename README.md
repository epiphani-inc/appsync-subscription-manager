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

## Using the AppSync Subscription Manager

Here is an example of using the subscription manager to register for notifications when a user is created.

```python
import appsync_subscription_manager as asm

AWS_APPSYNC_GQL_ENDPOINT_ID = 'dnj38asdfkn344nmkfndfnkl4nlk'
ID_TOKEN = 'JWT_ID_TOKEN'

USER_CREATE_SUBSCRIPTION = """
  subscription OnCreateUser {
    onCreateUser {
      id
      createdAt
      updatedAt
      userName
      fullName
    }
  }
"""

USER_UPDATE_SUBSCRIPTION = """
  subscription OnUpdateUser {
    onUpdateUser {
      id
      createdAt
      updatedAt
      userName
      fullName
    }
  }
"""
      
my_cb_data = {
    'current_env': 'dev',
}

def on_connection_error(error, cb_data):
    print("Got an error while making WebSocket connection: %r" % (error))

def on_close(cb_data):
    print("WebSocket connection closed")

def on_error(error, cb_data):
    print("Got an error on WebSocket connection: %r" % (error))

def user_create_subscription_error(error, cb_data):
    print("Subscription failed: %r" % (error))

def user_create_subscription_success(cb_data):
    print("Subscription succeeded")

def user_created(user_msg, cb_data):
    print("user created")

def user_update_subscription_error(error, cb_data):
    print("Subscription failed: %r" % (error))

def user_update_subscription_success(cb_data):
    print("Subscription succeeded")

def user_updated(user_msg, cb_data):
    print("user updated")

# sub: subscription object that you got (my_sub variable below)
#      when you made the subscription request is returned
#      back in the callback
def on_subscription_success(cb_data, sub):
    print("Got subscription success...")

# create an instance of the subscription manager using token
# based authentication. Refer to the README.md to subscribe
# using username/password for a cognito pool user
my_mgr = asm.AppSyncSubscriptionManager(id_token = ID_TOKEN,
    appsync_api_id = AWS_APPSYNC_GQL_ENDPOINT_ID,
    on_connection_error = on_connection_error,
    on_error = on_error,
    on_close = on_close,
    cb_data = my_cb_data)

# subscribe for user creation notifications
user_create_sub = my_mgr.subscribe(USER_CREATE_SUBSCRIPTION, user_created,
    user_create_subscription_error, user_create_subscription_success)
user_update_sub = my_mgr.subscribe(USER_UPDATE_SUBSCRIPTION, user_updated,
    user_update_subscription_error, user_update_subscription_success)

# Start the read loop to wait for subscription notifications
my_mgr.run_forever()
```
