from __future__ import print_function
from future.utils import iteritems
import sys
import base64
import uuid
import json
import logging
import pkg_resources
import traceback
import time
import os

# AppSync Subscription Manager imports
from .exceptions import *
from .types import *

# Depending modules
import warrant
import websocket
import six

try:
    VERSION = pkg_resources.require("appsync-subscription-manager")[0].version
except Exception:  # pylint: disable=broad-except
    VERSION = 'dev'

# Read GQL URL
LOCAL_GQL_HOST = os.environ.get('LOCAL_GQL_HOST', "epic-sandbox")
LOCAL_GQL_PORT = os.environ.get('LOCAL_GQL_PORT', "4000")
LOCAL_GQL_FRAG = "%s:%s" % (LOCAL_GQL_HOST, LOCAL_GQL_PORT)
GQL_PSK = os.environ.get("GQL_PSK", None)

# Logger for debugging
_LOGGER = logging.getLogger('appsync-sub-mgr')
_LOGGER.setLevel(logging.ERROR)
console = logging.StreamHandler()
console.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s'))
_LOGGER.addHandler(console)

# WebSocket GET request additional headers
WS_HEADERS = {
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Sec-WebSocket-Extensions': 'permessage-deflate; client_max_window_bits',
    'User-Agent': 'Python/{0[0]}.{0[1]} AppSyncSubscriptionManager/{1}'.format(sys.version_info, VERSION)
}

def set_gql_psk(gql_psk):
    global GQL_PSK
    GQL_PSK = gql_psk

def set_local_gql_frag(lgf):
    global LOCAL_GQL_FRAG
    LOCAL_GQL_FRAG = lgf

def b64encode(data):
    if six.PY2:
        return base64.b64encode(data)
    else:
        return base64.b64encode(data.encode()).decode()

def b64decode(data):
    if six.PY2:
        return base64.b64decode(data)
    else:
        return base64.b64decode(data.encode()).decode()

class AppSyncSubscription():
    def __init__(self, sub_id = None,
        sub_mgr = None,
        sub_query = None,
        sub_token = None,
        on_message = None,
        on_subscription_success = None,
        sub_filter = {},
        on_error = None):
        """
        sub_id: A unique ID for this subscription (UUID)
        sub_mgr: An instance of AppSyncSubscriptionManager class
        sub_query: Query for subscription
        sub_token: The id_token used to make this subscription
        on_message: Callback Function for received data and also the opaque cb data
        on_subscription_success: Callback Function 
        on_error: Callback Function with an exception representing the error and opaque cb data
        """
        self._subscription_id = sub_id
        self._subscription_mgr = sub_mgr
        self._subscription_query = sub_query
        self._id_token = sub_token
        self._on_message = on_message
        self._on_error = on_error
        self._on_subscription_success = on_subscription_success
        self._subscription_status = SubscriptionStatus.PENDING
        self._sub_filter = sub_filter
    
    def set_status(self, status):
        self._subscription_status = status

    def get_status(self):
        return self._subscription_status

    def get_id(self):
        return self._subscription_id

    def cancel(self):
        self._subscription_status = SubscriptionStatus.CLOSING
        self._subscription_mgr.cancel_subscription(self, self._subscription_id)

    def received_msg(self, msg):
        self._on_message(msg, self._subscription_mgr.get_cb_data())

    def on_subscription_success(self):
        self._on_subscription_success(self._subscription_mgr.get_cb_data(), self)

