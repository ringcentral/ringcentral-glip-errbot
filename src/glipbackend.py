import sys
import logging
import functools

from errbot.backends.base import RoomError, Identifier, Person, RoomOccupant, ONLINE, Room, Message
from errbot.core import ErrBot
from errbot.utils import rate_limited
from time import sleep
from ringcentral.subscription import Events

log = logging.getLogger('errbot.backends.glip')

try:
    from ringcentral import SDK
except ImportError:
    log.exception("Could not start the Glip back-end")
    log.fatal(
        "You need to install the ringcentral package in order to use the Glip back-end. "
        "You should be able to install this package using: pip install ringcentral"
    )
    sys.exit(1)


MESSAGE_SIZE_LIMIT = 50000
rate_limit = 3  # one message send per {rate_limit} seconds


class Eql(object):
    def __init__(self, o):
        self.obj = o

    def __eq__(self, other):
        return True

    def __hash__(self):
        return 0


def lru_cache_ignoring_first_argument(*args, **kwargs):
    lru_decorator = functools.lru_cache(*args, **kwargs)

    def decorator(f):
        @lru_decorator
        def helper(arg1, *args, **kwargs):
            arg1 = arg1.obj
            return f(arg1, *args, **kwargs)

        @functools.wraps(f)
        def function(arg1, *args, **kwargs):
            arg1 = Eql(arg1)
            return helper(arg1, *args, **kwargs)

        return function

    return decorator


class GlipBotFilter(object):
    @staticmethod
    def filter(record):
        if record.getMessage() == "No new updates found.":
            return 0


class RoomsNotSupportedError(RoomError):
    def __init__(self, message=None):
        if message is None:
            message = (
                "Room operations are not supported"
            )
        super().__init__(message)


class GlipIdentifier(Identifier):
    def __init__(self, info):
        self._info = info

    @property
    def id(self):
        return self._info['id']

    def __hash__(self):
        return self.id

    def __unicode__(self):
        return self.id

    def __str__(self):
        return str(self.id)

    def __eq__(self, other):
        return self.id == other.id


class GlipPerson(GlipIdentifier, Person):
    def __init__(self, info):
        super().__init__(info)

    @property
    def first_name(self):
        return self._info['firstName']

    @property
    def person(self):
        return self.id

    @property
    def last_name(self):
        return self._info['lastName']

    @property
    def email(self):
        return self._info['email']

    @property
    def location(self):
        return self._info['location']

    @property
    def fullname(self):
        fullname = self.first_name
        if self.last_name is not None:
            fullname += " " + self.last_name
        return fullname

    @property
    def nick(self):
        return self.fullname

    @property
    def client(self):
        return None

    def aclattr(self):
        return self.id


class GlipRoom(GlipIdentifier, Room):
    def __init__(self, info):
        super().__init__(info)

    @property
    def topic(self):
        return self._info['name']

    def join(self, username: str = None, password: str = None):
        raise RoomsNotSupportedError()

    def create(self):
        raise RoomsNotSupportedError()

    def leave(self, reason: str = None):
        raise RoomsNotSupportedError()

    def destroy(self):
        raise RoomsNotSupportedError()

    @property
    def joined(self):
        raise RoomsNotSupportedError()

    @property
    def exists(self):
        raise RoomsNotSupportedError()

    @property
    def occupants(self):
        # TODO Batch request persons and return array
        raise RoomsNotSupportedError()

    def invite(self, *args):
        raise RoomsNotSupportedError()


class GlipRoomOccupant(GlipPerson, RoomOccupant):
    """
    This class represents a person inside a MUC.
    """

    def __init__(self, info, room):
        super().__init__(info)
        self._room = room

    @property
    def room(self):
        return self._room


