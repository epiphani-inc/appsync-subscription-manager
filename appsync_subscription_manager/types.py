# python standard modules
from enum import IntEnum, Enum

# Depending modules
import six

__all__ = [
    'SubscriptionStatus',
    'SocketStatus',
    'MessageTypes'
]

class SubscriptionStatus(IntEnum):
    PENDING = 1
    CONNECTED = 2
    CLOSING = 3
    CLOSED = 4
    FAILED = 5

class SocketStatus(IntEnum):
    CONNECTING = 1
    READY = 2
    CLOSED = 3

class MessageTypes(Enum):
    def __eq__(self, other):
        if self.__class__ is other.__class__:
            return self.value == other.value
        elif (isinstance(other, str)
              or (not six.PY3 and isinstance(other, unicode))):
            return self.value == other
        return NotImplemented
    '''
     * Client -> Server message.
     * This message type is the first message after handshake and this will initialize AWS AppSync RealTime communication
    '''
    GQL_CONNECTION_INIT = 'connection_init'
    '''
     * Server -> Client message
     * This message type is in case there is an issue with AWS AppSync RealTime when establishing connection
    '''
    GQL_CONNECTION_ERROR = 'connection_error'
    '''
     * Server -> Client message.
     * This message type is for the ack response from AWS AppSync RealTime for GQL_CONNECTION_INIT message
    '''
    GQL_CONNECTION_ACK = 'connection_ack'
    '''
     * Client -> Server message.
     * This message type is for register subscriptions with AWS AppSync RealTime
    '''
    GQL_START = 'start'
    '''
     * Server -> Client message.
     * This message type is for the ack response from AWS AppSync RealTime for GQL_START message
    '''
    GQL_START_ACK = 'start_ack'
    '''
     * Server -> Client message.
     * This message type is for subscription message from AWS AppSync RealTime
    '''
    GQL_DATA = 'data'
    '''
     * Server -> Client message.
     * This message type helps the client to know is still receiving messages from AWS AppSync RealTime
    '''
    GQL_CONNECTION_KEEP_ALIVE = 'ka'
    '''
     * Client -> Server message.
     * This message type is for unregister subscriptions with AWS AppSync RealTime
    '''
    GQL_STOP = 'stop'
    '''
     * Server -> Client message.
     * This message type is for the ack response from AWS AppSync RealTime for GQL_STOP message
    '''
    GQL_COMPLETE = 'complete'
    '''
     * Server -> Client message.
     * This message type is for sending error messages from AWS AppSync RealTime to the client
    '''
    GQL_ERROR = 'error' #Server -> Client