class AppSyncSubscriptionManager():
    def __init__(self, id_token = None,
        username = None, passwd = None,
        aws_cognito_pool_id = None, aws_cognito_pool_client_id = None,
        aws_region = 'us-west-2', appsync_api_id = None,
        on_connection_error = None, on_error = None, cb_data = None,
        use_local_instance = False,
        on_close = None, logger = None):
        """
        AppSyncSubscriptionManager handles adding/removing subscriptions to an AWS AppSync instance
        id_token: An un-expired access token to be used for authorization of subscriptions
        username: Username in AWS Cognito pool to use for authentication
        passwd: Password to use for authenticating the username provided
        aws_cognito_pool_id: AWS Cognito Pool ID to use for authentication purposes
        aws_cognito_pool_client_id: AWS Cognito Pool ID to use for authentication purposes.
          Client should not have a secret set.
        aws_region: AWS Region to use for all operations
        appsync_api_id: API ID of AppSync application to manage subscriptions for
        on_connection_error: Callback function to notify of errors while connecting to GQL API endpoint
        on_error: Callback function to notify non-connection related errors
        cb_data: Opaque data that is passed back with any callback functions that the Mgr calls
        logger: An instance of python logging getLogger
        """
        if not id_token and not(username and passwd and aws_cognito_pool_id and aws_cognito_pool_client_id):
            raise NoAuthProvided("Please provide a username/passwd/userpool_id/client or a valid id token")

        if not appsync_api_id:
            raise NoAppSyncApiIdProvided("Please provide an AppSync API ID")

        if not on_connection_error:
            raise NoConnetionErrorCBProvided("Please provide a callback function for connection error notifications")

        # Set logger
        if logger:
            global _LOGGER
            _LOGGER = logger

        # Set Auth params
        self.id_token = id_token
        self.username = username
        self.passwd = b64encode(passwd) if passwd else None
        self.aws_cognito_pool_id = aws_cognito_pool_id
        self.aws_cognito_pool_client_id = aws_cognito_pool_client_id
        self.on_connection_error = on_connection_error
        self.on_error = on_error
        self.on_close = on_close
        self.cb_data = cb_data
        self.use_local_instance = use_local_instance

        # Set AppSync API ID params
        self.aws_region = aws_region
        self.appsync_api_id = appsync_api_id

        # Initialize user & connetion state
        self._user = None
        self._connected = False

        # Initialize map to store subscriptions
        self._subscriptions_map = {}

        # Initialize map to store subscriptions received before
        # connection to AppSync is established
        self._pending_subscriptions_map = {}

        # Initialize AppSync API hostnames
        if not use_local_instance:
            self._api_host = '%s.appsync-api.%s.amazonaws.com' % (self.appsync_api_id, self.aws_region)
            self._realtime_api_host = '%s.appsync-realtime-api.%s.amazonaws.com' % (self.appsync_api_id, self.aws_region)
        else:
            self._api_host = 'http://' + LOCAL_GQL_FRAG + '/graphql'
            self._realtime_api_host = 'http://' + LOCAL_GQL_FRAG + '/graphql'

        # Setup access token
        if id_token:
            self._cur_id_token = id_token
            self._can_update_token = False
            _LOGGER.debug("Using provided access token")
        else:
            self._can_update_token = True
            self._authenticate_user()

        self.headers = WS_HEADERS

        # Set WebSocket URL
        token_str = '{"Authorization":"%s","host":"%s"}' % (self._cur_id_token, self._api_host)
        token_encoded = b64encode(token_str)
        if not use_local_instance:
            self._ws_url = "wss://%s?header=%s&payload=e30=" % (self._realtime_api_host, token_encoded)
        else:
            self._ws_url = "ws://%s/graphql?header=%s&payload=e30=" % (LOCAL_GQL_FRAG, token_encoded)

        #websocket.enableTrace(True)
        self._ws = websocket.WebSocketApp(self._ws_url,
            on_message = self._ws_on_message,
            on_error = self._ws_on_error,
            on_close = self._ws_on_close,
            on_open = self._ws_on_open,
            header = self.headers,
            subprotocols = ['graphql-ws'])
        self._socket_status = SocketStatus.CONNECTING
        #thread.start_new_thread(self._ws.run_forever, (), {'origin': 'http://localhost:3000'})

    def run_forever(self, origin='http://localhost:3000'):
        self._ws.run_forever(origin=origin)

    def _authenticate_user(self):
        # Try to authenticate the user provided
        self._user = warrant.Cognito(self.aws_cognito_pool_id,
            self.aws_cognito_pool_client_id,
            username=self.username)

        try:
            # Try to authenticate the user
            self._user.authenticate(password=b64decode(self.passwd))
        except Exception as e:
            # Authentication failed...
            _LOGGER.error("User Authentication failed: %s" % (str(e)))
            raise UserAuthFailed(str(e))

        self._cur_id_token = self._user.id_token

    def _get_subscription(self, sub_id):
        return self._subscriptions_map.get(sub_id, None)

    def _send_subscription_msg(self, sub_id, tmp_sub):
        sub_msg = {
            'id': sub_id,
            'payload': {
                'data': json.dumps({"query": "%s" % (tmp_sub._subscription_query), 'variables': tmp_sub._sub_filter}, separators=(',', ':')),
                'extensions': {
                    'authorization': {
                        'host': self._api_host,
                        'x-amz-user-agent': "aws-amplify/2.2.0 js"
                    }
                }
            },
            'type': "start"
        }

        if not self.use_local_instance:
            sub_msg['payload']['extensions']['authorization']['Authorization'] = self._cur_id_token
        else:
            sub_msg['payload']['extensions']['authorization']['x-api-key'] = GQL_PSK

        _LOGGER.info("Sending subscription: %s" % (sub_id))
        self._send(json.dumps(sub_msg, separators=(',', ':')))

    def _handle_connection_ack(self):
        _LOGGER.debug("Sending pending subscriptions...")
        # Send pending subscriptions
        for (sub_id, tmp_sub) in iteritems(self._pending_subscriptions_map):
            self._send_subscription_msg(sub_id, tmp_sub)
            # Move to the subscriptions map
            self._subscriptions_map[sub_id] = tmp_sub

        # Reset the pending subscriptions map
        self._pending_subscriptions_map = {}

    def _update_subscription_acked(self, msg):
        tmp_sub = self._get_subscription(msg['id'])

        if tmp_sub:
            tmp_sub.set_status(SubscriptionStatus.CONNECTED)
            tmp_sub.on_subscription_success()
        else:
            _LOGGER.error("Could not find subscription for ID: %s" % (msg['id']))

    def _handle_subscription_complete(self, msg):
        tmp_sub = self._get_subscription(msg['id'])

        if tmp_sub:
            self._subscriptions_map.pop(msg['id'], None)
        else:
            _LOGGER.error("Could not find subscription for ID: %s" % (msg['id']))

    def _handle_subscription_data(self, msg):
        tmp_sub = self._get_subscription(msg['id'])

        if tmp_sub:
            sub_status = tmp_sub.get_status()

            if sub_status != SubscriptionStatus.CONNECTED:
                _LOGGER.error("Skipping subscription data, current state: %r" % (sub_status))
                return
            else:
                try:
                    tmp_sub.received_msg(msg['payload'])
                except:
                    traceback.print_exc(file=sys.stderr)
        else:
            _LOGGER.error("Could not find subscription for ID: %s" % (msg['id']))

    def _handle_connection_error(self, msg):
        self.on_connection_error(ConnectionError(",".join(["%s: Error CODE: %s" % (tmp_err['errorType'], tmp_err['errorCode']) for tmp_err in msg['payload']['errors']])),
            self.cb_data)

    def _ws_on_message(self, message):
        try:
            msg = json.loads(message)
            if not msg:
                _LOGGER.error("Received empty message, ignoring...")
                return
        except Exception as e:
            _LOGGER.error("Could not parse WebSocket message: %s Exception: %s" % (message, str(e)))
            return

        try:
            if msg['type'] == MessageTypes.GQL_CONNECTION_ERROR:
                _LOGGER.error("Received connection error: %r" % (message))
                self._handle_connection_error(msg)
            elif msg['type'] == MessageTypes.GQL_CONNECTION_ACK:
                _LOGGER.debug("Received connection ack...")
                self._handle_connection_ack()
            elif msg['type'] == MessageTypes.GQL_START_ACK:
                _LOGGER.debug("Received subscription ack msg: %s" % (msg['id']))
                self._update_subscription_acked(msg)
            elif msg['type'] == MessageTypes.GQL_CONNECTION_KEEP_ALIVE:
                _LOGGER.debug("Received KeepAlive...")
            elif msg['type'] == MessageTypes.GQL_DATA:
                _LOGGER.debug("Received subscription data")
                self._handle_subscription_data(msg)
            elif msg['type'] == MessageTypes.GQL_COMPLETE:
                _LOGGER.debug("Received subscription complete: %s" % (msg['id']))
                self._handle_subscription_complete(msg)
            elif msg['type'] == MessageTypes.GQL_ERROR:
                _LOGGER.error("Received Subscription Error: %r" % (msg))
                _LOGGER.error("Received Subscription Error(GQL_ERROR): ID: %s MSG: %s" % (msg['id'],
                    ",".join(["%s: %s" % (tmp_err.get('errorType', 'error'), tmp_err.get('message', 'NO MSG')) for tmp_err in msg.get('payload', {}).get('errors', [])])))
            else:
                _LOGGER.error("Unhandled message type: %s" % (msg['type']))
        except Exception as e:
            _LOGGER.error("Could not handle WebSocket message: %s Exception: %r" % (message, e))
            return

    def _ws_on_error(self, error):
        _LOGGER.error(error)

    def _ws_on_close(self):
        self._socket_status = SocketStatus.CLOSED
        _LOGGER.info("### WebSocket closed ###")
        self.on_close(self.cb_data)

    def _ws_on_open(self):
        self._socket_status = SocketStatus.READY
        _LOGGER.info("WebSocket connected, sending connection init")
        conn_init_msg = {"type": "connection_init"}
        self._send(json.dumps(conn_init_msg, separators=(',', ':')))

    def _send(self, msg):
        self._ws.send(msg)

    def get_cb_data(self):
        return self.cb_data

    def close(self):
        self._ws.close()

    def cancel_subscription(self, sub, sub_id):
        _LOGGER.debug("Cancel subscription: %s" % (sub_id))
        msg = {
            "id": sub_id,
            "type": "stop"
        }
        self._send(json.dumps(msg, separators=(',', ':')))

    def subscribe(self, query, on_message, on_error,
        on_subscription_success, sub_filter={}):
        tmp_sub_id = str(uuid.uuid4())
        tmp_sub = AppSyncSubscription(sub_id = tmp_sub_id,
            sub_mgr = self, sub_query = query,
            sub_token = self._cur_id_token,
            on_message = on_message,
            on_subscription_success = on_subscription_success,
            sub_filter = sub_filter,
            on_error = on_error)
        
        if self._socket_status == SocketStatus.READY:
            self._send_subscription_msg(tmp_sub_id, tmp_sub)
        else:
            # Socket isn't ready, save subscription in pending map
            _LOGGER.info("Subscription pending: %s" % (tmp_sub_id))
            self._pending_subscriptions_map[tmp_sub_id] = tmp_sub
        
        return tmp_sub