class GlipBackend(ErrBot):
    def __init__(self, config):

        super().__init__(config)

        config.MESSAGE_SIZE_LIMIT = MESSAGE_SIZE_LIMIT
        logging.getLogger('Glip.bot').addFilter(GlipBotFilter())

        identity = config.BOT_IDENTITY

        self.username = identity.get('username', None)
        self.extension = identity.get('extension', None)
        self.password = identity.get('password', None)
        self.appKey = identity.get('appKey', None)
        self.appSecret = identity.get('appSecret', None)
        self.server = identity.get('server', None)

        self.sdk = SDK(self.appKey, self.appSecret, self.server, 'glipbot', '0.0.0')
        self.bot_identifier = None  # Will be set in serve_once

        log.debug("SDK instance created")

        # TODO Platform observable

        # compact = config.COMPACT_OUTPUT if hasattr(config, 'COMPACT_OUTPUT') else False
        # enable_format('text', TEXT_CHRS, borders=not compact)
        # self.md_converter = text()

    def authorize(self):
        self.sdk.platform().login(self.username, self.extension, self.password)
        self.bot_identifier = self.get_user_query('~')

    @lru_cache_ignoring_first_argument(128)
    def get_user_query(self, _id):
        try:
            user_info = self.sdk.platform().get('/account/~/extension/' + _id).json()
            return GlipPerson({
                'id': user_info.id,
                'email': user_info.email,
                'lastName': user_info.lastName,
                'firstName': user_info.firstName
            })
        except Exception as e:
            log.exception('Failed to load user %s', str(e))

    @lru_cache_ignoring_first_argument(128)
    def get_group(self, _id):
        try:
            group_info = self.sdk.platform().get('/glip/groups/' + _id).json_dict()
            return GlipRoom(group_info)
        except Exception as e:
            log.exception('Failed to load group %s', str(e))

    @lru_cache_ignoring_first_argument(128)
    def get_person(self, _id, room):
        try:
            person_info = self.sdk.platform().get('/glip/persons/' + _id).json_dict()
            return GlipRoomOccupant(person_info, room)
        except Exception as e:
            log.exception('Failed to load user %s', str(e))

    def serve_once(self):
        log.info("Initializing connection")
        s = None

        try:
            self.authorize()

            s = self.sdk.create_subscription()
            s.add_events(['/account/~/extension/~/glip/posts'])
            s.on(Events.notification, lambda msg: self._handle_message(msg))
            s.register()

            self.reset_reconnection_count()
            self.connect_callback()
            log.info('Connected')

            while self.sdk.platform().logged_in():  # If this condition is false, it means SDK failed to refresh
                sleep(0.1)

        except KeyboardInterrupt:
            log.info("Interrupt received, shutting down")
            if s:
                s.destroy()
            return True
        except:
            log.exception("Error reading from Glip updates stream")
        finally:
            log.debug("Triggering disconnect callback")
            self.disconnect_callback()

        return False

    def _get_message(self, id):
        return self.sdk.platform().get('/account/~/extension/~/glip/posts/' + id).json()

    def _handle_message(self, message):
        try:
            post = message['body']

            if post['eventType'] != 'PostAdded':
                return

            log.debug('Incoming message')
            log.debug(message)

            room = self.get_group(post['groupId'])
            sender = self.get_person(post['creatorId'], room)

            message_instance = Message(post['text'], sender, room)

            # self.callback_room_joined(self)  # TODO Implement
            self.callback_message(message_instance)

        except Exception as e:
            log.exception('Failed to handle message %s', str(e))

    @rate_limited(rate_limit)  # <---- Rate Limit
    def send_message(self, mess):
        super().send_message(mess)

        sent_message = self.sdk.platform().post('/glip/posts', {
            'groupId': str(mess.to),  # this is instance of GlipRoom
            'text': mess.body
        }).json_dict()

    def send_reply(self, mess, text):

        mess.body = text
        self.send_message(mess)

    def change_presence(self, status: str = ONLINE, message: str = '') -> None:
        pass

    def build_identifier(self, txtrep):
        """
        Convert a textual representation into a :class:`~GlipPerson` or :class:`~GlipRoom`.
        """
        log.debug("building an identifier from %s" % txtrep)
        return GlipPerson({'id': txtrep})  # Can also be Room

    def build_reply(self, mess, text=None, private=False):
        response = self.build_message(text)
        # response.frm = self.bot_identifier
        if private:
            response.to = mess.frm
        else:
            response.to = mess.frm if mess.is_direct else mess.to
        return response

    @property
    def mode(self):
        return 'Glip'

    def query_room(self, room):
        """
        :raises: :class:`~RoomsNotSupportedError`
        """
        raise RoomsNotSupportedError()

    def rooms(self):
        """
        :raises: :class:`~RoomsNotSupportedError`
        """
        raise RoomsNotSupportedError()

    def prefix_groupchat_reply(self, message, identifier):
        super().prefix_groupchat_reply(message, identifier)
        message.body = '@{0}: {1}'.format(identifier.nick, message.body)